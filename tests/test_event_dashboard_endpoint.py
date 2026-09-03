import unittest
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import httpx
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI

from src.application.event.dto import EventAnalyticsResult
from src.application.event.exceptions import EventServiceError
from src.application.event.service import EventService
from src.domain.event.exceptions import EventAnalyticsNotFoundError
from src.presentation.events.router import router
from src.presentation.exceptions import (
    setup_application_exception_errors,
    setup_domain_exception_errors,
)


class _EventServiceProvider(Provider):
    def __init__(self, event_service: EventService) -> None:
        super().__init__()
        self._event_service = event_service

    @provide(scope=Scope.REQUEST)
    def get_event_service(self) -> EventService:
        return self._event_service


class EventDashboardEndpointTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._event_service = AsyncMock(spec=EventService)
        self._container = make_async_container(
            _EventServiceProvider(self._event_service),
            FastapiProvider(),
        )
        app = FastAPI()
        app.include_router(router)
        setup_domain_exception_errors(app)
        setup_application_exception_errors(app)
        setup_dishka(container=self._container, app=app)
        self._transport = httpx.ASGITransport(
            app=app,
            raise_app_exceptions=False,
        )

    async def asyncTearDown(self) -> None:
        await self._transport.aclose()
        await self._container.close()

    async def test_dashboard_returns_sales_and_occupancy_response(self) -> None:
        self._event_service.get_event_analytics_data.return_value = EventAnalyticsResult(
            event_title="Concert",
            starts_at=datetime.now(UTC),
            sales_paid_orders=2,
            sales_sold_tickets=3,
            sales_revenue=4_000,
            sales_average_order=Decimal("2000.5"),
            occupancy_total=6,
            occupancy_available=2,
            occupancy_sold=3,
        )

        response = await self._get_dashboard(event_id=11, organizer_id=101)

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data["event_title"], "Concert")
        self.assertEqual(
            response_data["sales"],
            {
                "paid_orders": 2,
                "sold_tickets": 3,
                "revenue": 4_000,
                "average_order": 2_000.5,
            },
        )
        self.assertEqual(response_data["occupancy"]["total"], 6)
        self.assertEqual(response_data["occupancy"]["available"], 2)
        self.assertEqual(response_data["occupancy"]["reserved"], 1)
        self.assertEqual(response_data["occupancy"]["sold"], 3)
        self.assertAlmostEqual(
            response_data["occupancy"]["occupancy_percent"],
            4 / 6 * 100,
        )
        self._event_service.get_event_analytics_data.assert_awaited_once_with(
            event_id=11,
            organizer_id=101,
        )

    async def test_foreign_or_missing_event_returns_http_404(self) -> None:
        self._event_service.get_event_analytics_data.side_effect = EventAnalyticsNotFoundError()

        for event_id in (11, -1):
            with self.subTest(event_id=event_id):
                response = await self._get_dashboard(
                    event_id=event_id,
                    organizer_id=202,
                )

                self.assertEqual(response.status_code, 404)
                self.assertIn("detail", response.json())

    async def test_database_failure_returns_controlled_http_500(self) -> None:
        database_error = RuntimeError("database password leaked")
        service_error = EventServiceError()
        service_error.__cause__ = database_error
        self._event_service.get_event_analytics_data.side_effect = service_error

        response = await self._get_dashboard(event_id=11, organizer_id=101)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {"detail": "Internal server error."},
        )
        self.assertNotIn("password", response.text)

    async def _get_dashboard(
        self,
        event_id: int,
        organizer_id: int,
    ) -> httpx.Response:
        async with httpx.AsyncClient(
            transport=self._transport,
            base_url="http://test",
        ) as client:
            return await client.get(
                f"/organizer/events/{event_id}/dashboard",
                headers={"X-User-Id": str(organizer_id)},
            )
