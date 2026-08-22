from datetime import datetime

from sqlalchemy import select

from src.infrastructure.database.models import EventSeat, SeatStatus
from src.infrastructure.database.repository.base import BaseRepo


class EventSeatRepo(BaseRepo):

    async def get_event_seats_for_update(self, event_id: int, seat_ids: list[int]) -> list[EventSeat]:
        query = (
            select(EventSeat)
            .where(
                EventSeat.event_id == event_id,
                EventSeat.seat_id.in_(seat_ids),
            )
            .order_by(EventSeat.seat_id)
            .with_for_update()
        )

        event_seats_results_orm = await self.session.execute(query)
        event_seats_results = event_seats_results_orm.scalars().all()

        return event_seats_results

    async def reserve_event_seats(
        self,
        event_seats: list[EventSeat],
        booking_id: int,
        reserved_until: datetime,
    ) -> None:
        for seat in event_seats:
            seat.status = SeatStatus.reserved
            seat.booking_id = booking_id
            seat.reserved_until = reserved_until

        await self.session.flush()
