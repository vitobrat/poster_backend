from datetime import datetime

from pydantic import BaseModel, Field


class ProtectionCalculationRequestPayload(BaseModel):
    booking_id: int
    ticket_amount: int = Field(..., gt=0, description="стоимость билетов в копейках")
    event_category: str
    event_starts_at: datetime = Field(..., description="дата начала мероприятия в ISO-формате")


class ProtectionCalculationResponse(BaseModel):
    available: bool
    price: int
    covered_amount: int
    description: str | None
