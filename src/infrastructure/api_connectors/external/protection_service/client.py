import json

import httpx
from pydantic import ValidationError

from src.infrastructure.api_connectors.base import BaseHTTPConnector
from src.infrastructure.api_connectors.external.protection_service.dto import (
    ProtectionCalculationRequestPayload,
    ProtectionCalculationResponse,
)
from src.infrastructure.api_connectors.external.protection_service.exceptions import (
    ProtectionExternalAPIError,
)


class ProtectionAPIHTTPConnector(BaseHTTPConnector):

    async def protection_calculate(self, payload: ProtectionCalculationRequestPayload) -> ProtectionCalculationResponse:
        protection_calculate_response = await self._request(
            method="POST",
            url="/protection/calculate",
            json=payload.model_dump(mode="json"),
            retry=True,
        )

        try:
            protection_calculate_response.raise_for_status()
        except httpx.HTTPStatusError as http_error:
            raise ProtectionExternalAPIError from http_error

        try:
            return self._parse_protection_calculation_response(
                protection_calculate_response,
            )
        except (json.JSONDecodeError, ValidationError) as error:
            raise ProtectionExternalAPIError(
                "Protection API returned an invalid response",
            ) from error

    @staticmethod
    def _parse_protection_calculation_response(
        response: httpx.Response,
    ) -> ProtectionCalculationResponse:
        response_data = response.json()
        return ProtectionCalculationResponse.model_validate(response_data)
