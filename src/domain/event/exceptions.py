from src.domain.exceptions import DomainError


class AnalyticsDomainError(DomainError):
    """Базовая ошибка аналитики."""


class EventAnalyticsNotFoundError(AnalyticsDomainError):
    """Аналитические данные по мероприятию не найдены."""


class EventOccupancyAnalyticsNotFoundError(EventAnalyticsNotFoundError):
    """Аналитические данные по заполняемости мероприятия не найдены."""


class EventSalesAnalyticsNotFoundError(EventAnalyticsNotFoundError):
    """Аналитические данные по продажам мероприятия не найдены."""
