import asyncio

from src.application.event.dto import (
    EventAnalyticsResult,
    EventOccupancyAnalytics,
    EventSalesAnalytics,
)
from src.application.event.exceptions import (
    EventAnalyticsError,
    EventServiceError,
    OccupancyAnalyticsError,
    SalesAnalyticsError,
)
from src.domain.event.exceptions import (
    EventAnalyticsNotFoundError,
    EventOccupancyAnalyticsNotFoundError,
    EventSalesAnalyticsNotFoundError,
)
from src.infrastructure.database.base_client import DatabaseClient


class ObtainEventAnalyticsDataService:
    def __init__(
        self,
        db_client: DatabaseClient,
    ) -> None:
        self._db_client = db_client

    async def exec(self, event_id: int, organizer_id: int) -> EventAnalyticsResult:
        """Возвращает аналитические данные мероприятия."""
        try:
            return await self._competitive_analytics_request(event_id, organizer_id)
        except (EventSalesAnalyticsNotFoundError, EventOccupancyAnalyticsNotFoundError) as domain_error:
            raise EventAnalyticsNotFoundError from domain_error
        except EventAnalyticsError as analytics_error:
            raise EventServiceError from analytics_error

    async def _competitive_analytics_request(self, event_id: int, organizer_id: int) -> EventAnalyticsResult:
        """Возвращает аналитические данные мероприятия из базы данных."""
        try:
            async with asyncio.TaskGroup() as tg:
                task_sales_analytics = tg.create_task(
                    self._get_sales_repo_request(event_id, organizer_id),
                )
                task_occupancy_analytics = tg.create_task(
                    self._get_occupancy_repo_request(event_id, organizer_id),
                )
        except* (SalesAnalyticsError, OccupancyAnalyticsError) as analytics_errors:
            raise EventAnalyticsError from analytics_errors.exceptions[0]

        task_sales_analytics_result = task_sales_analytics.result()
        task_occupancy_analytics_result = task_occupancy_analytics.result()

        if task_sales_analytics_result is None:
            raise EventSalesAnalyticsNotFoundError("Аналитические данные по продажам мероприятия не найдены.")
        if task_occupancy_analytics_result is None:
            raise EventOccupancyAnalyticsNotFoundError("Аналитические данные по заполняемости мероприятия не найдены.")

        return EventAnalyticsResult(
            event_title=task_sales_analytics_result.title,
            starts_at=task_sales_analytics_result.starts_at,
            sales_paid_orders=task_sales_analytics_result.paid_orders,
            sales_sold_tickets=task_sales_analytics_result.sold_tickets,
            sales_revenue=task_sales_analytics_result.revenue,
            sales_average_order=task_sales_analytics_result.average_order,
            occupancy_total=task_occupancy_analytics_result.total,
            occupancy_available=task_occupancy_analytics_result.available,
            occupancy_sold=task_occupancy_analytics_result.sold,
        )

    async def _get_sales_repo_request(self, event_id: int, organizer_id: int) -> EventSalesAnalytics | None:
        """Возвращает аналитические данные по продажам мероприятия из базы данных."""

        try:
            async with self._db_client.transaction() as db_manager:
                return await db_manager.event_analytics_repo.get_sales_analytics(
                    event_id,
                    organizer_id,
                )
        except Exception as exception:
            raise SalesAnalyticsError from exception

    async def _get_occupancy_repo_request(self, event_id: int, organizer_id: int) -> EventOccupancyAnalytics | None:
        """Возвращает аналитические данные по заполняемости мероприятия из базы данных."""

        try:
            async with self._db_client.transaction() as db_manager:
                return await db_manager.event_analytics_repo.get_occupancy_analytics(
                    event_id,
                    organizer_id,
                )
        except Exception as exception:
            raise OccupancyAnalyticsError from exception
