from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PAYMENT_API_URL = "http://localhost:9001"
PROTECTION_API_URL = "http://localhost:9002"
BOOKING_TTL_MINUTES = 15


class AppConfig(BaseModel):
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
    app: AppConfig
    postgres: PostgresConfig
    redis: RedisConfig

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )
