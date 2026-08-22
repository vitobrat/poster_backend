from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.repository.booking import BookingRepo
from src.infrastructure.database.repository.event_seats import EventSeatRepo


class DatabaseManager:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        return self._session

    @property
    def event_seats_repo(self) -> EventSeatRepo:
        return EventSeatRepo(self._session)

    @property
    def booking_repo(self) -> BookingRepo:
        return BookingRepo(self._session)
