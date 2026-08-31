from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorAPISchema:
    status_code: int
    description: str
