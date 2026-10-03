from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.booking import Booking, BookingSeat
from app.models.event import Event
from app.models.seat import Seat
from app.models.user import User

router = APIRouter()

class BookingRequest(BaseModel):
    event_id: int
    seat_ids: list[int]

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_booking(payload: BookingRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    event = db.get(Event, payload.event_id)
    if not event or event.status in ("CANCELLED", "COMPLETED"):
        raise HTTPException(400, "Event is not bookable")
    ids = list(dict.fromkeys(payload.seat_ids))
    seats = db.execute(select(Seat).where(Seat.id.in_(ids), Seat.event_id == payload.event_id).with_for_update()).scalars().all()
    if len(seats) != len(ids): raise HTTPException(400, "Invalid seat selection")
    unavailable = [s.seat_number for s in seats if s.status != "AVAILABLE"]
    if unavailable: raise HTTPException(409, "One or more seats are unavailable")
    booking = Booking(reference="TKT-" + uuid4().hex[:10].upper(), user_id=current_user.id, event_id=event.id, status="CONFIRMED")
    db.add(booking); db.flush()
    for seat in seats:
        seat.status = "BOOKED"
        db.add(BookingSeat(booking_id=booking.id, seat_id=seat.id))
    db.commit(); db.refresh(booking)
    return {"id": booking.id, "reference": booking.reference, "event_id": event.id, "seat_ids": ids, "status": booking.status}

@router.get("/")
def my_bookings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.execute(select(Booking).where(Booking.user_id == current_user.id).order_by(Booking.created_at.desc())).scalars().all()
