from fastapi import APIRouter

from src.presentation.locations.dto import (
    LocationDetail,
    LocationRead,
    SeatRead,
)

router = APIRouter()


@router.get("/locations")
async def list_locations() -> list[LocationRead]:
    """Возвращает список площадок."""
    raise NotImplementedError


@router.get("/locations/{location_id}")
async def get_location(location_id: int) -> LocationDetail:
    """Возвращает площадку со схемой мест."""
    raise NotImplementedError


@router.get("/locations/{location_id}/seats")
async def list_location_seats(location_id: int) -> list[SeatRead]:
    """Возвращает все места площадки."""
    raise NotImplementedError
