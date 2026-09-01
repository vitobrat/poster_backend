from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ReservedSeat:
    seat_id: int
    price: int


@dataclass(frozen=True)
class ReservedBooking:
    booking_id: int
    amount: int
    event_title: str
    event_category: str
    event_starts_at: datetime
    reserved_until: datetime
    seats: tuple[ReservedSeat, ...]


@dataclass(frozen=True)
class PaymentQuote:
    commission: int
    total: int
    payment_methods: list[str]
    expires_at: datetime | None = None


@dataclass(frozen=True)
class ProtectionQuote:
    available: bool
    price: int
    covered_amount: int
    description: str | None


@dataclass(frozen=True)
class CheckoutResult:
    booking_id: int
    reserved_until: datetime

    # Финансовая информация
    base_amount: int

    # Данные внешних сервисов
    payment: PaymentQuote
    protection: ProtectionQuote | None

    # Информация о событии
    event_title: str
    starts_at: datetime
    seats: tuple[ReservedSeat, ...]
