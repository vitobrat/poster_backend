import redis

from src.application.event.dto import EventData
from src.application.event.exceptions import (
    EventLockTimeoutError,
    ReadEventError,
)
from src.domain.event.exceptions import EventDataNotFoundError
from src.infrastructure.concurrency.single_flight import SingleFlight
from src.infrastructure.database.base_client import DatabaseClient
from src.infrastructure.redis.event_cache import EventCache
from src.infrastructure.redis.event_lock import EventLock


class ObtainEventService:
    def __init__(
        self,
        db_client: DatabaseClient,
        single_flight: SingleFlight,
        event_cache_manager: EventCache,
        event_lock_manager: EventLock,
    ) -> None:
        self._db_client = db_client
        self._single_flight = single_flight
        self._event_cache_manager = event_cache_manager
        self._event_lock_manager = event_lock_manager

    async def exec(self, event_id: int) -> EventData:
        """Возвращает полное описание мероприятия."""
        event_cache_result = await self._event_cache_manager.get_event(event_id)

        if event_cache_result is not None:
            return event_cache_result

        try:
            event_data: EventData = await self._single_flight.run(
                key=f"event:{event_id}",
                operation=self._exec_flight_task,
                event_id=event_id,
            )
        except redis.exceptions.LockError as redis_lock_exception:
            raise EventLockTimeoutError from redis_lock_exception

        return event_data

    async def _exec_flight_task(self, event_id: int) -> EventData:
        async with self._event_lock_manager.lock_event(
            event_id=event_id,
        ):
            event_cache_result = await self._event_cache_manager.get_event(event_id)

            if event_cache_result is not None:
                return event_cache_result

            try:
                async with self._db_client.transaction() as db_manager:
                    event_data_orm = await db_manager.event_repo.get_by_id(event_id)
            except Exception as db_error:
                raise ReadEventError from db_error

            if event_data_orm is None:
                raise EventDataNotFoundError

            event_data = EventData.model_validate(event_data_orm, from_attributes=True)
            await self._event_cache_manager.set_event(
                event_id=event_id,
                event_data=event_data,
            )

            return event_data
