from collections.abc import Mapping
from types import MappingProxyType

from fastapi import status

from src.domain.checkout.exceptions import (
    DuplicateSeatIdsError,
    EmptySeatIdsError,
    EventNotFoundError,
    SeatsNotFoundError,
    SeatsUnavailableError,
)
from src.domain.exceptions import DomainError
from src.presentation.schema import ErrorAPISchema

CHECKOUT_DOMAIN_EXCEPTION_RESPONSES: Mapping[type[DomainError], ErrorAPISchema] = MappingProxyType(
    {
        SeatsUnavailableError: ErrorAPISchema(
            status_code=status.HTTP_409_CONFLICT,
            description="Already reserved, try reserved another",
        ),
        EmptySeatIdsError: ErrorAPISchema(
            status_code=status.HTTP_400_BAD_REQUEST,
            description="No seat identifiers were requested.",
        ),
        DuplicateSeatIdsError: ErrorAPISchema(
            status_code=status.HTTP_400_BAD_REQUEST,
            description="Seat identifiers must be unique",
        ),
        EventNotFoundError: ErrorAPISchema(
            status_code=status.HTTP_404_NOT_FOUND,
            description="The requested event does not exist",
        ),
        SeatsNotFoundError: ErrorAPISchema(
            status_code=status.HTTP_404_NOT_FOUND,
            description="Some requested seats were not found for the event",
        ),
    },
)
