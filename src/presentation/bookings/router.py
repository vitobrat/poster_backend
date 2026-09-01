from fastapi import APIRouter

from src.presentation.bookings.dto import PaymentCompleted, PaymentCreate
from src.presentation.dependencies import CurrentUserId

router = APIRouter()


@router.post("/bookings/{booking_id}/pay")
async def pay_booking(
    booking_id: int,
    payload: PaymentCreate,
    user_id: CurrentUserId,
) -> PaymentCompleted:
    """Принимает способ оплаты и флаг with_protection."""
    raise NotImplementedError
