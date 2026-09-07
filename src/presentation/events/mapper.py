from src.application.event.dto import EventAnalyticsResult
from src.presentation.events.dto import (
    EventDashboardResponse,
    OccupancyDashboard,
    SalesDashboard,
)


def map_event_analytics_to_dashboard_response(
    event_sales_data_result: EventAnalyticsResult,
) -> EventDashboardResponse:
    """Преобразует EventAnalyticsResult в EventDashboardResponse."""
    return EventDashboardResponse(
        event_title=event_sales_data_result.event_title,
        starts_at=event_sales_data_result.starts_at,
        sales=SalesDashboard(
            paid_orders=event_sales_data_result.sales_paid_orders,
            sold_tickets=event_sales_data_result.sales_sold_tickets,
            revenue=event_sales_data_result.sales_revenue,
            average_order=float(event_sales_data_result.sales_average_order),
        ),
        occupancy=OccupancyDashboard(
            total=event_sales_data_result.occupancy_total,
            available=event_sales_data_result.occupancy_available,
            reserved=event_sales_data_result.occupancy_total
            - event_sales_data_result.occupancy_available
            - event_sales_data_result.occupancy_sold,
            sold=event_sales_data_result.occupancy_sold,
            occupancy_percent=(
                (event_sales_data_result.occupancy_total - event_sales_data_result.occupancy_available)
                / event_sales_data_result.occupancy_total
                * 100
                if event_sales_data_result.occupancy_total > 0
                else 0
            ),
        ),
    )
