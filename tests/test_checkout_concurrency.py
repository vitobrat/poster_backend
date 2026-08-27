import asyncio
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.application.checkout.checkout_event import CheckoutEventService
from src.configs.config import BOOKING_TTL_MINUTES, Settings
from src.domain.checkout.exceptions import (
    DuplicateSeatIdsError,
    EmptySeatIdsError,
    EventNotFoundError,
    SeatsNotFoundError,
    SeatsUnavailableError,
)
from src.infrastructure.api_connectors.external.payment_service.client import (
    PaymentHTTPConnector,
)
from src.infrastructure.api_connectors.external.payment_service.dto import (
    PaymentCalculationResponse,
)
from src.infrastructure.api_connectors.external.protection_service.client import (
    ProtectionHTTPConnector,
)
from src.infrastructure.api_connectors.external.protection_service.dto import (
    ProtectionCalculationResponse,
)
from src.infrastructure.database.models import (
    Booking,
    Event,
    EventSeat,
    Location,
    Seat,
    SeatStatus,
)
from src.infrastructure.database.repository.event_seats import EventSeatRepo
from src.infrastructure.postgres.client import PostgresClient


class _LockCoordinator:
    def __init__(self) -> None:
        self.winner_has_lock = asyncio.Event()
        self.release_winner = asyncio.Event()
        self.loser_query_started = asyncio.Event()
        self.loser_backend_pid: int | None = None
        self._session_roles: dict[int, int] = {}

    def create_repository(self, session: AsyncSession) -> EventSeatRepo:
        session_key = id(session)
        if session_key not in self._session_roles:
            self._session_roles[session_key] = len(self._session_roles)

        return _CoordinatedEventSeatRepo(
            session=session,
            coordinator=self,
            role=self._session_roles[session_key],
        )


class _CoordinatedEventSeatRepo(EventSeatRepo):
    def __init__(
        self,
        session: AsyncSession,
        coordinator: _LockCoordinator,
        role: int,
    ) -> None:
        super().__init__(session)
        self._coordinator = coordinator
        self._role = role

    async def get_event_seats_for_update(
        self,
        event_id: int,
        seat_ids: list[int],
    ) -> list[EventSeat]:
        if self._role == 1:
            self._coordinator.loser_backend_pid = await self.session.scalar(
                text("SELECT pg_backend_pid()"),
            )
            self._coordinator.loser_query_started.set()

        event_seats = await super().get_event_seats_for_update(
            event_id=event_id,
            seat_ids=seat_ids,
        )

        if self._role == 0:
            self._coordinator.winner_has_lock.set()
            await self._coordinator.release_winner.wait()

        return event_seats


