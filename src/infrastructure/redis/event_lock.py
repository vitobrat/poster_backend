from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from redis.asyncio.lock import Lock

from src.configs.consts import (
    DEFAULT_LOCK_BLOCKING_WAITING_TIMEOUT_SEC,
    DEFAULT_LOCK_TIMEOUT_SEC,
)
from src.infrastructure.redis.redis_manger import RedisManager


class EventLock:
    """Механизм блокировки для операций с мероприятиями."""

    def __init__(self, redis_manager: RedisManager) -> None:
        self._client = redis_manager.client

    @asynccontextmanager
    async def lock_event(
        self,
        event_id: int,
        timeout_lock: int = DEFAULT_LOCK_TIMEOUT_SEC,
        blocking_timeout: int = DEFAULT_LOCK_BLOCKING_WAITING_TIMEOUT_SEC,
    ) -> AsyncIterator[Lock]:
        async with self._client.lock(
            name=self._get_lock_key(event_id),
            timeout=timeout_lock,
            blocking_timeout=blocking_timeout,
        ) as event_lock:
            yield event_lock

    def _get_lock_key(self, event_id: int) -> str:
        """Возвращает ключ для блокировки мероприятия в Redis."""

        return f"locks:get_event:{event_id}"
