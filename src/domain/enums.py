from enum import Enum, StrEnum


class SeatStatus(str, Enum):
    available = "available"
    reserved = "reserved"
    sold = "sold"


class BookingStatus(str, Enum):
    pending_payment = "pending_payment"
    paid = "paid"
    cancelled = "cancelled"
    expired = "expired"


class Currency(StrEnum):
    RUB = "RUB"
    DOLLAR = "USD"
    EURO = "EU"
