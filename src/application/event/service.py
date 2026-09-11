from src.application.event.dto import EventAnalyticsResult, EventData
from src.application.event.obtain_analytics import (
    ObtainEventAnalyticsDataService,
)
from src.application.event.obtain_event import ObtainEventService


class EventService:

    def __init__(
        self,
        obtain_event_analytics_service: ObtainEventAnalyticsDataService,
        obtain_event_singleflight_service: ObtainEventService,
    ) -> None:
        self._obtain_event_analytics_data_service = obtain_event_analytics_service
        self._obtain_event_singleflight_service = obtain_event_singleflight_service

    async def get_event_analytics_data(
        self,
        event_id: int,
        organizer_id: int,
    ) -> EventAnalyticsResult:

        return await self._obtain_event_analytics_data_service.exec(event_id, organizer_id)

    async def get_event_data(
        self,
        event_id: int,
    ) -> EventData:

        return await self._obtain_event_singleflight_service.exec(event_id)
