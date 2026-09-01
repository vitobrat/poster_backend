from pydantic import BaseModel

from src.domain.enums import BookingStatus


class PaymentCreate(BaseModel):
    payment_method: str
    with_protection: bool = False


class PaymentCompleted(BaseModel):
    booking_id: int
    status: BookingStatus
    charged_amount: int
    transaction_id: str
