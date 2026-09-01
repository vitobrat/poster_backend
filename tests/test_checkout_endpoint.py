import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI

from src.application.checkout.dto import (
    CheckoutResult,
    PaymentQuote,
    ProtectionQuote,
    ReservedSeat,
)
from src.application.checkout.service import CheckoutService
from src.domain.checkout.exceptions import SeatsUnavailableError
from src.presentation.checkout.router import router
from src.presentation.exceptions import setup_domain_exception_errors


class _CheckoutServiceProvider(Provider):
    def __init__(self, checkout_service: CheckoutService) -> None:
        super().__init__()
        self._checkout_service = checkout_service

    @provide(scope=Scope.REQUEST)
    def get_checkout_service(self) -> CheckoutService:
        return self._checkout_service


class CheckoutEndpointTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._checkout_service = AsyncMock(spec=CheckoutService)
        self._container = make_async_container(
            _CheckoutServiceProvider(self._checkout_service),
            FastapiProvider(),
        )
        app = FastAPI()
        app.include_router(router)
        setup_domain_exception_errors(app)
        setup_dishka(container=self._container, app=app)
        self._transport = httpx.ASGITransport(app=app)

    async def asyncTearDown(self) -> None:
        await self._transport.aclose()
        await self._container.close()

    async def test_successful_checkout_returns_price_and_protection(self) -> None:
        current_time = datetime.now(UTC)
        self._checkout_service.checkout_event_for_booking_use_case.return_value = CheckoutResult(
            booking_id=42,
            reserved_until=current_time + timedelta(minutes=15),
            base_amount=10_000,
            payment=PaymentQuote(
                commission=300,
                total=10_300,
                payment_methods=["bank_card", "sbp"],
                expires_at=current_time + timedelta(minutes=10),
            ),
            protection=ProtectionQuote(
                available=True,
                price=700,
                covered_amount=10_000,
                description="Full refund",
            ),
            event_title="Concert",
            starts_at=current_time + timedelta(days=1),
            seats=(ReservedSeat(seat_id=7, price=10_000),),
        )

        response = await self._post_checkout()

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data["booking"]["id"], 42)
        self.assertEqual(response_data["booking"]["base_amount"], 10_000)
        self.assertEqual(response_data["payment"]["total"], 10_300)
        self.assertEqual(response_data["protection"]["price"], 700)
        self._checkout_service.checkout_event_for_booking_use_case.assert_awaited_once_with(
            event_id=11,
            user_id=101,
            seat_ids=[7],
        )

    async def test_unavailable_seat_returns_http_409(self) -> None:
        self._checkout_service.checkout_event_for_booking_use_case.side_effect = SeatsUnavailableError()

        response = await self._post_checkout()

        self.assertEqual(response.status_code, 409)
        self.assertIn("detail", response.json())

    async def _post_checkout(self) -> httpx.Response:
        async with httpx.AsyncClient(
            transport=self._transport,
            base_url="http://test",
        ) as client:
            return await client.post(
                "/events/11/checkout",
                headers={"X-User-Id": "101"},
                json={"seat_ids": [7]},
            )
