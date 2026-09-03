from src.application.event.dto import EventAnalyticsResult
from src.application.event.obtain_analytics import (
    ObtainEventAnalyticsDataService,
)


class EventService:

    def __init__(self, obtain_event_analytics_service: ObtainEventAnalyticsDataService):
        self._obtain_event_analytics_data_service = obtain_event_analytics_service

    async def get_event_analytics_data(
        self,
        event_id: int,
        organizer_id: int,
    ) -> EventAnalyticsResult:
        return await self._obtain_event_analytics_data_service.exec(event_id, organizer_id)
