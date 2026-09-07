from src.application.exception import ApplicationError


class PaymentCalculationError(ApplicationError):
    """Ошибка расчета платежа"""


class PaymentAPIConnectorError(PaymentCalculationError):
    """Ошибка при вычислении суммы платежа"""


class PaymentAPIConnectorTimeout(PaymentAPIConnectorError):
    """Превышено время ожидания сервиса платежей"""


class BookingDBError(ApplicationError):
    """Ошибка при взаимодействии с таблицей Booking в базе данных"""


class BookingReservedError(BookingDBError):
    """Ошибка при создании резервации бронирования"""


class BookingUpdatePaymentError(BookingDBError):
    """Ошибка при обновлении стоимости бронирования"""


class CheckoutCompensationError(ApplicationError):
    """Ошибка возникла при выполнении компенсации бронирования (откате брони мест)"""
