from src.domain.exceptions import DomainError


class CheckoutDomainError(DomainError):
    """Базовая ошибка checkout."""


class EmptySeatIdsError(CheckoutDomainError):
    """No seat identifiers were requested."""


class DuplicateSeatIdsError(CheckoutDomainError):
    """Запрошенные идентификаторы мест содержат дубликаты."""


class EventNotFoundError(CheckoutDomainError):
    """The requested event does not exist."""


class SeatsNotFoundError(CheckoutDomainError):
    """Часть запрошенных мест не найдена для мероприятия."""


class SeatsUnavailableError(CheckoutDomainError):
    """Хотя бы одно из запрошенных мест недоступно для бронирования."""
