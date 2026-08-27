import asyncio
from datetime import UTC, datetime, timedelta

from src.application.checkout.dto import (
    CheckoutResult,
    PaymentQuote,
    ProtectionQuote,
    ReservedBooking,
    ReservedSeat,
)
from src.application.checkout.exceptions import (
    BookingReservedError,
    BookingUpdatePaymentError,
    CheckoutCompensationError,
    PaymentAPIConnectorError,
    PaymentAPIConnectorTimeout,
    PaymentCalculationError,
)
from src.configs.config import BOOKING_TTL_MINUTES
from src.domain.checkout.exceptions import (
    CheckoutError,
    DuplicateSeatIdsError,
    EmptySeatIdsError,
    EventNotFoundError,
    SeatsNotFoundError,
    SeatsUnavailableError,
)
from src.domain.enums import Currency
from src.infrastructure.api_connectors.external.payment_service.client import (
    PaymentHTTPConnector,
)
from src.infrastructure.api_connectors.external.payment_service.dto import (
    PaymentCalculationRequestPayload,
)
from src.infrastructure.api_connectors.external.payment_service.exceptions import (
    PaymentExternalAPIError,
)
from src.infrastructure.api_connectors.external.protection_service.client import (
    ProtectionHTTPConnector,
)
from src.infrastructure.api_connectors.external.protection_service.dto import (
    ProtectionCalculationRequestPayload,
)
from src.infrastructure.api_connectors.external.protection_service.exceptions import (
    ProtectionExternalAPIError,
)
from src.infrastructure.database.base_client import DatabaseClient
from src.infrastructure.database.models import Event, EventSeat, SeatStatus
from src.infrastructure.database.repository.exceptions import (
    BookingNotFoundException,
)


