from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import engine
from src.models import Event, EventSeat, Location, Seat

NUM_SEAT_ROWS = 5
NUM_SEATS_PER_ROW = 10
SEAT_POSITION_STEP = 50
EVENT_DAYS_AHEAD = 30
EVENT_BASE_PRICE = 5000


async def add_event_data_to_db() -> None:  # noqa: WPS213
    async with AsyncSession(engine, expire_on_commit=False) as db:
        async with db.begin():
            if await db.scalar(select(func.count(Location.id))):
                print("Тестовые данные уже существуют")
                return

            location = Location(
                name="Центральный зал",
                city="Москва",
                address="Тверская улица, 1",
            )
            db.add(location)
            await db.flush()

            seats = []
            for row in range(1, NUM_SEAT_ROWS + 1):
                for number in range(1, NUM_SEATS_PER_ROW + 1):
                    seats.append(
                        Seat(
                            location_id=location.id,
                            sector="Основной сектор",
                            row=row,
                            number=number,
                            x=number * SEAT_POSITION_STEP,
                            y=row * SEAT_POSITION_STEP,
                        ),
                    )
            db.add_all(seats)
            await db.flush()

            event = Event(
                organizer_id=1,
                location_id=location.id,
                title="Python Конференция",
                description="Тестовое мероприятие для домашнего задания",
                category="конференция",
                starts_at=datetime.now() + timedelta(days=EVENT_DAYS_AHEAD),
                base_price=EVENT_BASE_PRICE,
            )
            db.add(event)
            await db.flush()

            event_seats = [
                EventSeat(
                    event_id=event.id,
                    seat_id=seat.id,
                    price=event.base_price,
                )
                for seat in seats
            ]
            db.add_all(event_seats)

    print("Тестовые данные созданы")


if __name__ == "__main__":
    import asyncio

    asyncio.run(add_event_data_to_db())
