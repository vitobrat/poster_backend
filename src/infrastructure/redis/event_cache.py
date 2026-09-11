from src.application.event.dto import EventData
from src.configs.consts import DEFAULT_EVENT_CACHE_TTL_SEC
from src.infrastructure.cache.ttl import get_int_jitter
from src.infrastructure.redis.redis_manger import RedisManager


class EventCache:
    """Кэш для хранения информации о мероприятиях."""

    def __init__(self, redis_manager: RedisManager) -> None:
        self._client = redis_manager.client

    async def get_event(self, event_id: int) -> EventData | None:
        """Возвращает данные мероприятия из кэша."""
        event_data_value = await self._client.get(self._get_event_key(event_id))

        if event_data_value is None:
            return None

        return EventData.model_validate_json(event_data_value)

    async def set_event(self, event_id: int, event_data: EventData, ttl: int = DEFAULT_EVENT_CACHE_TTL_SEC) -> None:
        """Сохраняет данные мероприятия в кэш."""

        int_jitter = get_int_jitter()

        await self._client.set(
            name=self._get_event_key(event_id),
            value=event_data.model_dump_json(),
            ex=ttl + int_jitter,
        )

    def _get_event_key(self, event_id: int) -> str:
        """Возвращает ключ для хранения данных мероприятия в кэше."""

        return f"event:{event_id}"
