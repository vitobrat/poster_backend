import httpx

from src.infrastructure.api_connectors.base import BaseHTTPConnector
from src.infrastructure.api_connectors.external.payment_service.dto import (
    PaymentCalculationRequestPayload,
    PaymentCalculationResponse,
)
from src.infrastructure.api_connectors.external.payment_service.exceptions import (
    PaymentServiceError,
)


class PaymentHTTPConnector(BaseHTTPConnector):

    async def payment_calculate(self, payload: PaymentCalculationRequestPayload) -> PaymentCalculationResponse:
        payment_calculate_response = await self._request(
            method="POST",
            url="/payment/calculate",
            json=payload.model_dump(),
            retry=True,
        )

        try:
            payment_calculate_response.raise_for_status()
        except httpx.HTTPStatusError as http_error:
            raise PaymentServiceError from http_error

        payment_calculate_response_data = payment_calculate_response.json()

        return PaymentCalculationResponse.model_validate(payment_calculate_response_data)
