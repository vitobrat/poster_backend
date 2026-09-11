from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class EventData(BaseModel):
    id: int = Field(..., description="ID мероприятия")
    organizer_id: int = Field(..., description="ID организатора")
    location_id: int = Field(..., description="ID локации")
    title: str = Field(..., description="Название мероприятия")
    description: str | None = Field(default=None, description="Описание мероприятия")
    category: str = Field(..., description="Категория мероприятия")
    starts_at: datetime = Field(..., description="Дата и время начала мероприятия")
    base_price: int = Field(..., description="Базовая цена билета на мероприятие")


@dataclass(frozen=True, slots=True)
class EventAnalyticsResult:
    event_title: str
    starts_at: datetime
    sales_paid_orders: int
    sales_sold_tickets: int
    sales_revenue: int
    sales_average_order: Decimal
    occupancy_total: int
    occupancy_available: int
    occupancy_sold: int


@dataclass(frozen=True, slots=True)
class EventSalesAnalytics:
    title: str
    starts_at: datetime
    paid_orders: int
    sold_tickets: int
    revenue: int
    average_order: Decimal


@dataclass(frozen=True, slots=True)
class EventOccupancyAnalytics:
    total: int
    available: int
    sold: int
