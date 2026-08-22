from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings
from src.infrastructure.database.base_client import DatabaseClient
from src.infrastructure.database.models import Event, EventSeat, Location, Seat
from src.infrastructure.postgres.client import PostgresClient

_NUM_SEAT_ROWS = 5
_NUM_SEATS_PER_ROW = 10
_SEAT_POSITION_STEP = 50
_EVENT_DAYS_AHEAD = 30
_EVENT_BASE_PRICE = 5000


async def add_event_data_to_db() -> None:  # noqa: WPS213
    database_client: DatabaseClient = PostgresClient(Settings().postgres)
    async with database_client.transaction() as db:
        session: AsyncSession = db.session

        if await session.scalar(select(func.count(Location.id))):
            print("Тестовые данные уже существуют")
            return

        location = Location(
            name="Центральный зал",
            city="Москва",
            address="Тверская улица, 1",
        )
        session.add(location)
        await session.flush()

        seats = []
        for row in range(1, _NUM_SEAT_ROWS + 1):
            for number in range(1, _NUM_SEATS_PER_ROW + 1):
                seats.append(
                    Seat(
                        location_id=location.id,
                        sector="Основной сектор",
                        row=row,
                        number=number,
                        x=number * _SEAT_POSITION_STEP,
                        y=row * _SEAT_POSITION_STEP,
                    ),
                )
        session.add_all(seats)
        await session.flush()

        event = Event(
            organizer_id=1,
            location_id=location.id,
            title="Python Конференция",
            description="Тестовое мероприятие для домашнего задания",
            category="конференция",
            starts_at=datetime.now() + timedelta(days=_EVENT_DAYS_AHEAD),
            base_price=_EVENT_BASE_PRICE,
        )
        session.add(event)
        await session.flush()

        event_seats = [
            EventSeat(
                event_id=event.id,
                seat_id=seat.id,
                price=event.base_price,
            )
            for seat in seats
        ]
        session.add_all(event_seats)

    print("Тестовые данные созданы")


if __name__ == "__main__":
    import asyncio

    asyncio.run(add_event_data_to_db())
