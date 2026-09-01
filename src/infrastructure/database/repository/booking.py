from datetime import datetime

from sqlalchemy import update

from src.domain.enums import BookingStatus
from src.infrastructure.database.models import Booking
from src.infrastructure.database.repository.base import BaseRepo
from src.infrastructure.database.repository.exceptions import (
    BookingNotFoundException,
)


class BookingRepo(BaseRepo):

    async def create_pending_booking(
        self,
        event_id: int,
        user_id: int,
        amount: int,
        reserved_until: datetime,
    ) -> Booking:
        """Создание бронирования на BOOKING_TTL_MINUTES минут без расчитанной стоимости брони"""

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

    async def update_booking_payment(
        self,
        booking_id: int,
        payment_commission: int,
        protection_price: int | None,
    ) -> None:
        """Обновление стоимости брони и необязательное обновление стоимости страховки для брони"""

        query = (
            update(Booking)
            .where(Booking.id == booking_id)
            .values(payment_commission=payment_commission, protection_price=protection_price)
        )

        booking_update_response = await self.session.execute(query)

        if booking_update_response.rowcount == 0:
            raise BookingNotFoundException

    async def expire_booking(self, booking_id: int) -> None:
        """Обновляем статус бронирования на 'expired', если текущий статус бронирования равен 'pending_payment'"""

        query = (
            update(Booking)
            .where(Booking.id == booking_id, Booking.status == BookingStatus.pending_payment)
            .values(status=BookingStatus.expired)
        )

        booking_update_response = await self.session.execute(query)

        if booking_update_response.rowcount == 0:
            raise BookingNotFoundException

    async def expire_booking_bulk(self, booking_ids: list[int]) -> None:
        """Обновляем статус бронирования на 'expired' у всех booking,
        у кого текущий статус бронирования равен 'pending_payment'"""

        query = (
            update(Booking)
            .where(Booking.id.in_(booking_ids), Booking.status == BookingStatus.pending_payment)
            .values(status=BookingStatus.expired)
        )

        await self.session.execute(query)
