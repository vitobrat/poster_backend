import json

import httpx
from pydantic import ValidationError

from src.infrastructure.api_connectors.base import BaseHTTPConnector
from src.infrastructure.api_connectors.external.payment_service.dto import (
    PaymentCalculationRequestPayload,
    PaymentCalculationResponse,
)
from src.infrastructure.api_connectors.external.payment_service.exceptions import (
    PaymentExternalAPIError,
)


class PaymentAPIHTTPConnector(BaseHTTPConnector):

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
            raise PaymentExternalAPIError from http_error

        try:
            return self._parse_payment_calculation_response(
                payment_calculate_response,
            )
        except (json.JSONDecodeError, ValidationError) as error:
            raise PaymentExternalAPIError(
                "Payment API returned an invalid response",
            ) from error

    @staticmethod
    def _parse_payment_calculation_response(
        response: httpx.Response,
    ) -> PaymentCalculationResponse:
        response_data = response.json()
        return PaymentCalculationResponse.model_validate(response_data)
