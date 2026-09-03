from src.application.exception import ApplicationError


class EventServiceError(ApplicationError):
    """Базовый класс для всех ошибок сервиса мероприятий."""


class EventAnalyticsError(EventServiceError):
    """Ошибка получения аналитических данных мероприятия."""


class SalesAnalyticsError(EventAnalyticsError):
    """Ошибка получения аналитических данных по продажам мероприятия."""


class OccupancyAnalyticsError(EventAnalyticsError):
    """Ошибка получения аналитических данных по заполняемости мероприятия."""
