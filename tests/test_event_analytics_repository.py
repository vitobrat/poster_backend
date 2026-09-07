import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.configs.config import Settings
from src.domain.enums import BookingStatus, SeatStatus
from src.infrastructure.database.models import (
    Booking,
    Event,
    EventSeat,
    Location,
    Seat,
)
from src.infrastructure.database.repository.event_analytics import (
    EventAnalyticsRepo,
)


class EventAnalyticsRepositoryTest(unittest.IsolatedAsyncioTestCase):
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
        self._event_ids: list[int] = []
        self._seat_ids: list[int] = []
        self._booking_ids: list[int] = []

        await self._create_test_data()

    async def asyncTearDown(self) -> None:
        try:
            async with self._session_maker.begin() as session:
                await session.execute(
                    delete(EventSeat).where(
                        EventSeat.event_id.in_(self._event_ids),
                    ),
                )
                await session.execute(
                    delete(Booking).where(
                        Booking.id.in_(self._booking_ids),
                    ),
                )
                await session.execute(
                    delete(Event).where(Event.id.in_(self._event_ids)),
                )
                await session.execute(
                    delete(Seat).where(Seat.id.in_(self._seat_ids)),
                )
                await session.execute(
                    delete(Location).where(Location.id == self._location_id),
                )
        finally:
            await self._engine.dispose()

    async def test_sales_aggregates_include_only_paid_bookings(self) -> None:
        async with self._session_maker() as session:
            result = await EventAnalyticsRepo(session).get_sales_analytics(
                event_id=self._target_event_id,
                organizer_id=self._organizer_id,
            )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.title, self._target_title)
        self.assertEqual(result.paid_orders, 2)
        self.assertEqual(result.sold_tickets, 3)
        self.assertEqual(result.revenue, 4_000)
        self.assertEqual(result.average_order, Decimal("2000"))

    async def test_occupancy_is_isolated_by_event_and_counts_statuses(self) -> None:
        async with self._session_maker() as session:
            result = await EventAnalyticsRepo(session).get_occupancy_analytics(
                event_id=self._target_event_id,
                organizer_id=self._organizer_id,
            )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.total, 6)
        self.assertEqual(result.available, 2)
        self.assertEqual(result.sold, 3)
        self.assertEqual(result.total - result.available - result.sold, 1)

    async def test_event_without_sales_returns_zero_aggregates(self) -> None:
        async with self._session_maker() as session:
            result = await EventAnalyticsRepo(session).get_sales_analytics(
                event_id=self._no_sales_event_id,
                organizer_id=self._organizer_id,
            )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.paid_orders, 0)
        self.assertEqual(result.sold_tickets, 0)
        self.assertEqual(result.revenue, 0)
        self.assertEqual(result.average_order, Decimal("0"))

    async def test_event_without_seats_returns_zero_occupancy(self) -> None:
        async with self._session_maker() as session:
            result = await EventAnalyticsRepo(session).get_occupancy_analytics(
                event_id=self._empty_event_id,
                organizer_id=self._organizer_id,
            )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.total, 0)
        self.assertEqual(result.available, 0)
        self.assertEqual(result.sold, 0)

    async def test_foreign_organizer_and_missing_event_return_none(self) -> None:
        async with self._session_maker() as session:
            repository = EventAnalyticsRepo(session)
            foreign_sales = await repository.get_sales_analytics(
                event_id=self._target_event_id,
                organizer_id=self._organizer_id + 1,
            )
            foreign_occupancy = await repository.get_occupancy_analytics(
                event_id=self._target_event_id,
                organizer_id=self._organizer_id + 1,
            )
            missing_sales = await repository.get_sales_analytics(
                event_id=-1,
                organizer_id=self._organizer_id,
            )
            missing_occupancy = await repository.get_occupancy_analytics(
                event_id=-1,
                organizer_id=self._organizer_id,
            )

        self.assertIsNone(foreign_sales)
        self.assertIsNone(foreign_occupancy)
        self.assertIsNone(missing_sales)
        self.assertIsNone(missing_occupancy)

    async def _create_test_data(self) -> None:
        token = uuid4().hex
        starts_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
        self._organizer_id = 91_001
        self._target_title = f"analytics-target-{token}"

        async with self._session_maker.begin() as session:
            location = Location(
                name=f"analytics-location-{token}",
                city="test-city",
                address="test-address",
            )
            session.add(location)
            await session.flush()
            self._location_id = location.id

            target_event = Event(
                organizer_id=self._organizer_id,
                location_id=location.id,
                title=self._target_title,
                description=None,
                category="test",
                starts_at=starts_at,
                base_price=1_000,
            )
            pollution_event = Event(
                organizer_id=self._organizer_id,
                location_id=location.id,
                title=f"analytics-pollution-{token}",
                description=None,
                category="test",
                starts_at=starts_at,
                base_price=5_000,
            )
            no_sales_event = Event(
                organizer_id=self._organizer_id,
                location_id=location.id,
                title=f"analytics-no-sales-{token}",
                description=None,
                category="test",
                starts_at=starts_at,
                base_price=2_000,
            )
            empty_event = Event(
                organizer_id=self._organizer_id,
                location_id=location.id,
                title=f"analytics-empty-{token}",
                description=None,
                category="test",
                starts_at=starts_at,
                base_price=3_000,
            )
            session.add_all(
                [
                    target_event,
                    pollution_event,
                    no_sales_event,
                    empty_event,
                ],
            )
            await session.flush()
            self._target_event_id = target_event.id
            self._no_sales_event_id = no_sales_event.id
            self._empty_event_id = empty_event.id
            self._event_ids.extend(
                [
                    target_event.id,
                    pollution_event.id,
                    no_sales_event.id,
                    empty_event.id,
                ],
            )

            bookings = [
                self._booking(
                    target_event.id,
                    101,
                    3_000,
                    BookingStatus.paid,
                    starts_at,
                ),
                self._booking(
                    target_event.id,
                    102,
                    1_000,
                    BookingStatus.paid,
                    starts_at,
                ),
                self._booking(
                    target_event.id,
                    103,
                    9_000,
                    BookingStatus.pending_payment,
                    starts_at,
                ),
                self._booking(
                    target_event.id,
                    104,
                    8_000,
                    BookingStatus.cancelled,
                    starts_at,
                ),
            ]
            session.add_all(bookings)
            await session.flush()
            self._booking_ids.extend(booking.id for booking in bookings)

            target_statuses = [
                SeatStatus.available,
                SeatStatus.available,
                SeatStatus.reserved,
                SeatStatus.sold,
                SeatStatus.sold,
                SeatStatus.sold,
            ]
            pollution_statuses = [
                SeatStatus.available,
                SeatStatus.available,
                SeatStatus.available,
                SeatStatus.sold,
                SeatStatus.sold,
            ]
            no_sales_statuses = [SeatStatus.available, SeatStatus.reserved]
            event_seats: list[EventSeat] = []
            all_status_groups = (
                (target_event.id, target_statuses),
                (pollution_event.id, pollution_statuses),
                (no_sales_event.id, no_sales_statuses),
            )
            seat_number = 1
            for event_id, statuses in all_status_groups:
                for status in statuses:
                    seat = Seat(
                        location_id=location.id,
                        sector="test-sector",
                        row=1,
                        number=seat_number,
                        x=seat_number,
                        y=0,
                    )
                    session.add(seat)
                    await session.flush()
                    self._seat_ids.append(seat.id)
                    event_seats.append(
                        EventSeat(
                            event_id=event_id,
                            seat_id=seat.id,
                            price=1_000,
                            status=status,
                            booking_id=self._booking_id_for_status(
                                status,
                                bookings,
                            ),
                            reserved_until=starts_at,
                        ),
                    )
                    seat_number += 1

            session.add_all(event_seats)

    @staticmethod
    def _booking(
        event_id: int,
        user_id: int,
        amount: int,
        status: BookingStatus,
        reserved_until: datetime,
    ) -> Booking:
        return Booking(
            event_id=event_id,
            user_id=user_id,
            amount=amount,
            payment_commission=0,
            protection_price=None,
            with_protection=False,
            status=status,
            reserved_until=reserved_until,
        )

    @staticmethod
    def _booking_id_for_status(
        status: SeatStatus,
        bookings: list[Booking],
    ) -> int | None:
        if status == SeatStatus.sold:
            return bookings[0].id
        if status == SeatStatus.reserved:
            return bookings[2].id
        return None
