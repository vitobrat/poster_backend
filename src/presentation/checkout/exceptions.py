from collections.abc import Mapping
from types import MappingProxyType

from fastapi import status

from src.application.checkout.exceptions import (
    BookingReservedError,
    BookingUpdatePaymentError,
    CheckoutCompensationError,
    PaymentAPIConnectorError,
    PaymentAPIConnectorTimeout,
)
from src.application.exception import ApplicationError
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

CHECKOUT_APPLICATION_EXCEPTION_RESPONSES: Mapping[type[ApplicationError], ErrorAPISchema] = MappingProxyType(
    {
        PaymentAPIConnectorTimeout: ErrorAPISchema(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            description="Payment API request timed out",
        ),
        PaymentAPIConnectorError: ErrorAPISchema(
            status_code=status.HTTP_502_BAD_GATEWAY,
            description="Failed to connect to payment API",
        ),
        BookingReservedError: ErrorAPISchema(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            description="Failed to reserve booking",
        ),
        BookingUpdatePaymentError: ErrorAPISchema(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            description="Failed to update payment for booking",
        ),
        CheckoutCompensationError: ErrorAPISchema(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            description="Failed to compensate for checkout issue",
        ),
    },
)
