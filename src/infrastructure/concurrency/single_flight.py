import asyncio
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar, cast

OperationParams = ParamSpec("OperationParams")
OperationResult = TypeVar("OperationResult")


class SingleFlight:

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[object]] = {}

    async def run(
        self,
        key: str,
        operation: Callable[OperationParams, Awaitable[OperationResult]],
        *args: OperationParams.args,
        **kwargs: OperationParams.kwargs,
    ) -> OperationResult:
        existing_task = self._tasks.get(key)
        if existing_task is None:
            task = asyncio.create_task(
                self._execute_operation(key, operation, *args, **kwargs),
            )
            self._tasks[key] = task
        else:
            task = cast("asyncio.Task[OperationResult]", existing_task)

        return await asyncio.shield(task)

    async def _execute_operation(
        self,
        key: str,
        operation: Callable[OperationParams, Awaitable[OperationResult]],
        *args: OperationParams.args,
        **kwargs: OperationParams.kwargs,
    ) -> OperationResult:
        try:  # noqa: WPS501
            return await operation(*args, **kwargs)
        finally:
            self._tasks.pop(key, None)
