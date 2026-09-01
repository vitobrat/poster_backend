from sqlalchemy import select

from src.infrastructure.database.models import Event
from src.infrastructure.database.repository.base import BaseRepo


class EventRepo(BaseRepo):

    async def get_by_id(self, event_id: int) -> Event | None:
        query = select(Event).where(Event.id == event_id)

        event_orm = await self.session.execute(query)
        event = event_orm.scalar_one_or_none()

        return event
