class CheckoutError(Exception):
    """Базовая ошибка checkout."""


class DuplicateSeatIdsError(CheckoutError):
    """Запрошенные идентификаторы мест содержат дубликаты."""


class SeatsNotFoundError(CheckoutError):
    """Часть запрошенных мест не найдена для мероприятия."""


class SeatsUnavailableError(CheckoutError):
    """Хотя бы одно из запрошенных мест недоступно для бронирования."""
