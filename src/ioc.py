from collections.abc import AsyncIterator

from dishka import (
    AsyncContainer,
    Provider,
    Scope,
    make_async_container,
    provide,
)

from src.application.checkout.checkout_event import CheckoutEventService
from src.application.checkout.service import CheckoutService
from src.application.event.obtain_analytics import (
    ObtainEventAnalyticsDataService,
)
from src.application.event.service import EventService
from src.configs.config import (
    APIConnectorsConfigs,
    PostgresConfig,
    RedisConfig,
    Settings,
    UvicornConfig,
)
from src.infrastructure.api_connectors.external.payment_service.client import (
    PaymentAPIHTTPConnector,
)
from src.infrastructure.api_connectors.external.protection_service.client import (
    ProtectionAPIHTTPConnector,
)
from src.infrastructure.api_connectors.schemas import HttpRateLimit
from src.infrastructure.database.base_client import DatabaseClient
from src.infrastructure.postgres.client import PostgresClient


class ConfigProvider(Provider):

    def __init__(self, settings: Settings) -> None:

        super().__init__()
        self._settings = settings

    @provide(scope=Scope.APP)
    def get_settings(self) -> Settings:
        return self._settings

    @provide(scope=Scope.APP)
    def get_api_connectors(self) -> APIConnectorsConfigs:
        return self._settings.api_connectors

    @provide(scope=Scope.APP)
    def get_app(self) -> UvicornConfig:
        return self._settings.app

    @provide(scope=Scope.APP)
    def get_postgres_config(self) -> PostgresConfig:
        return self._settings.postgres

    @provide(scope=Scope.APP)
    def get_redis_config(self) -> RedisConfig:
        return self._settings.redis


class DatabaseProvider(Provider):
    @provide(scope=Scope.APP)
    async def get_database_client(self, config: PostgresConfig) -> AsyncIterator[DatabaseClient]:

        db_client = PostgresClient(config)
        yield db_client
        await db_client.aclose()


class APIConnectorProvider(Provider):

    @provide(scope=Scope.APP)
    async def get_payment_api_connector(self, config: APIConnectorsConfigs) -> AsyncIterator[PaymentAPIHTTPConnector]:
        api_config = config.payment_api_connector
        api_connector = PaymentAPIHTTPConnector(
            base_url=api_config.base_url,
            timeout=api_config.timeout,
            max_retry_attempts=api_config.max_retry_attempts,
            rate_limit_config=HttpRateLimit(
                rate_limit_interval_in_seconds=api_config.rate_limit_interval_in_seconds,
                rate_limit_requests_count=api_config.rate_limit_requests_count,
            ),
        )

        yield api_connector
        await api_connector.aclose_client()

    @provide(scope=Scope.APP)
    async def get_protection_api_connector(
        self,
        config: APIConnectorsConfigs,
    ) -> AsyncIterator[ProtectionAPIHTTPConnector]:
        api_config = config.protection_api_connector
        api_connector = ProtectionAPIHTTPConnector(
            base_url=api_config.base_url,
            timeout=api_config.timeout,
            max_retry_attempts=api_config.max_retry_attempts,
            rate_limit_config=HttpRateLimit(
                rate_limit_interval_in_seconds=api_config.rate_limit_interval_in_seconds,
                rate_limit_requests_count=api_config.rate_limit_requests_count,
            ),
        )

        yield api_connector

        await api_connector.aclose_client()


class EventServiceProvider(Provider):
    @provide(scope=Scope.APP)
    def get_event_obtain_analytics_service(
        self,
        db_client: DatabaseClient,
    ) -> ObtainEventAnalyticsDataService:
        return ObtainEventAnalyticsDataService(
            db_client=db_client,
        )

    @provide(scope=Scope.APP)
    def get_event_service(
        self,
        obtain_event_analytics_service: ObtainEventAnalyticsDataService,
    ) -> EventService:
        return EventService(obtain_event_analytics_service)


class CheckoutServiceProvider(Provider):
    @provide(scope=Scope.APP)
    def get_checkout_event_service(
        self,
        db_client: DatabaseClient,
        payment_api_connector: PaymentAPIHTTPConnector,
        protection_api_connector: ProtectionAPIHTTPConnector,
    ) -> CheckoutEventService:
        return CheckoutEventService(
            db_client=db_client,
            payment_api_connector=payment_api_connector,
            protection_api_connector=protection_api_connector,
        )

    @provide(scope=Scope.APP)
    def get_checkout_service(
        self,
        checkout_event_service: CheckoutEventService,
    ) -> CheckoutService:
        return CheckoutService(checkout_event_service)


def create_container(settings: Settings) -> AsyncContainer:
    return make_async_container(
        ConfigProvider(settings),
        DatabaseProvider(),
        APIConnectorProvider(),
        CheckoutServiceProvider(),
        EventServiceProvider(),
    )
