from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.event import Event


router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_event(
    name: str,
    venue: str,
    starts_at: datetime,
    db: Session = Depends(get_db),
):
    event = Event(
        name=name,
        venue=venue,
        starts_at=starts_at,
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return event


@router.get("/")
def list_events(db: Session = Depends(get_db)):
    result = db.execute(
        select(Event).order_by(Event.starts_at)
    )

    return result.scalars().all()


@router.get("/{event_id}")
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    return event


@router.delete("/{event_id}")
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    db.delete(event)
    db.commit()

    return {
        "message": "Event deleted successfully",
        "event_id": event_id,
    }