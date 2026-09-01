from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PAYMENT_API_URL = "http://localhost:9001"
PROTECTION_API_URL = "http://localhost:9002"
BOOKING_TTL_MINUTES = 15


class PaymentAPIServiceConfig(BaseModel):
    base_url: str = PAYMENT_API_URL
    timeout: float = 5.0
    rate_limit_requests_count: int = 6
    rate_limit_interval_in_seconds: float = 1.0
    max_retry_attempts: int = 5


class ProtectionAPIServiceConfig(BaseModel):
    base_url: str = PROTECTION_API_URL
    timeout: float = 2.9
    rate_limit_requests_count: int = 6
    rate_limit_interval_in_seconds: float = 1.0
    max_retry_attempts: int = 3


class APIConnectorsConfigs(BaseModel):
    payment_api_connector: PaymentAPIServiceConfig = Field(
        default_factory=PaymentAPIServiceConfig,
    )
    protection_api_connector: ProtectionAPIServiceConfig = Field(
        default_factory=ProtectionAPIServiceConfig,
    )


class UvicornConfig(BaseModel):
    host: str
    port: int
    reload: bool


class PostgresConfig(BaseModel):
    host: str
    port: int
    user: str
    password: SecretStr
    database: str

    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 20

    @property
    def url(self) -> str:
        return (
            f"postgresql+psycopg://{self.user}:"
            f"{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.database}"
        )


class RedisConfig(BaseModel):
    host: str
    port: int
    password: SecretStr | None = None
    database: int = 0

    @property
    def url(self) -> str:
        if self.password is None:
            return f"redis://{self.host}:{self.port}/{self.database}"

        password = self.password.get_secret_value()
        return f"redis://:{password}@{self.host}:{self.port}/{self.database}"


class Settings(BaseSettings):
    app: UvicornConfig
    postgres: PostgresConfig
    redis: RedisConfig
    api_connectors: APIConnectorsConfigs = Field(
        default_factory=APIConnectorsConfigs,
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )
