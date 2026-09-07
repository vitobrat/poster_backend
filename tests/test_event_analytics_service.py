import asyncio
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType

from src.application.event.dto import (
    EventOccupancyAnalytics,
    EventSalesAnalytics,
)
from src.application.event.exceptions import EventServiceError
from src.application.event.obtain_analytics import (
    ObtainEventAnalyticsDataService,
)


class _ConcurrencyProbe:
    def __init__(self) -> None:
        self.sales_started = asyncio.Event()
        self.occupancy_started = asyncio.Event()
        self.transaction_tokens: list[object] = []
        self.active_transactions = 0
        self.max_active_transactions = 0
        self.exited_transactions = 0


class _AnalyticsRepositoryStub:
    def __init__(
        self,
        probe: _ConcurrencyProbe,
        sales_result: EventSalesAnalytics,
        occupancy_result: EventOccupancyAnalytics,
        fail_sales: bool,
    ) -> None:
        self._probe = probe
        self._sales_result = sales_result
        self._occupancy_result = occupancy_result
        self._fail_sales = fail_sales

    async def get_sales_analytics(
        self,
        event_id: int,
        organizer_id: int,
    ) -> EventSalesAnalytics:
        self._probe.sales_started.set()
        await asyncio.wait_for(
            self._probe.occupancy_started.wait(),
            timeout=0.5,
        )
        if self._fail_sales:
            raise RuntimeError("database connection lost")
        return self._sales_result

    async def get_occupancy_analytics(
        self,
        event_id: int,
        organizer_id: int,
    ) -> EventOccupancyAnalytics:
        self._probe.occupancy_started.set()
        await asyncio.wait_for(
            self._probe.sales_started.wait(),
            timeout=0.5,
        )
        return self._occupancy_result


class _DatabaseManagerStub:
    def __init__(self, repository: _AnalyticsRepositoryStub) -> None:
        self.event_analytics_repo = repository


class _TransactionStub:
    def __init__(
        self,
        probe: _ConcurrencyProbe,
        repository: _AnalyticsRepositoryStub,
    ) -> None:
        self._probe = probe
        self._manager = _DatabaseManagerStub(repository)
        self.session_token = object()

    async def __aenter__(self) -> _DatabaseManagerStub:
        self._probe.transaction_tokens.append(self.session_token)
        self._probe.active_transactions += 1
        self._probe.max_active_transactions = max(
            self._probe.max_active_transactions,
            self._probe.active_transactions,
        )
        return self._manager

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._probe.active_transactions -= 1
        self._probe.exited_transactions += 1


class _DatabaseClientStub:
    def __init__(
        self,
        sales_result: EventSalesAnalytics,
        occupancy_result: EventOccupancyAnalytics,
        fail_sales: bool = False,
    ) -> None:
        self.probe = _ConcurrencyProbe()
        self._repository = _AnalyticsRepositoryStub(
            probe=self.probe,
            sales_result=sales_result,
            occupancy_result=occupancy_result,
            fail_sales=fail_sales,
        )

    def transaction(self) -> _TransactionStub:
        return _TransactionStub(self.probe, self._repository)

    async def aclose(self) -> None:
        return None


class EventAnalyticsServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._sales_result = EventSalesAnalytics(
            title="Concert",
            starts_at=datetime.now(UTC),
            paid_orders=2,
            sold_tickets=3,
            revenue=4_000,
            average_order=Decimal("2000"),
        )
        self._occupancy_result = EventOccupancyAnalytics(
            total=6,
            available=2,
            sold=3,
        )

    async def test_queries_overlap_and_use_separate_transactions(self) -> None:
        db_client = _DatabaseClientStub(
            sales_result=self._sales_result,
            occupancy_result=self._occupancy_result,
        )
        service = ObtainEventAnalyticsDataService(db_client=db_client)

        result = await service.exec(event_id=11, organizer_id=101)

        self.assertEqual(result.sales_paid_orders, 2)
        self.assertEqual(result.occupancy_total, 6)
        self.assertEqual(len(db_client.probe.transaction_tokens), 2)
        self.assertIsNot(
            db_client.probe.transaction_tokens[0],
            db_client.probe.transaction_tokens[1],
        )
        self.assertEqual(db_client.probe.max_active_transactions, 2)
        self.assertEqual(db_client.probe.exited_transactions, 2)
        self.assertEqual(db_client.probe.active_transactions, 0)

    async def test_database_error_becomes_controlled_service_error(self) -> None:
        db_client = _DatabaseClientStub(
            sales_result=self._sales_result,
            occupancy_result=self._occupancy_result,
            fail_sales=True,
        )
        service = ObtainEventAnalyticsDataService(db_client=db_client)

        with self.assertRaises(EventServiceError) as raised_error:
            await service.exec(event_id=11, organizer_id=101)

        self.assertIsNotNone(raised_error.exception.__cause__)
        self.assertEqual(db_client.probe.exited_transactions, 2)
        self.assertEqual(db_client.probe.active_transactions, 0)
