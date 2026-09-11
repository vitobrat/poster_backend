from src.domain.exceptions import DomainError


class EventDomainError(DomainError):
    """Базовая ошибка мероприятия"""


class EventAnalyticsError(EventDomainError):
    """Базовая ошибка аналитики мероприятия."""


class EventDataNotFoundError(EventDomainError):
    """Данные по мероприятию не найдены"""


class EventAnalyticsNotFoundError(EventAnalyticsError):
    """Аналитические данные по мероприятию не найдены."""


class EventOccupancyAnalyticsNotFoundError(EventAnalyticsNotFoundError):
    """Аналитические данные по заполняемости мероприятия не найдены."""


class EventSalesAnalyticsNotFoundError(EventAnalyticsNotFoundError):
    """Аналитические данные по продажам мероприятия не найдены."""
