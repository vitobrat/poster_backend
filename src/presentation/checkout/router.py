from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter

from src.application.checkout.service import CheckoutService
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
    # TODO: создать бронь для выбранных мест через SELECT FOR UPDATE, и посчитать базовую стоимость.
    # TODO: конкурентно запросить Payment API и Protection API для расчета checkout.
    raise NotImplementedError
