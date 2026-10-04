from uuid import uuid4
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.booking import Booking, BookingSeat
from app.models.event import Event
from app.models.seat import Seat
from app.models.user import User
from app.models.notification import Notification
from app.models.food import FoodOrder, FoodOrderItem, FoodItem
from app.models.payment import Payment
from app.services.email import send_booking_confirmation_email, send_notification_email

router = APIRouter()


class BookingRequest(BaseModel):
    event_id: int
    seat_ids: list[int]


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.get(Event, payload.event_id)
    if not event or event.status in ("CANCELLED", "COMPLETED"):
        raise HTTPException(400, "Event is not bookable")

    ids = list(dict.fromkeys(payload.seat_ids))
    if not ids:
        raise HTTPException(400, "At least one seat is required")

    seats = db.execute(
        select(Seat)
        .where(Seat.id.in_(ids), Seat.event_id == payload.event_id)
        .with_for_update()
    ).scalars().all()

    if len(seats) != len(ids):
        raise HTTPException(400, "Invalid seat selection")

    unavailable = [s.seat_number for s in seats if s.status != "AVAILABLE"]
    if unavailable:
        raise HTTPException(409, "One or more seats are unavailable")

    booking = Booking(
        reference="TKT-" + uuid4().hex[:10].upper(),
        user_id=current_user.id,
        event_id=event.id,
        status="CONFIRMED",
    )
    db.add(booking)
    db.flush()

    for seat in seats:
        seat.status = "BOOKED"
        db.add(BookingSeat(booking_id=booking.id, seat_id=seat.id))

    message = f"Booking {booking.reference} confirmed for {event.name}"
    db.add(Notification(
        user_id=current_user.id,
        channel="IN_APP",
        message=message,
        status="PENDING",
    ))
    db.commit()
    db.refresh(booking)

    background_tasks.add_task(
        send_booking_confirmation_email,
        current_user.email, current_user.name, booking.reference,
        event.name, event.venue, event.starts_at.isoformat(),
        [seat.seat_number for seat in seats], len(seats) * 500,
    )

    return {
        "id": booking.id,
        "reference": booking.reference,
        "event_id": event.id,
        "seat_ids": ids,
        "status": booking.status,
    }


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
def create_bulk_bookings(
    event_id: int,
    background_tasks: BackgroundTasks,
    count: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if count < 1 or count > 500:
        raise HTTPException(400, "count must be between 1 and 500")

    event = db.get(Event, event_id)
    if not event or event.status in ("CANCELLED", "COMPLETED"):
        raise HTTPException(400, "Event is not bookable")

    created = []
    for _ in range(count):
        seat = db.execute(
            select(Seat)
            .where(Seat.event_id == event_id, Seat.status == "AVAILABLE")
            .with_for_update()
            .limit(1)
        ).scalar_one_or_none()

        if not seat:
            break

        booking = Booking(
            reference="TKT-" + uuid4().hex[:10].upper(),
            user_id=current_user.id,
            event_id=event.id,
            status="CONFIRMED",
        )
        db.add(booking)
        db.flush()
        seat.status = "BOOKED"
        db.add(BookingSeat(booking_id=booking.id, seat_id=seat.id))

        db.add(Notification(
            user_id=current_user.id,
            channel="IN_APP",
            message=f"Booking {booking.reference} confirmed",
            status="PENDING",
        ))
        created.append({"id": booking.id, "reference": booking.reference, "seat_id": seat.id})

    db.commit()

    if created:
        message = (
            f"{len(created)} booking(s) confirmed for {event.name}. "
            f"References: {', '.join(item['reference'] for item in created[:10])}"
        )
        if len(created) > 10:
            message += f" and {len(created) - 10} more."

        background_tasks.add_task(
            send_notification_email,
            current_user.email,
            current_user.name,
            message,
            "Bulk Booking Confirmed",
        )

    return {
        "requested": count,
        "created": len(created),
        "failed": count - len(created),
        "bookings": created,
    }


@router.get("/orders")
def my_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bookings = db.execute(select(Booking).where(Booking.user_id == current_user.id).order_by(Booking.created_at.desc())).scalars().all()
    result = []
    for booking in bookings:
        event = db.get(Event, booking.event_id)
        seats = db.execute(select(Seat).join(BookingSeat, BookingSeat.seat_id == Seat.id).where(BookingSeat.booking_id == booking.id).order_by(Seat.seat_number)).scalars().all()
        payments = db.execute(select(Payment).where(Payment.booking_id == booking.id).order_by(Payment.id.desc())).scalars().all()
        food_orders = db.execute(select(FoodOrder).where(FoodOrder.booking_id == booking.id).order_by(FoodOrder.id.desc())).scalars().all()
        food = []
        for order in food_orders:
            items = db.execute(select(FoodOrderItem, FoodItem).join(FoodItem, FoodItem.id == FoodOrderItem.food_item_id).where(FoodOrderItem.food_order_id == order.id)).all()
            food.append({
                "order_id": order.id, "status": order.status,
                "items": [{"name": item.name, "quantity": row.quantity, "unit_price": float(item.price), "line_total": round(float(item.price) * row.quantity, 2)} for row, item in items],
                "total": round(sum(float(item.price) * row.quantity for row, item in items), 2),
            })
        result.append({
            "booking_id": booking.id, "reference": booking.reference, "status": booking.status,
            "created_at": booking.created_at.isoformat() if booking.created_at else None,
            "event": {"id": event.id, "name": event.name, "venue": event.venue, "starts_at": event.starts_at.isoformat(), "status": event.status} if event else None,
            "seats": [{"id": s.id, "number": s.seat_number, "status": s.status} for s in seats],
            "ticket_amount": round(len(seats) * 500, 2),
            "payments": [{"id": p.id, "amount": float(p.amount), "status": p.status, "provider_reference": p.provider_reference} for p in payments],
            "food_orders": food,
            "food_total": round(sum(x["total"] for x in food if x["status"] != "CANCELLED"), 2),
        })
    return result


@router.get("/")
def my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.execute(
        select(Booking)
        .where(Booking.user_id == current_user.id)
        .order_by(Booking.created_at.desc())
    ).scalars().all()
