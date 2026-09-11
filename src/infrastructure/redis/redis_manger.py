from redis.asyncio import Redis


class RedisManager:
    def __init__(self, redis: Redis[str]) -> None:
        self.client = redis

    async def aclose(self) -> None:
        await self.client.aclose()  # type: ignore[attr-defined]
