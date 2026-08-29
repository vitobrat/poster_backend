from src.application.checkout.checkout_event import CheckoutEventService
from src.application.checkout.dto import CheckoutResult


class CheckoutService:
    def __init__(self, checkout_event_service: CheckoutEventService) -> None:
        self._checkout_event_service = checkout_event_service

    async def checkout_event_for_booking_use_case(
        self,
        event_id: int,
        user_id: int,
        seat_ids: list[int],
    ) -> CheckoutResult:
        return await self._checkout_event_service.exec(
            event_id,
            user_id,
            seat_ids,
        )
