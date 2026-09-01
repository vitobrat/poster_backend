from fastapi import APIRouter

from src.presentation.dependencies import CurrentUserId
from src.presentation.events.dto import (
    EventCreate,
    EventDashboard,
    EventRead,
    EventSeatRead,
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
async def get_event_dashboard(
    event_id: int,
    organizer_id: CurrentUserId,
) -> EventDashboard:
    """Возвращает аналитические данные мероприятия."""
    # TODO: проверить принадлежность мероприятия organizer_id.
    # TODO: конкурентно загрузить продажи и занятость разными DB-запросами.
    raise NotImplementedError
