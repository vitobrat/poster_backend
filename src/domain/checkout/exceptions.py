class CheckoutError(Exception):
    """Базовая ошибка checkout."""


class EmptySeatIdsError(CheckoutError):
    """No seat identifiers were requested."""


class DuplicateSeatIdsError(CheckoutError):
    """Запрошенные идентификаторы мест содержат дубликаты."""


class EventNotFoundError(CheckoutError):
    """The requested event does not exist."""


class SeatsNotFoundError(CheckoutError):
    """Часть запрошенных мест не найдена для мероприятия."""


class SeatsUnavailableError(CheckoutError):
    """Хотя бы одно из запрошенных мест недоступно для бронирования."""
