from datetime import UTC, datetime, timedelta

from src.config import BOOKING_TTL_MINUTES
from src.domain.checkout.exceptions import (
    DuplicateSeatIdsError,
    SeatsNotFoundError,
    SeatsUnavailableError,
)
from src.infrastructure.database.base_client import DatabaseClient
from src.infrastructure.database.models import Booking, EventSeat, SeatStatus


class CheckoutService:

    def __init__(
        self,
        db_client: DatabaseClient,
    ) -> None:
        self._db_client = db_client

    async def checkout_booking(self, event_id: int, user_id: int, seat_ids: list[int]) -> Booking:

        async with self._db_client.transaction() as db_manager:
            retrieved_event_seats = await db_manager.event_seats_repo.get_event_seats_for_update(event_id, seat_ids)

            current_time = datetime.now(UTC).replace(tzinfo=None)
            self._ensure_seats_available(retrieved_event_seats, seat_ids, current_time)

            booking = await db_manager.booking_repo.create_pending_booking(
                event_id=event_id,
                user_id=user_id,
                amount=sum(seat.price for seat in retrieved_event_seats),
                reserved_until=current_time + timedelta(minutes=BOOKING_TTL_MINUTES),
            )

            await db_manager.event_seats_repo.reserve_event_seats(
                event_seats=retrieved_event_seats,
                booking_id=booking.id,
                reserved_until=booking.reserved_until,
            )

            return booking

    def _ensure_seats_available(
        self,
        event_seats: list[EventSeat],
        seat_ids: list[int],
        current_time: datetime,
    ) -> None:
        self._ensure_requested_seats_exist(event_seats, seat_ids)

        for event_seat in event_seats:
            self._ensure_event_seat_available(event_seat, current_time)

    def _ensure_requested_seats_exist(
        self,
        event_seats: list[EventSeat],
        seat_ids: list[int],
    ) -> None:
        requested_seat_ids = set(seat_ids)
        if len(requested_seat_ids) != len(seat_ids):
            raise DuplicateSeatIdsError

        retrieved_seat_ids = {seat.seat_id for seat in event_seats}
        if requested_seat_ids != retrieved_seat_ids:
            raise SeatsNotFoundError

    def _ensure_event_seat_available(
        self,
        event_seat: EventSeat,
        current_time: datetime,
    ) -> None:
        if event_seat.status == SeatStatus.sold:
            raise SeatsUnavailableError

        if (
            event_seat.status == SeatStatus.reserved
            and event_seat.reserved_until is not None
            and event_seat.reserved_until > current_time
        ):
            raise SeatsUnavailableError