class CheckoutConcurrencyTest(unittest.IsolatedAsyncioTestCase):
    def _build_checkout_service(self) -> CheckoutEventService:
        payment_connector = AsyncMock(spec=PaymentHTTPConnector)
        payment_connector.payment_calculate.return_value = PaymentCalculationResponse(
            commission=300,
            total=1_534,
            payment_methods=["bank_card", "sbp"],
            expires_at=None,
        )
        protection_connector = AsyncMock(spec=ProtectionHTTPConnector)
        protection_connector.protection_calculate.return_value = ProtectionCalculationResponse(
            available=True,
            price=700,
            covered_amount=1_234,
            description="Full refund",
        )

        return CheckoutEventService(
            db_client=self._db_client,
            payment_api_connector=payment_connector,
            protection_api_connector=protection_connector,
        )

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
                name=f"checkout-lock-test-{token}",
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
                title=f"checkout-lock-test-{token}",
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
            self._event_seat_id = event_seat.id
            self._base_price = event.base_price

    async def asyncTearDown(self) -> None:
        try:
            if hasattr(self, "_event_id"):
                async with self._session_maker.begin() as session:
                    await session.execute(
                        delete(EventSeat).where(
                            EventSeat.event_id == self._event_id,
                        ),
                    )
                    await session.execute(
                        delete(Booking).where(
                            Booking.event_id == self._event_id,
                        ),
                    )
                    await session.execute(
                        delete(Event).where(Event.id == self._event_id),
                    )
                    await session.execute(
                        delete(Seat).where(Seat.id == self._seat_id),
                    )
                    await session.execute(
                        delete(Location).where(
                            Location.id == self._location_id,
                        ),
                    )
        finally:
            if hasattr(self, "_db_client"):
                await self._db_client.close()
            if hasattr(self, "_engine"):
                await self._engine.dispose()

    async def test_only_one_checkout_reserves_a_locked_seat(self) -> None:
        coordinator = _LockCoordinator()
        service = self._build_checkout_service()
        winner_task: asyncio.Task[None] | None = None
        loser_task: asyncio.Task[None] | None = None

        with patch(
            "src.infrastructure.database.db_manager.EventSeatRepo",
            new=coordinator.create_repository,
        ):
            try:
                winner_task = asyncio.create_task(
                    service.exec(
                        event_id=self._event_id,
                        user_id=101,
                        seat_ids=[self._seat_id],
                    ),
                )
                await asyncio.wait_for(
                    coordinator.winner_has_lock.wait(),
                    timeout=5,
                )

                loser_task = asyncio.create_task(
                    service.exec(
                        event_id=self._event_id,
                        user_id=202,
                        seat_ids=[self._seat_id],
                    ),
                )
                await asyncio.wait_for(
                    coordinator.loser_query_started.wait(),
                    timeout=5,
                )

                loser_backend_pid = coordinator.loser_backend_pid
                self.assertIsNotNone(loser_backend_pid)
                await self._wait_until_backend_waits_on_lock(
                    loser_backend_pid,
                )
                self.assertFalse(loser_task.done())

                coordinator.release_winner.set()
                await asyncio.wait_for(winner_task, timeout=5)

                with self.assertRaises(SeatsUnavailableError):
                    await asyncio.wait_for(loser_task, timeout=5)
            finally:
                coordinator.release_winner.set()
                active_tasks = [task for task in (winner_task, loser_task) if task is not None]
                for task in active_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(
                    *active_tasks,
                    return_exceptions=True,
                )

        async with self._session_maker() as session:
            reserved_seat = await session.get(
                EventSeat,
                self._event_seat_id,
            )
            bookings = list(
                await session.scalars(
                    select(Booking).where(
                        Booking.event_id == self._event_id,
                    ),
                ),
            )

        self.assertEqual(len(bookings), 1)
        booking = bookings[0]

        self.assertIsNotNone(reserved_seat)
        self.assertEqual(reserved_seat.status, SeatStatus.reserved)
        self.assertEqual(reserved_seat.booking_id, booking.id)
        self.assertEqual(reserved_seat.reserved_until, booking.reserved_until)
        self.assertEqual(booking.user_id, 101)

        seconds_left = (booking.reserved_until - datetime.now(UTC).replace(tzinfo=None)).total_seconds()
        self.assertGreater(
            seconds_left,
            BOOKING_TTL_MINUTES * 60 - 10,
        )
        self.assertLessEqual(
            seconds_left,
            BOOKING_TTL_MINUTES * 60,
        )

    async def test_checkout_preserves_expected_checkout_errors(self) -> None:
        service = self._build_checkout_service()
        with self.assertRaises(EmptySeatIdsError):
            await service.exec(
                event_id=self._event_id,
                user_id=101,
                seat_ids=[],
            )

        with self.assertRaises(DuplicateSeatIdsError):
            await service.exec(
                event_id=self._event_id,
                user_id=101,
                seat_ids=[self._seat_id, self._seat_id],
            )

        with self.assertRaises(EventNotFoundError):
            await service.exec(
                event_id=-1,
                user_id=101,
                seat_ids=[self._seat_id],
            )

        with self.assertRaises(SeatsNotFoundError):
            await service.exec(
                event_id=self._event_id,
                user_id=101,
                seat_ids=[-1],
            )

    async def test_checkout_saves_payment_and_protection_quotes(self) -> None:
        service = self._build_checkout_service()
        await service.exec(
            event_id=self._event_id,
            user_id=101,
            seat_ids=[self._seat_id],
        )

        async with self._session_maker() as session:
            booking = (
                await session.scalars(
                    select(Booking).where(Booking.event_id == self._event_id),
                )
            ).one()

        self.assertEqual(booking.amount, self._base_price)
        self.assertEqual(booking.payment_commission, 300)
        self.assertEqual(booking.protection_price, 700)
        self.assertFalse(booking.with_protection)

    async def _wait_until_backend_waits_on_lock(
        self,
        backend_pid: int,
    ) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 5

        async with self._session_maker() as observer:
            while loop.time() < deadline:
                wait_event_type = await observer.scalar(
                    text(
                        "SELECT wait_event_type " "FROM pg_stat_activity " "WHERE pid = :backend_pid",
                    ),
                    {"backend_pid": backend_pid},
                )
                if wait_event_type == "Lock":
                    return
                await asyncio.sleep(0.01)

        self.fail(
            "The second checkout did not wait on the row lock",
        )
