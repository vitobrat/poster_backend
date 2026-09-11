from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.domain.enums import SeatStatus

EVENT_TITLE_MAX_LENGTH = 255
EVENT_DESCRIPTION_MAX_LENGTH = 2000


class EventCreate(BaseModel):
    location_id: int
    title: str = Field(min_length=1, max_length=EVENT_TITLE_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=EVENT_DESCRIPTION_MAX_LENGTH)
    category: str = Field(min_length=1, max_length=100)
    starts_at: datetime
    base_price: int = Field(gt=0)


class EventReadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    organizer_id: int
    location_id: int
    title: str
    description: str | None
    category: str
    starts_at: datetime
    base_price: int


class EventSeatRead(BaseModel):
    id: int
    event_id: int
    seat_id: int
    sector: str
    row: int
    number: int
    x: int  # noqa: WPS111
    y: int  # noqa: WPS111
    price: int
    status: SeatStatus
    reserved_until: datetime | None
    booking_id: int | None


class SalesDashboard(BaseModel):
    paid_orders: int
    sold_tickets: int
    revenue: int
    average_order: float


class OccupancyDashboard(BaseModel):
    total: int
    available: int
    reserved: int
    sold: int
    occupancy_percent: float


class EventDashboardResponse(BaseModel):
    event_title: str
    starts_at: datetime
    sales: SalesDashboard
    occupancy: OccupancyDashboard
