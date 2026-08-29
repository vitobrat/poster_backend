import asyncio
import unittest
from datetime import UTC, datetime, timedelta
from time import monotonic
from unittest.mock import AsyncMock
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.application.checkout.checkout_event import CheckoutEventService
from src.configs.config import Settings
from src.infrastructure.api_connectors.external.payment_service.client import (
    PaymentAPIHTTPConnector,
)
from src.infrastructure.api_connectors.external.payment_service.dto import (
    PaymentCalculationResponse,
)
from src.infrastructure.api_connectors.external.protection_service.client import (
    ProtectionAPIHTTPConnector,
)
from src.infrastructure.api_connectors.external.protection_service.exceptions import (
    ProtectionExternalAPIError,
)
from src.infrastructure.database.models import (
    Booking,
    Event,
    EventSeat,
    Location,
    Seat,
)
from src.infrastructure.postgres.client import PostgresClient


class CheckoutProtectionTest(unittest.IsolatedAsyncioTestCase):
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
                name=f"checkout-protection-test-{token}",
                city="test-city",
                address="test-address",
            )
            session.add(location)
            await session.flush()

            seat = Seat(
                location_id=location.id,
                sector="test-sector",
                row=1,
                number=1,
                x=0,
                y=0,
            )
            session.add(seat)
            await session.flush()

            event = Event(
                organizer_id=1,
                location_id=location.id,
                title=f"checkout-protection-test-{token}",
                description=None,
                category="test",
                starts_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1),
                base_price=1_234,
            )
            session.add(event)
            await session.flush()

            event_seat = EventSeat(
                event_id=event.id,
                seat_id=seat.id,
                price=event.base_price,
            )
            session.add(event_seat)
            await session.flush()

            self._location_id = location.id
            self._seat_id = seat.id
            self._event_id = event.id

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
                        delete(Seat).where(Seat.id == self._seat_id),
                    )
                    await session.execute(
                        delete(Location).where(Location.id == self._location_id),
                    )
        finally:
            if hasattr(self, "_db_client"):
                await self._db_client.aclose()
            if hasattr(self, "_engine"):
                await self._engine.dispose()

    async def test_slow_protection_does_not_block_payment_result(self) -> None:
        protection_cancelled_after: float | None = None

        async def slow_protection_calculate(*, payload: object) -> None:
            nonlocal protection_cancelled_after
            request_started_at = monotonic()
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                protection_cancelled_after = monotonic() - request_started_at
                raise

        service = self._build_checkout_service(
            protection_side_effect=slow_protection_calculate,
        )

        request_started_at = monotonic()
        result = await service.exec(
            event_id=self._event_id,
            user_id=101,
            seat_ids=[self._seat_id],
        )
        checkout_duration = monotonic() - request_started_at
        booking = await self._get_booking()

        self.assertIsNone(result.protection)
        self.assertEqual(result.payment.commission, 300)
        self.assertEqual(result.payment.total, 1_534)
        self.assertEqual(booking.payment_commission, 300)
        self.assertIsNone(booking.protection_price)
        self.assertIsNotNone(protection_cancelled_after)
        self.assertLessEqual(protection_cancelled_after, 3.2)
        self.assertLess(checkout_duration, 3.5)

    async def test_protection_error_does_not_break_checkout(self) -> None:
        service = self._build_checkout_service(
            protection_side_effect=ProtectionExternalAPIError(
                "503 Service Unavailable",
            ),
        )

        result = await service.exec(
            event_id=self._event_id,
            user_id=101,
            seat_ids=[self._seat_id],
        )
        booking = await self._get_booking()

        self.assertIsNone(result.protection)
        self.assertEqual(result.payment.commission, 300)
        self.assertEqual(result.payment.total, 1_534)
        self.assertEqual(booking.payment_commission, 300)
        self.assertIsNone(booking.protection_price)

    def _build_checkout_service(
        self,
        protection_side_effect: object,
    ) -> CheckoutEventService:
        payment_connector = AsyncMock(spec=PaymentAPIHTTPConnector)
        payment_connector.payment_calculate.return_value = PaymentCalculationResponse(
            commission=300,
            total=1_534,
            payment_methods=["bank_card", "sbp"],
            expires_at=None,
        )
        protection_connector = AsyncMock(spec=ProtectionAPIHTTPConnector)
        protection_connector.protection_calculate.side_effect = protection_side_effect

        return CheckoutEventService(
            db_client=self._db_client,
            payment_api_connector=payment_connector,
            protection_api_connector=protection_connector,
        )

    async def _get_booking(self) -> Booking:
        async with self._session_maker() as session:
            return (
                await session.scalars(
                    select(Booking).where(Booking.event_id == self._event_id),
                )
            ).one()
