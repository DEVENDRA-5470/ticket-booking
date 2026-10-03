from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.booking import Booking
from app.models.payment import Payment
from app.models.user import User

router = APIRouter()

@router.post("/{booking_id}")
def create_payment(booking_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    booking = db.get(Booking, booking_id)
    if not booking or booking.user_id != current_user.id: raise HTTPException(404, "Booking not found")
    payment = Payment(booking_id=booking.id, amount=0, status="PENDING", provider_reference=f"SIM-{uuid4().hex[:12].upper()}")
    db.add(payment); db.commit(); db.refresh(payment)
    return payment

@router.post("/{payment_id}/complete")
def complete_payment(payment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    payment = db.get(Payment, payment_id)
    if not payment: raise HTTPException(404, "Payment not found")
    booking = db.get(Booking, payment.booking_id)
    if not booking or booking.user_id != current_user.id: raise HTTPException(404, "Payment not found")
    if payment.status == "REFUNDED": raise HTTPException(409, "Payment already refunded")
    payment.status = "SUCCESS"; db.commit(); db.refresh(payment)
    return payment

@router.post("/{payment_id}/refund")
def refund_payment(payment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    payment = db.get(Payment, payment_id)
    if not payment: raise HTTPException(404, "Payment not found")
    booking = db.get(Booking, payment.booking_id)
    if not booking or booking.user_id != current_user.id: raise HTTPException(404, "Payment not found")
    if payment.status != "SUCCESS": raise HTTPException(409, "Only successful payments can be refunded")
    payment.status = "REFUNDED"; db.commit(); db.refresh(payment)
    return payment
