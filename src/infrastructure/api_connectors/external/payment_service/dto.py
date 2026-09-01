from datetime import datetime

from pydantic import BaseModel, Field


class PaymentCalculationRequestPayload(BaseModel):
    booking_id: int
    amount: int = Field(..., gt=0, description="сумма брони в копейках")
    currency: str = Field(..., description="валюта, например RUB")


class PaymentCalculationResponse(BaseModel):
    commission: int = Field(..., ge=0)
    total: int = Field(..., ge=0)
    payment_methods: list[str]
    expires_at: datetime | None = None
