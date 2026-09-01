from pydantic import BaseModel, Field


class HttpRateLimit(BaseModel):
    rate_limit_requests_count: int = Field(gt=0)
    rate_limit_interval_in_seconds: float
