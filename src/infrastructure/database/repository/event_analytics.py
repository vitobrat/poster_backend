from sqlalchemy import func, select

from src.application.event.dto import (
    EventOccupancyAnalytics,
    EventSalesAnalytics,
)
from src.domain.enums import BookingStatus, SeatStatus
from src.infrastructure.database.models import Booking, Event, EventSeat
from src.infrastructure.database.repository.base import BaseRepo


class EventAnalyticsRepo(BaseRepo):

    async def get_sales_analytics(self, event_id: int, organizer_id: int) -> EventSalesAnalytics | None:
        """Возвращает аналитические данные мероприятия."""

        sold_tickets_count = func.count(EventSeat.id).label("sold_tickets")
        event_sold_tickets_subquery = (
            select(sold_tickets_count)
            .select_from(Event)
            .join(EventSeat, (EventSeat.event_id == Event.id))
            .where(
                EventSeat.status == SeatStatus.sold,
                Event.id == event_id,
                Event.organizer_id == organizer_id,
            )
            .scalar_subquery()
        )

        query = (
            select(
                Event.title,
                Event.starts_at,
                func.count(Booking.id).label("paid_orders"),
                func.coalesce(func.sum(Booking.amount), 0).label("revenue"),
                func.coalesce(func.avg(Booking.amount), 0).label("average_order"),
                event_sold_tickets_subquery.label("sold_tickets"),
            )
            .select_from(Event)
            .outerjoin(Booking, (Booking.event_id == Event.id) & (Booking.status == BookingStatus.paid))
            .where(Event.id == event_id, Event.organizer_id == organizer_id)
            .group_by(Event.id, Event.title, Event.starts_at)
        )

        query_result_orm = await self.session.execute(query)
        analytics_result = query_result_orm.mappings().one_or_none()

        if analytics_result is None:
            return None

        return EventSalesAnalytics(
            title=analytics_result["title"],
            starts_at=analytics_result["starts_at"],
            paid_orders=analytics_result["paid_orders"],
            sold_tickets=analytics_result["sold_tickets"],
            revenue=analytics_result["revenue"],
            average_order=analytics_result["average_order"],
        )

    async def get_occupancy_analytics(self, event_id: int, organizer_id: int) -> EventOccupancyAnalytics | None:
        """Возвращает аналитические данные по заполняемости мероприятия."""

        available_seats_count = func.count(EventSeat.id).label("available_seats")
        sold_seats_count = func.count(EventSeat.id).label("sold_seats")
        total_seats_count = func.count(EventSeat.id).label("total_seats")

        avaible_seats_subquery = (
            select(available_seats_count)
            .select_from(EventSeat)
            .where(
                EventSeat.event_id == Event.id,
                EventSeat.status == SeatStatus.available,
            )
            .correlate(Event)
            .scalar_subquery()
        )

        sold_seats_subquery = (
            select(sold_seats_count)
            .select_from(EventSeat)
            .where(
                EventSeat.event_id == Event.id,
                EventSeat.status == SeatStatus.sold,
            )
            .correlate(Event)
            .scalar_subquery()
        )

        query = (
            select(
                total_seats_count,
                avaible_seats_subquery.label("available_seats"),
                sold_seats_subquery.label("sold_seats"),
            )
            .select_from(Event)
            .outerjoin(EventSeat, (Event.id == EventSeat.event_id))
            .where(Event.id == event_id, Event.organizer_id == organizer_id)
            .group_by(Event.id)
        )

        query_result_orm = await self.session.execute(query)
        analytics_result = query_result_orm.mappings().one_or_none()

        if analytics_result is None:
            return None

        return EventOccupancyAnalytics(
            total=analytics_result["total_seats"],
            available=analytics_result["available_seats"],
            sold=analytics_result["sold_seats"],
        )
