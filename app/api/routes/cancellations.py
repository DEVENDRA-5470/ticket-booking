from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.booking import Booking, BookingSeat
from app.models.seat import Seat
from app.models.payment import Payment
from app.models.user import User
from app.models.food import FoodOrder
from app.models.notification import Notification

router = APIRouter()

@router.post("/{booking_id}")
def cancel_booking(booking_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    booking = db.get(Booking, booking_id)
    if not booking or booking.user_id != current_user.id: raise HTTPException(404, "Booking not found")
    if booking.status == "CANCELLED": return {"message": "Booking already cancelled", "booking_id": booking.id}
    booking.status = "CANCELLED"
    links = db.execute(select(BookingSeat).where(BookingSeat.booking_id == booking.id)).scalars().all()
    for link in links:
        seat = db.get(Seat, link.seat_id)
        if seat: seat.status = "AVAILABLE"
    food_orders = db.execute(select(FoodOrder).where(FoodOrder.booking_id == booking.id)).scalars().all()
    for order in food_orders:
        if order.status != "CANCELLED": order.status = "CANCELLED"
    payments = db.execute(select(Payment).where(Payment.booking_id == booking.id)).scalars().all()
    for payment in payments:
        if payment.status == "SUCCESS": payment.status = "REFUND_PENDING"
        elif payment.status == "PENDING": payment.status = "CANCELLED"
    db.add(Notification(user_id=current_user.id, channel="IN_APP", message=f"Booking {booking.reference} cancelled: tickets, food orders and payment flow cancelled", status="PENDING"))
    db.commit()
    return {"message": "Booking cancelled: tickets, food orders and payment flow cancelled", "booking_id": booking.id, "status": booking.status, "food_orders_cancelled": len(food_orders), "refunds_pending": len([p for p in payments if p.status == "REFUND_PENDING"])}
