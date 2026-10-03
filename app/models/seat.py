from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

class Seat(Base):
    __tablename__ = "seats"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    seat_number: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="AVAILABLE")
