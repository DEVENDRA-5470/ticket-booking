from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.event import Event
from app.models.seat import Seat
from app.models.user import User

router = APIRouter()

@router.post("/event/{event_id}/generate", status_code=status.HTTP_201_CREATED)
def generate_seats(event_id: int, count: int = Query(50, ge=1, le=500), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    event = db.get(Event, event_id)
    if not event: raise HTTPException(404, "Event not found")
    existing = db.execute(select(Seat.seat_number).where(Seat.event_id == event_id)).scalars().all()
    existing_set = set(existing)
    created = []
    for i in range(1, count + 1):
        number = f"S{i:03d}"
        if number not in existing_set:
            created.append(Seat(event_id=event_id, seat_number=number, status="AVAILABLE"))
    db.add_all(created); db.commit()
    return {"event_id": event_id, "created": len(created), "total_requested": count}

@router.get("/event/{event_id}")
def list_seats(event_id: int, db: Session = Depends(get_db)):
    if not db.get(Event, event_id): raise HTTPException(404, "Event not found")
    return db.execute(select(Seat).where(Seat.event_id == event_id).order_by(Seat.id)).scalars().all()