class CheckoutEventService:

    def __init__(
        self,
        db_client: DatabaseClient,
        payment_api_connector: PaymentHTTPConnector,
        protection_api_connector: ProtectionHTTPConnector,
    ) -> None:
        self._db_client = db_client
        self._payment_api_connector = payment_api_connector
        self._protection_api_connector = protection_api_connector

    async def exec(self, event_id: int, user_id: int, seat_ids: list[int]) -> CheckoutResult:

        try:
            booking_info = await self._reserve_empty_booking(
                event_id=event_id,
                user_id=user_id,
                seat_ids=seat_ids,
            )
        except CheckoutError:
            raise
        except Exception as exception:
            raise BookingReservedError from exception

        try:

            async with asyncio.TaskGroup() as tg:
                payment_task = tg.create_task(
                    self._calculate_payment(
                        booking_id=booking_info.booking_id,
                        amount=booking_info.amount,
                    ),
                    name="calculate_booking_payment",
                )
                protection_task = tg.create_task(
                    self._calculate_optional_protection(
                        booking_id=booking_info.booking_id,
                        amount=booking_info.amount,
                        event_category=booking_info.event_category,
                        event_starts_at=booking_info.event_starts_at,
                    ),
                    name="calculate_optional_booking_protection_payment",
                )

        except* PaymentCalculationError as payment_calculating_exception:
            await self.checkout_compensation(
                booking_id=booking_info.booking_id,
            )
            raise CheckoutError from payment_calculating_exception

        payment: PaymentQuote = payment_task.result()
        protection: ProtectionQuote | None = protection_task.result()

        try:
            await self._update_booking_payment_info(
                booking_id=booking_info.booking_id,
                payment_commission=payment.commission,
                protection_price=protection.price if protection is not None and protection.available else None,
            )
        except BookingNotFoundException as booking_not_found_exception:
            await self.checkout_compensation(
                booking_id=booking_info.booking_id,
            )
            raise BookingUpdatePaymentError from booking_not_found_exception

        return CheckoutResult(
            booking_id=booking_info.booking_id,
            reserved_until=booking_info.reserved_until,
            base_amount=booking_info.amount,
            payment=PaymentQuote(
                total=payment.total,
                expires_at=payment.expires_at,
                commission=payment.commission,
                payment_methods=payment.payment_methods,
            ),
            protection=(
                ProtectionQuote(
                    available=protection.available,
                    price=protection.price,
                    covered_amount=protection.covered_amount,
                    description=protection.description,
                )
                if protection
                else None
            ),
            event_title=booking_info.event_title,
            starts_at=booking_info.event_starts_at,
            seats=booking_info.seats,
        )

    async def checkout_compensation(
        self,
        booking_id: int,
    ) -> None:

        try:
            async with self._db_client.transaction() as db_manager:
                await db_manager.booking_repo.expire_booking(booking_id)
                await db_manager.event_seats_repo.unreserve_event_seats(booking_id)
        except BookingNotFoundException as booking_not_found_exception:
            raise CheckoutCompensationError from booking_not_found_exception

    async def _reserve_empty_booking(self, event_id: int, user_id: int, seat_ids: list[int]) -> ReservedBooking:
        self._ensure_requested_seat_ids_valid(seat_ids)

        async with self._db_client.transaction() as db_manager:

            # TODO: Отправить два запроса для retrieved_event_seats и event
            # конкурентно в базу данных, потому что они независимые
            retrieved_event_seats = await db_manager.event_seats_repo.get_event_seats_for_update(event_id, seat_ids)
            event = self._ensure_event_exists(
                await db_manager.event_repo.get_by_id(event_id),
            )

            current_time = datetime.now(UTC).replace(tzinfo=None)
            booking_compensation_ids = self._ensure_seats_available(retrieved_event_seats, seat_ids, current_time)
            if booking_compensation_ids:
                await db_manager.booking_repo.expire_booking_bulk(booking_compensation_ids)

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

        return ReservedBooking(
            booking_id=booking.id,
            amount=booking.amount,
            event_title=event.title,
            event_category=event.category,
            event_starts_at=event.starts_at,
            reserved_until=booking.reserved_until,
            seats=tuple(
                ReservedSeat(seat_id=event_seat.seat_id, price=event_seat.price) for event_seat in retrieved_event_seats
            ),
        )

    async def _update_booking_payment_info(
        self,
        booking_id: int,
        payment_commission: int,
        protection_price: int | None,
    ) -> None:

        async with self._db_client.transaction() as db_manager:
            await db_manager.booking_repo.update_booking_payment(
                booking_id,
                payment_commission,
                protection_price,
            )

    def _ensure_seats_available(
        self,
        event_seats: list[EventSeat],
        seat_ids: list[int],
        current_time: datetime,
    ) -> list[int]:
        self._ensure_requested_seats_exist(event_seats, seat_ids)

        booking_id_needs_compensation = []
        for event_seat in event_seats:
            booking_id_compensation_optional = self._ensure_event_seat_available(event_seat, current_time)
            if booking_id_compensation_optional is not None:
                booking_id_needs_compensation.append(booking_id_compensation_optional)
        return booking_id_needs_compensation

    def _ensure_requested_seat_ids_valid(self, seat_ids: list[int]) -> None:
        if not seat_ids:
            raise EmptySeatIdsError

        if len(set(seat_ids)) != len(seat_ids):
            raise DuplicateSeatIdsError

    def _ensure_requested_seats_exist(
        self,
        event_seats: list[EventSeat],
        seat_ids: list[int],
    ) -> None:
        requested_seat_ids = set(seat_ids)
        retrieved_seat_ids = {seat.seat_id for seat in event_seats}
        if requested_seat_ids != retrieved_seat_ids:
            raise SeatsNotFoundError

    def _ensure_event_exists(self, event: Event | None) -> Event:
        if event is None:
            raise EventNotFoundError

        return event

    def _ensure_event_seat_available(
        self,
        event_seat: EventSeat,
        current_time: datetime,
    ) -> int | None:
        """Возвращает id броней, у которых истек TTL и их необходимо перевести в статус 'expired'"""
        if event_seat.status == SeatStatus.sold:
            raise SeatsUnavailableError

        if (
            event_seat.status == SeatStatus.reserved
            and event_seat.reserved_until is not None
            and event_seat.reserved_until > current_time
        ):
            raise SeatsUnavailableError

        if event_seat.status == SeatStatus.reserved:
            return event_seat.booking_id
        return None

    async def _calculate_payment(self, booking_id: int, amount: int, currency: Currency = Currency.RUB) -> PaymentQuote:
        try:
            async with asyncio.timeout(10):
                payment_calculate_response = await self._payment_api_connector.payment_calculate(
                    payload=PaymentCalculationRequestPayload(
                        booking_id=booking_id,
                        amount=amount,
                        currency=currency.value,
                    ),
                )
        except asyncio.TimeoutError as payment_timeout_exception:
            raise PaymentAPIConnectorTimeout from payment_timeout_exception
        except PaymentExternalAPIError as payment_exception:
            raise PaymentAPIConnectorError from payment_exception

        return PaymentQuote(
            commission=payment_calculate_response.commission,
            total=payment_calculate_response.total,
            payment_methods=payment_calculate_response.payment_methods,
            expires_at=payment_calculate_response.expires_at,
        )

    async def _calculate_optional_protection(
        self,
        booking_id: int,
        amount: int,
        event_category: str,
        event_starts_at: datetime,
    ) -> ProtectionQuote | None:
        try:
            async with asyncio.timeout(3):
                protection_calculate_response = await self._protection_api_connector.protection_calculate(
                    payload=ProtectionCalculationRequestPayload(
                        booking_id=booking_id,
                        ticket_amount=amount,
                        event_category=event_category,
                        event_starts_at=event_starts_at,
                    ),
                )
        except (
            asyncio.TimeoutError,
            ProtectionExternalAPIError,
        ):
            return None

        return ProtectionQuote(
            available=protection_calculate_response.available,
            price=protection_calculate_response.price,
            covered_amount=protection_calculate_response.covered_amount,
            description=protection_calculate_response.description,
        )
