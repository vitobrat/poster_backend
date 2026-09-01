import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.application.checkout.checkout_event import CheckoutEventService
from src.configs.config import Settings
from src.domain.checkout.exceptions import CheckoutDomainError
from src.infrastructure.api_connectors.exceptions import HTTPConnectionError
from src.infrastructure.api_connectors.external.payment_service.client import (
    PaymentAPIHTTPConnector,
)
from src.infrastructure.api_connectors.external.payment_service.dto import (
    PaymentCalculationResponse,
)
from src.infrastructure.api_connectors.external.payment_service.exceptions import (
    PaymentExternalAPIError,
)
from src.infrastructure.api_connectors.external.protection_service.client import (
    ProtectionAPIHTTPConnector,
)
from src.infrastructure.api_connectors.external.protection_service.dto import (
    ProtectionCalculationResponse,
)
from src.infrastructure.database.models import (
    Booking,
    BookingStatus,
    Event,
    EventSeat,
    Location,
    Seat,
    SeatStatus,
)
from src.infrastructure.postgres.client import PostgresClient


class CheckoutCompensationTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        settings = Settings()
        self._engine = create_async_engine(
            settings.postgres.url,
            pool_pre_ping=True,
        )
        self._session_maker = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            autoflush=False,
        )
        self._db_client = PostgresClient(settings.postgres)

        token = uuid4().hex
        async with self._session_maker.begin() as session:
            location = Location(
                name=f"checkout-compensation-test-{token}",
                city="test-city",
                address="test-address",
            )
            session.add(location)
            await session.flush()

            seats = [
                Seat(
                    location_id=location.id,
                    sector="test-sector",
                    row=1,
                    number=seat_number,
                    x=0,
                    y=0,
                )
                for seat_number in (1, 2)
            ]
            session.add_all(seats)
            await session.flush()

            event = Event(
                organizer_id=1,
                location_id=location.id,
                title=f"checkout-compensation-test-{token}",
                description=None,
                category="test",
                starts_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1),
                base_price=1_234,
            )
            session.add(event)
            await session.flush()

            event_seats = [
                EventSeat(
                    event_id=event.id,
                    seat_id=seat.id,
                    price=event.base_price,
                )
                for seat in seats
            ]
            session.add_all(event_seats)
            await session.flush()

            self._location_id = location.id
            self._seat_ids = [seat.id for seat in seats]
            self._event_id = event.id
            self._event_seat_ids = [event_seat.id for event_seat in event_seats]

    async def asyncTearDown(self) -> None:
        try:
            if hasattr(self, "_event_id"):
                async with self._session_maker.begin() as session:
                    await session.execute(
                        delete(EventSeat).where(EventSeat.event_id == self._event_id),
                    )
                    await session.execute(
                        delete(Booking).where(Booking.event_id == self._event_id),
                    )
                    await session.execute(
                        delete(Event).where(Event.id == self._event_id),
                    )
                    await session.execute(
                        delete(Seat).where(Seat.id.in_(self._seat_ids)),
                    )
                    await session.execute(
                        delete(Location).where(Location.id == self._location_id),
                    )
        finally:
            if hasattr(self, "_db_client"):
                await self._db_client.aclose()
            if hasattr(self, "_engine"):
                await self._engine.dispose()

    async def test_payment_error_expires_booking_and_releases_seat(self) -> None:
        await self._assert_payment_failure_compensates(
            payment_error=PaymentExternalAPIError("payment failed"),
        )

    async def test_payment_transport_error_expires_booking_and_releases_seat(
        self,
    ) -> None:
        await self._assert_payment_failure_compensates(
            payment_error=HTTPConnectionError("payment connection failed"),
        )

    async def test_unexpected_error_expires_booking_and_releases_seat(
        self,
    ) -> None:
        service = self._build_checkout_service(
            payment_error=RuntimeError("unexpected checkout failure"),
        )

        with self.assertRaises(Exception):
            await service.exec(
                event_id=self._event_id,
                user_id=101,
                seat_ids=[self._seat_ids[0]],
            )

        async with self._session_maker() as session:
            booking = (
                await session.scalars(
                    select(Booking).where(Booking.event_id == self._event_id),
                )
            ).one()
            event_seat = await session.get(
                EventSeat,
                self._event_seat_ids[0],
            )

        self.assertEqual(booking.status, BookingStatus.expired)
        self.assertIsNotNone(event_seat)
        self.assertEqual(event_seat.status, SeatStatus.available)
        self.assertIsNone(event_seat.booking_id)
        self.assertIsNone(event_seat.reserved_until)

    async def _assert_payment_failure_compensates(
        self,
        payment_error: Exception,
    ) -> None:
        service = self._build_checkout_service(payment_error=payment_error)

        with self.assertRaises(CheckoutDomainError) as error_context:
            await service.exec(
                event_id=self._event_id,
                user_id=101,
                seat_ids=[self._seat_ids[0]],
            )

        async with self._session_maker() as session:
            booking = (
                await session.scalars(
                    select(Booking).where(Booking.event_id == self._event_id),
                )
            ).one()
            event_seat = await session.get(EventSeat, self._event_seat_ids[0])

        self.assertEqual(booking.status, BookingStatus.expired)
        self.assertIsNotNone(event_seat)
        self.assertEqual(event_seat.status, SeatStatus.available)
        self.assertIsNone(event_seat.booking_id)
        self.assertIsNone(event_seat.reserved_until)

        self.assertIs(type(error_context.exception), CheckoutDomainError)

    async def test_expired_booking_is_replaced_by_new_booking(self) -> None:
        expired_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)
        old_booking_id = await self._reserve_both_seats_for_old_booking(expired_at)
        service = self._build_checkout_service()

        result = await service.exec(
            event_id=self._event_id,
            user_id=202,
            seat_ids=self._seat_ids,
        )

        async with self._session_maker() as session:
            bookings = {
                booking.id: booking
                for booking in await session.scalars(
                    select(Booking).where(Booking.event_id == self._event_id),
                )
            }
            event_seats = list(
                await session.scalars(
                    select(EventSeat).where(EventSeat.event_id == self._event_id).order_by(EventSeat.id),
                ),
            )

        self.assertEqual(len(bookings), 2)
        self.assertEqual(bookings[old_booking_id].status, BookingStatus.expired)

        new_booking = bookings[result.booking_id]
        self.assertEqual(new_booking.status, BookingStatus.pending_payment)
        self.assertEqual(new_booking.user_id, 202)
        self.assertGreater(new_booking.reserved_until, expired_at)

        self.assertEqual(len(event_seats), 2)
        for event_seat in event_seats:
            self.assertEqual(event_seat.status, SeatStatus.reserved)
            self.assertEqual(event_seat.booking_id, new_booking.id)
            self.assertEqual(event_seat.reserved_until, new_booking.reserved_until)

    def _build_checkout_service(
        self,
        payment_error: Exception | None = None,
    ) -> CheckoutEventService:
        payment_connector = AsyncMock(spec=PaymentAPIHTTPConnector)
        if payment_error is None:
            payment_connector.payment_calculate.return_value = PaymentCalculationResponse(
                commission=300,
                total=2_768,
                payment_methods=["bank_card", "sbp"],
                expires_at=None,
            )
        else:
            payment_connector.payment_calculate.side_effect = payment_error

        protection_connector = AsyncMock(spec=ProtectionAPIHTTPConnector)
        protection_connector.protection_calculate.return_value = ProtectionCalculationResponse(
            available=True,
            price=700,
            covered_amount=2_468,
            description="Full refund",
        )

        return CheckoutEventService(
            db_client=self._db_client,
            payment_api_connector=payment_connector,
            protection_api_connector=protection_connector,
        )

    async def _reserve_both_seats_for_old_booking(
        self,
        reserved_until: datetime,
    ) -> int:
        async with self._session_maker.begin() as session:
            booking = Booking(
                event_id=self._event_id,
                user_id=101,
                amount=2_468,
                payment_commission=0,
                protection_price=None,
                with_protection=False,
                status=BookingStatus.pending_payment,
                reserved_until=reserved_until,
            )
            session.add(booking)
            await session.flush()

            event_seats = list(
                await session.scalars(
                    select(EventSeat).where(EventSeat.event_id == self._event_id),
                ),
            )
            for event_seat in event_seats:
                event_seat.status = SeatStatus.reserved
                event_seat.booking_id = booking.id
                event_seat.reserved_until = reserved_until

            await session.flush()
            return booking.id
