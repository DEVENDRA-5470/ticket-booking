#!/usr/bin/env python3
"""
TicketFlow database bootstrap and seed data.

Run inside the backend container:

    PYTHONPATH=/app python /app/scripts/create_table_seed_data.py

This script is idempotent:
- Existing events are not duplicated.
- Existing food items are not duplicated.
- Existing tables are left unchanged.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.db.base import Base
from app.db.session import SessionLocal, engine

from app.models.booking import Booking, BookingSeat
from app.models.event import Event
from app.models.food import FoodItem, FoodOrder, FoodOrderItem
from app.models.notification import Notification
from app.models.payment import Payment
from app.models.seat import Seat
from app.models.user import User


FOOD_ITEMS = [
    ("Veg Burger", Decimal("149.00")),
    ("Paneer Wrap", Decimal("179.00")),
    ("Veg Pizza", Decimal("249.00")),
    ("Margherita Pizza", Decimal("229.00")),
    ("Paneer Tikka", Decimal("199.00")),
    ("Veg Sandwich", Decimal("129.00")),
    ("French Fries", Decimal("99.00")),
    ("Masala Fries", Decimal("119.00")),
    ("Veg Momos", Decimal("139.00")),
    ("Cheese Nachos", Decimal("159.00")),
    ("Masala Maggi", Decimal("99.00")),
    ("Veg Pasta", Decimal("189.00")),
    ("Chole Kulche", Decimal("149.00")),
    ("Rajma Rice", Decimal("169.00")),
    ("Paneer Biryani", Decimal("219.00")),
    ("Veg Biryani", Decimal("189.00")),
    ("Cold Coffee", Decimal("119.00")),
    ("Fresh Lime Soda", Decimal("89.00")),
    ("Mango Juice", Decimal("99.00")),
    ("Chocolate Brownie", Decimal("129.00")),
]


EVENTS = [
    ("Rock Night Live", "Delhi Arena"),
    ("Comedy Night", "Phoenix Hall"),
    ("Tech Conference 2026", "India Expo Centre"),
    ("Startup Summit", "World Trade Centre"),
    ("Bollywood Music Night", "Jawaharlal Nehru Stadium"),
    ("Indie Music Festival", "NSIC Grounds"),
    ("Stand-Up Special", "Siri Fort Auditorium"),
    ("Business Leadership Summit", "Hotel Pullman"),
    ("AI & Cloud Expo", "Pragati Maidan"),
    ("Developer Conference", "Yashobhoomi"),
    ("EDM Night", "Noida Stadium"),
    ("Classical Music Evening", "Kamani Auditorium"),
    ("Food & Music Festival", "Major Dhyan Chand Stadium"),
    ("Gaming Expo", "India Expo Mart"),
    ("Cyber Security Summit", "Le Meridien"),
    ("Cloud Native India", "The Lalit"),
    ("Data Science Conference", "India Habitat Centre"),
    ("DevOps Days India", "Aerocity Convention Centre"),
    ("Open Source Summit", "NDMC Convention Centre"),
    ("New Year Music Festival", "Noida Exhibition Centre"),
]


def create_tables() -> None:
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables ready.")


def seed_events(db) -> None:
    print("Seeding events...")

    existing_names = set(
        db.execute(select(Event.name)).scalars().all()
    )

    created = 0
    skipped = 0
    now = datetime.now(timezone.utc)

    for index, (name, venue) in enumerate(EVENTS, start=1):
        if name in existing_names:
            skipped += 1
            continue

        event = Event(
            name=name,
            venue=venue,
            starts_at=now + timedelta(days=index * 3),
            capacity=100,
            status="PUBLISHED",
        )

        db.add(event)
        db.flush()

        db.add_all(
            [
                Seat(
                    event_id=event.id,
                    seat_number=f"S{i:03d}",
                    status="AVAILABLE",
                )
                for i in range(1, event.capacity + 1)
            ]
        )

        created += 1

    db.commit()

    print(f"Events seed complete: created={created}, skipped={skipped}")


def seed_food(db) -> None:
    print("Seeding food items...")

    existing_names = set(
        db.execute(select(FoodItem.name)).scalars().all()
    )

    created = 0
    skipped = 0

    for name, price in FOOD_ITEMS:
        if name in existing_names:
            skipped += 1
            continue

        db.add(
            FoodItem(
                name=name,
                price=price,
                available=True,
            )
        )
        created += 1

    db.commit()

    print(f"Food seed complete: created={created}, skipped={skipped}")


def main() -> None:
    print("=" * 60)
    print("TicketFlow Database Bootstrap")
    print("=" * 60)

    create_tables()

    db = SessionLocal()

    try:
        seed_events(db)
        seed_food(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print("=" * 60)
    print("Database bootstrap and seed completed successfully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
