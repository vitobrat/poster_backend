from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter

from src.application.checkout.service import CheckoutService
from src.presentation.checkout import mapper
from src.presentation.checkout.dto import CheckoutRequest, CheckoutResponse
from src.presentation.dependencies import CurrentUserId

router = APIRouter()


@router.post("/events/{event_id}/checkout")
@inject
async def prepare_checkout(
    event_id: int,
    payload: CheckoutRequest,
    user_id: CurrentUserId,
    checkout_service: FromDishka[CheckoutService],
) -> CheckoutResponse:
    """Временно бронирует места за клиентом, возвращает итоговую стоимость
    и возможность страховки."""
    checkout_result = await checkout_service.checkout_event_for_booking_use_case(
        event_id=event_id,
        user_id=user_id,
        seat_ids=payload.seat_ids,
    )

    return mapper.to_checkout_response(checkout_result)
