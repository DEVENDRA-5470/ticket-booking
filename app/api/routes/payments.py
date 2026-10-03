from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.booking import Booking, BookingSeat
from app.models.food import FoodItem, FoodOrder, FoodOrderItem
from app.models.notification import Notification
from app.models.payment import Payment
from app.models.user import User
from app.services.email import send_notification_email

router = APIRouter()


def _calculate_amount(booking_id: int, db: Session) -> float:
    seat_count = db.execute(
        select(BookingSeat).where(BookingSeat.booking_id == booking_id)
    ).scalars().all()

    food_orders = db.execute(
        select(FoodOrder).where(
            FoodOrder.booking_id == booking_id,
            FoodOrder.status != "CANCELLED",
        )
    ).scalars().all()

    food_total = 0.0
    for order in food_orders:
        items = db.execute(
            select(FoodOrderItem).where(FoodOrderItem.food_order_id == order.id)
        ).scalars().all()

        for order_item in items:
            item = db.get(FoodItem, order_item.food_item_id)
            if item:
                food_total += float(item.price) * order_item.quantity

    return len(seat_count) * 500.0 + food_total


@router.post("/simulate/{booking_id}")
def simulate_payment(
    booking_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    booking = db.get(Booking, booking_id)
    if not booking or booking.user_id != current_user.id or booking.status != "CONFIRMED":
        raise HTTPException(404, "Booking not found")

    existing = db.execute(
        select(Payment).where(
            Payment.booking_id == booking.id,
            Payment.status == "SUCCESS",
        )
    ).scalar_one_or_none()

    if existing:
        return {"payment": existing, "message": "Payment already successful"}

    amount = _calculate_amount(booking.id, db)
    payment = Payment(
        booking_id=booking.id,
        amount=amount,
        status="SUCCESS",
        provider_reference=f"SIM-{uuid4().hex[:12].upper()}",
    )
    db.add(payment)

    message = f"Payment successful for booking {booking.reference}: ₹{amount:.2f}"
    db.add(Notification(
        user_id=current_user.id,
        channel="IN_APP",
        message=message,
        status="PENDING",
    ))
    db.commit()
    db.refresh(payment)

    background_tasks.add_task(
        send_notification_email,
        current_user.email,
        current_user.name,
        message,
        "Payment Successful",
    )

    return {"message": "Simulated payment successful", "payment": payment}


@router.post("/{booking_id}")
def create_payment(
    booking_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    booking = db.get(Booking, booking_id)
    if not booking or booking.user_id != current_user.id:
        raise HTTPException(404, "Booking not found")

    amount = _calculate_amount(booking.id, db)
    payment = Payment(
        booking_id=booking.id,
        amount=amount,
        status="PENDING",
        provider_reference=f"SIM-{uuid4().hex[:12].upper()}",
    )
    db.add(payment)
    db.flush()

    message = f"Payment #{payment.id} created for booking {booking.reference}: ₹{amount:.2f}"
    db.add(Notification(
        user_id=current_user.id,
        channel="IN_APP",
        message=message,
        status="PENDING",
    ))
    db.commit()
    db.refresh(payment)

    background_tasks.add_task(
        send_notification_email,
        current_user.email,
        current_user.name,
        message,
        "Payment Created",
    )

    return payment


@router.post("/{payment_id}/complete")
def complete_payment(
    payment_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "Payment not found")

    booking = db.get(Booking, payment.booking_id)
    if not booking or booking.user_id != current_user.id:
        raise HTTPException(404, "Payment not found")

    if payment.status == "REFUNDED":
        raise HTTPException(409, "Payment already refunded")

    payment.status = "SUCCESS"
    message = f"Payment #{payment.id} successful"
    db.add(Notification(
        user_id=current_user.id,
        channel="IN_APP",
        message=message,
        status="PENDING",
    ))
    db.commit()
    db.refresh(payment)

    background_tasks.add_task(
        send_notification_email,
        current_user.email,
        current_user.name,
        message,
        "Payment Successful",
    )

    return payment


@router.post("/{payment_id}/refund")
def refund_payment(
    payment_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "Payment not found")

    booking = db.get(Booking, payment.booking_id)
    if not booking or booking.user_id != current_user.id:
        raise HTTPException(404, "Payment not found")

    if payment.status not in ("SUCCESS", "REFUND_PENDING"):
        raise HTTPException(409, "Only successful or refund-pending payments can be refunded")

    payment.status = "REFUNDED"
    message = f"Payment #{payment.id} refunded"
    db.add(Notification(
        user_id=current_user.id,
        channel="IN_APP",
        message=message,
        status="PENDING",
    ))
    db.commit()
    db.refresh(payment)

    background_tasks.add_task(
        send_notification_email,
        current_user.email,
        current_user.name,
        message,
        "Payment Refunded",
    )

    return payment
