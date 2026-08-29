import asyncio
import random
from typing import TypedDict, Unpack

import httpx

from src.configs.consts import (
    DEFAULT_MAX_HTTP_RETRY_ATTEMPTS,
    DEFAULT_RATE_LIMITER_JITTER_IN_SECONDS,
    INITIAL_RETRY_BACKOFF_IN_SECONDS,
    MAX_RETRY_JITTER_IN_SECONDS,
    MIN_RETRY_JITTER_IN_SECONDS,
)
from src.infrastructure.api_connectors.exceptions import HTTPConnectionError
from src.infrastructure.api_connectors.schemas import HttpRateLimit


class _RequestOptions(TypedDict, total=False):
    json: object


class BaseHTTPConnector:
    def __init__(
        self,
        base_url: str,
        timeout: float,
        headers: dict[str, str] | None = None,
        rate_limit_config: HttpRateLimit | None = None,
        max_retry_attempts: int = DEFAULT_MAX_HTTP_RETRY_ATTEMPTS,
    ) -> None:
        self._api_client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers=headers,
        )

        self._rate_limiter: asyncio.Semaphore | None = None
        self._rate_limit_interval_in_seconds: float = 0
        if isinstance(rate_limit_config, HttpRateLimit):
            self._rate_limiter = asyncio.Semaphore(
                rate_limit_config.rate_limit_requests_count,
            )
            self._rate_limit_interval_in_seconds = rate_limit_config.rate_limit_interval_in_seconds

        self._max_retry_attempts = max_retry_attempts

    async def aclose_client(self) -> None:
        await self._api_client.aclose()

    async def _request(
        self,
        method: str,
        url: str,
        retry: bool = False,
        **request_options: Unpack[_RequestOptions],
    ) -> httpx.Response:
        max_retry_attempts = self._max_retry_attempts if retry else 1

        for attempt in range(max_retry_attempts):
            await self._wait_for_rate_limit()
            http_response = await self._request_attempt(
                method=method,
                url=url,
                attempt=attempt,
                max_retry_attempts=max_retry_attempts,
                **request_options,
            )
            if http_response is not None:
                return http_response

        raise HTTPConnectionError("HTTP request did not produce a response")

    async def _request_attempt(
        self,
        method: str,
        url: str,
        attempt: int,
        max_retry_attempts: int,
        **request_options: Unpack[_RequestOptions],
    ) -> httpx.Response | None:
        try:
            http_response = await self._api_client.request(
                method,
                url,
                **request_options,
            )
        except (httpx.NetworkError, httpx.TimeoutException) as http_exception:
            if attempt >= max_retry_attempts - 1:
                raise HTTPConnectionError(
                    "HTTP request failed after all retry attempts",
                ) from http_exception
            await self._exponentially_backoff(attempt)
            return None

        if http_response.status_code in (429, 503, 504) and attempt < max_retry_attempts - 1:
            await self._exponentially_backoff(attempt)
            return None

        return http_response

    async def _wait_for_rate_limit(self) -> None:
        rate_limiter = self._rate_limiter
        if rate_limiter is None:
            return

        await rate_limiter.acquire()
        asyncio.create_task(self._release_rate_limiter(rate_limiter))

    async def _exponentially_backoff(self, attempt: int) -> None:
        uniform_jitter = random.uniform(
            MIN_RETRY_JITTER_IN_SECONDS,
            MAX_RETRY_JITTER_IN_SECONDS,
        )
        backoff_time = INITIAL_RETRY_BACKOFF_IN_SECONDS * (2 ** (attempt + 1)) + uniform_jitter
        await asyncio.sleep(backoff_time)

    async def _release_rate_limiter(
        self,
        rate_limiter: asyncio.Semaphore,
    ) -> None:
        await asyncio.sleep(
            self._rate_limit_interval_in_seconds + DEFAULT_RATE_LIMITER_JITTER_IN_SECONDS,
        )
        rate_limiter.release()
