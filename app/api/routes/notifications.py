from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.notification import Notification
from app.models.user import User

router = APIRouter()

@router.get("/")
def list_notifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.execute(select(Notification).where(Notification.user_id == current_user.id).order_by(Notification.id.desc())).scalars().all()

@router.post("/{notification_id}/read")
def mark_read(notification_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.get(Notification, notification_id)
    if not item or item.user_id != current_user.id: raise HTTPException(404, "Notification not found")
    item.status = "READ"; db.commit(); db.refresh(item)
    return item
