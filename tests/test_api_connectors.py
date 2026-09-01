import asyncio
import json
import unittest
from collections.abc import Callable
from datetime import UTC, datetime
from unittest.mock import AsyncMock, call, patch

import httpx
from pydantic import ValidationError

from src.infrastructure.api_connectors.base import BaseHTTPConnector
from src.infrastructure.api_connectors.exceptions import HTTPConnectionError
from src.infrastructure.api_connectors.external.payment_service.client import (
    PaymentAPIHTTPConnector,
)
from src.infrastructure.api_connectors.external.payment_service.dto import (
    PaymentCalculationRequestPayload,
)
from src.infrastructure.api_connectors.external.payment_service.exceptions import (
    PaymentExternalAPIError,
)
from src.infrastructure.api_connectors.external.protection_service.client import (
    ProtectionAPIHTTPConnector,
)
from src.infrastructure.api_connectors.external.protection_service.dto import (
    ProtectionCalculationRequestPayload,
)
from src.infrastructure.api_connectors.external.protection_service.exceptions import (
    ProtectionExternalAPIError,
)
from src.infrastructure.api_connectors.schemas import HttpRateLimit

RequestHandler = Callable[[httpx.Request], httpx.Response]


class APIConnectorTests(unittest.IsolatedAsyncioTestCase):
    def _build_payment_connector(
        self,
        handler: RequestHandler,
        *,
        max_retry_attempts: int = 3,
    ) -> PaymentAPIHTTPConnector:
        api_client = httpx.AsyncClient(
            base_url="https://payment.test",
            transport=httpx.MockTransport(handler),
        )
        with patch(
            "src.infrastructure.api_connectors.base.httpx.AsyncClient",
            return_value=api_client,
        ):
            connector = PaymentAPIHTTPConnector(
                base_url="https://payment.test",
                timeout=1.0,
                max_retry_attempts=max_retry_attempts,
            )

        connector._rate_limiter = None
        self.addAsyncCleanup(connector.aclose_client)
        return connector

    def _build_protection_connector(
        self,
        handler: RequestHandler,
        *,
        max_retry_attempts: int = 3,
    ) -> ProtectionAPIHTTPConnector:
        api_client = httpx.AsyncClient(
            base_url="https://protection.test",
            transport=httpx.MockTransport(handler),
        )
        with patch(
            "src.infrastructure.api_connectors.base.httpx.AsyncClient",
            return_value=api_client,
        ):
            connector = ProtectionAPIHTTPConnector(
                base_url="https://protection.test",
                timeout=1.0,
                max_retry_attempts=max_retry_attempts,
            )

        connector._rate_limiter = None
        self.addAsyncCleanup(connector.aclose_client)
        return connector

    @staticmethod
    def _payment_response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            request=request,
            json={
                "commission": 300,
                "total": 10_300,
                "payment_methods": ["bank_card", "sbp"],
                "expires_at": "2026-08-24T12:05:00+00:00",
            },
        )

    async def test_payment_calculate_serializes_request_and_validates_response(
        self,
    ) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return self._payment_response(request)

        connector = self._build_payment_connector(handler)

        result = await connector.payment_calculate(
            PaymentCalculationRequestPayload(
                booking_id=42,
                amount=10_000,
                currency="RUB",
            ),
        )

        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].method, "POST")
        self.assertEqual(requests[0].url.path, "/payment/calculate")
        self.assertEqual(
            json.loads(requests[0].content),
            {"booking_id": 42, "amount": 10_000, "currency": "RUB"},
        )
        self.assertEqual(result.commission, 300)
        self.assertEqual(result.total, 10_300)
        self.assertEqual(result.expires_at, datetime(2026, 8, 24, 12, 5, tzinfo=UTC))

    async def test_payment_retries_429_and_returns_successful_response(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if len(requests) == 1:
                return httpx.Response(status_code=429, request=request)
            return self._payment_response(request)

        connector = self._build_payment_connector(handler)
        connector._exponentially_backoff = AsyncMock()

        result = await connector.payment_calculate(
            PaymentCalculationRequestPayload(
                booking_id=42,
                amount=10_000,
                currency="RUB",
            ),
        )

        self.assertEqual(result.total, 10_300)
        self.assertEqual(len(requests), 2)
        self.assertEqual(connector._exponentially_backoff.await_args_list, [call(0)])

    async def test_payment_wraps_final_http_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=400, request=request)

        connector = self._build_payment_connector(handler)

        with self.assertRaises(PaymentExternalAPIError) as error_context:
            await connector.payment_calculate(
                PaymentCalculationRequestPayload(
                    booking_id=42,
                    amount=10_000,
                    currency="RUB",
                ),
            )

        self.assertIsInstance(error_context.exception.__cause__, httpx.HTTPStatusError)

    async def test_payment_wraps_invalid_json_response(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=200,
                request=request,
                content=b"not-json",
                headers={"content-type": "application/json"},
            )

        connector = self._build_payment_connector(handler)

        with self.assertRaises(PaymentExternalAPIError) as error_context:
            await connector.payment_calculate(
                PaymentCalculationRequestPayload(
                    booking_id=42,
                    amount=10_000,
                    currency="RUB",
                ),
            )

        self.assertIsInstance(
            error_context.exception.__cause__,
            json.JSONDecodeError,
        )

    async def test_payment_wraps_response_schema_validation_error(
        self,
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=200,
                request=request,
                json={
                    "commission": "invalid",
                    "total": 10_300,
                    "payment_methods": ["bank_card"],
                    "expires_at": None,
                },
            )

        connector = self._build_payment_connector(handler)

        with self.assertRaises(PaymentExternalAPIError) as error_context:
            await connector.payment_calculate(
                PaymentCalculationRequestPayload(
                    booking_id=42,
                    amount=10_000,
                    currency="RUB",
                ),
            )

        self.assertIsInstance(
            error_context.exception.__cause__,
            ValidationError,
        )

    async def test_payment_retries_transport_error_and_returns_success(self) -> None:
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise httpx.ConnectError("connection failed", request=request)
            return self._payment_response(request)

        connector = self._build_payment_connector(handler)
        connector._exponentially_backoff = AsyncMock()

        result = await connector.payment_calculate(
            PaymentCalculationRequestPayload(
                booking_id=42,
                amount=10_000,
                currency="RUB",
            ),
        )

        self.assertEqual(result.total, 10_300)
        self.assertEqual(attempts, 2)
        self.assertEqual(connector._exponentially_backoff.await_args_list, [call(0)])

    async def test_payment_wraps_exhausted_transport_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection failed", request=request)

        connector = self._build_payment_connector(handler, max_retry_attempts=2)
        connector._exponentially_backoff = AsyncMock()

        with self.assertRaises(HTTPConnectionError) as error_context:
            await connector.payment_calculate(
                PaymentCalculationRequestPayload(
                    booking_id=42,
                    amount=10_000,
                    currency="RUB",
                ),
            )

        self.assertIsInstance(error_context.exception.__cause__, httpx.ConnectError)

    async def test_protection_calculate_serializes_datetime_and_validates_response(
        self,
    ) -> None:
        requests: list[httpx.Request] = []
        event_starts_at = datetime(2026, 8, 25, 15, 30, tzinfo=UTC)

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                status_code=200,
                request=request,
                json={
                    "available": True,
                    "price": 700,
                    "covered_amount": 10_000,
                    "description": "Полный возврат",
                },
            )

        connector = self._build_protection_connector(handler)

        result = await connector.protection_calculate(
            ProtectionCalculationRequestPayload(
                booking_id=42,
                ticket_amount=10_000,
                event_category="concert",
                event_starts_at=event_starts_at,
            ),
        )

        request_data = json.loads(requests[0].content)
        serialized_starts_at = datetime.fromisoformat(
            request_data["event_starts_at"].replace("Z", "+00:00"),
        )
        self.assertEqual(serialized_starts_at, event_starts_at)
        self.assertTrue(result.available)
        self.assertEqual(result.price, 700)

    async def test_protection_retries_503_and_returns_successful_response(self) -> None:
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return httpx.Response(status_code=503, request=request)
            return httpx.Response(
                status_code=200,
                request=request,
                json={
                    "available": False,
                    "price": 0,
                    "covered_amount": 0,
                    "description": None,
                },
            )

        connector = self._build_protection_connector(handler)
        connector._exponentially_backoff = AsyncMock()

        result = await connector.protection_calculate(
            ProtectionCalculationRequestPayload(
                booking_id=42,
                ticket_amount=10_000,
                event_category="charity",
                event_starts_at=datetime(2026, 8, 25, 15, 30, tzinfo=UTC),
            ),
        )

        self.assertFalse(result.available)
        self.assertEqual(attempts, 2)
        self.assertEqual(connector._exponentially_backoff.await_args_list, [call(0)])

    async def test_protection_wraps_final_http_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=500, request=request)

        connector = self._build_protection_connector(handler)

        with self.assertRaises(ProtectionExternalAPIError) as error_context:
            await connector.protection_calculate(
                ProtectionCalculationRequestPayload(
                    booking_id=42,
                    ticket_amount=10_000,
                    event_category="concert",
                    event_starts_at=datetime(2026, 8, 25, 15, 30, tzinfo=UTC),
                ),
            )

        self.assertIsInstance(error_context.exception.__cause__, httpx.HTTPStatusError)

    async def test_protection_wraps_response_schema_validation_error(
        self,
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=200,
                request=request,
                json={
                    "available": True,
                    "price": "invalid",
                    "covered_amount": 10_000,
                    "description": "Full refund",
                },
            )

        connector = self._build_protection_connector(handler)

        with self.assertRaises(ProtectionExternalAPIError) as error_context:
            await connector.protection_calculate(
                ProtectionCalculationRequestPayload(
                    booking_id=42,
                    ticket_amount=10_000,
                    event_category="concert",
                    event_starts_at=datetime(
                        2026,
                        8,
                        25,
                        15,
                        30,
                        tzinfo=UTC,
                    ),
                ),
            )

        self.assertIsInstance(
            error_context.exception.__cause__,
            ValidationError,
        )

    async def test_protection_wraps_exhausted_transport_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("read timed out", request=request)

        connector = self._build_protection_connector(handler, max_retry_attempts=2)
        connector._exponentially_backoff = AsyncMock()

        with self.assertRaises(HTTPConnectionError) as error_context:
            await connector.protection_calculate(
                ProtectionCalculationRequestPayload(
                    booking_id=42,
                    ticket_amount=10_000,
                    event_category="concert",
                    event_starts_at=datetime(2026, 8, 25, 15, 30, tzinfo=UTC),
                ),
            )

        self.assertIsInstance(error_context.exception.__cause__, httpx.ReadTimeout)

    async def test_base_connector_allows_omitting_rate_limiter(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=204, request=request)

        api_client = httpx.AsyncClient(
            base_url="https://external.test",
            transport=httpx.MockTransport(handler),
        )
        with patch(
            "src.infrastructure.api_connectors.base.httpx.AsyncClient",
            return_value=api_client,
        ):
            connector = BaseHTTPConnector(
                base_url="https://external.test",
                timeout=1.0,
            )

        self.addAsyncCleanup(connector.aclose_client)

        response = await connector._request("GET", "/health")

        self.assertEqual(response.status_code, 204)

    async def test_rate_limiter_blocks_request_over_configured_quota(self) -> None:
        connector = BaseHTTPConnector(
            base_url="https://external.test",
            timeout=1.0,
            rate_limit_config=HttpRateLimit(
                rate_limit_requests_count=2,
                rate_limit_interval_in_seconds=60,
            ),
        )
        self.addAsyncCleanup(connector.aclose_client)
        connector._api_client.request = AsyncMock(
            return_value=httpx.Response(status_code=204),
        )
        release_permits = asyncio.Event()

        async def controlled_release(rate_limiter: asyncio.Semaphore) -> None:
            await release_permits.wait()
            rate_limiter.release()

        with patch.object(
            connector,
            "_release_rate_limiter",
            new=controlled_release,
        ):
            requests = [asyncio.create_task(connector._request("GET", "/health")) for _ in range(3)]
            await self._wait_for_await_count(
                connector._api_client.request,
                expected_count=2,
            )

            self.assertEqual(connector._api_client.request.await_count, 2)
            self.assertFalse(requests[2].done())

            release_permits.set()
            responses = await asyncio.wait_for(
                asyncio.gather(*requests),
                timeout=1,
            )

        self.assertEqual(connector._api_client.request.await_count, 3)
        self.assertEqual(
            [response.status_code for response in responses],
            [204, 204, 204],
        )

    async def _wait_for_await_count(
        self,
        async_mock: AsyncMock,
        expected_count: int,
    ) -> None:
        for _ in range(100):
            if async_mock.await_count == expected_count:
                return
            await asyncio.sleep(0)
        self.fail(
            "Requests did not acquire the expected rate-limit permits",
        )

    async def test_aclose_client_closes_connection_pool(self) -> None:
        connector = self._build_payment_connector(self._payment_response)

        self.assertFalse(connector._api_client.is_closed)

        await connector.aclose_client()

        self.assertTrue(connector._api_client.is_closed)
