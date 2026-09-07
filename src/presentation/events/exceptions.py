from collections.abc import Mapping
from types import MappingProxyType

from fastapi import status

from src.application.event.exceptions import EventAnalyticsError
from src.application.exception import ApplicationError
from src.domain.event.exceptions import EventAnalyticsNotFoundError
from src.domain.exceptions import DomainError
from src.presentation.schema import ErrorAPISchema

EVENT_DOMAIN_EXCEPTION_RESPONSES: Mapping[type[DomainError], ErrorAPISchema] = MappingProxyType(
    {
        EventAnalyticsNotFoundError: ErrorAPISchema(
            status_code=status.HTTP_404_NOT_FOUND,
            description="Аналитические данные по мероприятию не найдены.",
        ),
    },
)


EVENT_APPLICATION_EXCEPTION_RESPONSES: Mapping[type[ApplicationError], ErrorAPISchema] = MappingProxyType(
    {
        EventAnalyticsError: ErrorAPISchema(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            description="Ошибка получения аналитических данных мероприятия.",
        ),
    },
)
