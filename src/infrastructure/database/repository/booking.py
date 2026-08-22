from datetime import datetime

from src.infrastructure.database.models import Booking, BookingStatus
from src.infrastructure.database.repository.base import BaseRepo


class BookingRepo(BaseRepo):

    async def create_pending_booking(
        self,
        event_id: int,
        user_id: int,
        amount: int,
        reserved_until: datetime,
    ) -> Booking:
        """"""

        booking = Booking(
            event_id=event_id,
            user_id=user_id,
            amount=amount,
            payment_commission=0,
            protection_price=None,
            with_protection=False,
            status=BookingStatus.pending_payment,
            reserved_until=reserved_until,
        )

        self.session.add(booking)
        await self.session.flush()

        return booking
