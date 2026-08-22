from contextlib import AbstractAsyncContextManager
from typing import Protocol

from src.infrastructure.database.db_manager import DatabaseManager


class DatabaseClient(Protocol):
    def transaction(
        self,
    ) -> AbstractAsyncContextManager[DatabaseManager]: ...

    async def close(self) -> None: ...
