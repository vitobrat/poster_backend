from datetime import datetime

from pydantic import BaseModel, Field


class CheckoutRequest(BaseModel):
    seat_ids: list[int] = Field(min_length=1)


class CheckoutSeatResponse(BaseModel):
    seat_id: int
    price: int


class PaymentQuoteResponse(BaseModel):
    commission: int
    total: int
    payment_methods: list[str]
    expires_at: datetime | None = None


class ProtectionQuoteResponse(BaseModel):
    available: bool
    price: int
    covered_amount: int
    description: str | None = None


class CheckoutBookingResponse(BaseModel):
    id: int
    event_title: str
    starts_at: datetime
    seats: list[CheckoutSeatResponse]
    base_amount: int
    payment_commission: int
    protection_price: int | None
    with_protection: bool
    reserved_until: datetime


class CheckoutResponse(BaseModel):
    booking: CheckoutBookingResponse
    payment: PaymentQuoteResponse
    protection: ProtectionQuoteResponse | None
