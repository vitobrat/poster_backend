from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter

from src.application.event.service import EventService
from src.presentation.dependencies import CurrentUserId
from src.presentation.events.dto import (
    EventCreate,
    EventDashboardResponse,
    EventRead,
    EventSeatRead,
)
from src.presentation.events.mapper import (
    map_event_analytics_to_dashboard_response,
)

router = APIRouter()


@router.get("/events")
async def list_events() -> list[EventRead]:
    """Возвращает список мероприятий для клиента."""
    raise NotImplementedError


@router.get("/events/{event_id}")
async def get_event(event_id: int) -> EventRead:
    """Возвращает описание мероприятия."""
    raise NotImplementedError


@router.get("/events/{event_id}/seats")
async def list_event_seats(event_id: int) -> list[EventSeatRead]:
    """Возвращает места на мероприятии с ценами и статусами."""
    raise NotImplementedError


@router.get("/organizer/events")
async def list_organizer_events(organizer_id: CurrentUserId) -> list[EventRead]:
    """Возвращает список созданных событий текущего организатора."""
    raise NotImplementedError


@router.post("/organizer/events")
async def create_event(
    payload: EventCreate,
    organizer_id: CurrentUserId,
) -> EventRead:
    """Создаёт мероприятие от лица текущего организатора."""
    raise NotImplementedError


@router.get("/organizer/events/{event_id}/dashboard")
@inject
async def get_event_dashboard(
    event_id: int,
    organizer_id: CurrentUserId,
    event_analytics_service: FromDishka[EventService],
) -> EventDashboardResponse:
    """Возвращает аналитические данные мероприятия."""

    event_sales_data_result = await event_analytics_service.get_event_analytics_data(
        event_id=event_id,
        organizer_id=organizer_id,
    )

    return map_event_analytics_to_dashboard_response(event_sales_data_result)
