from collections.abc import Mapping

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from src.domain.exceptions import DomainError
from src.presentation.checkout.exceptions import (
    CHECKOUT_DOMAIN_EXCEPTION_RESPONSES,
)
from src.presentation.schema import ErrorAPISchema

DOMAIN_EXCEPTION_RESPONSES: Mapping[type[DomainError], ErrorAPISchema] = CHECKOUT_DOMAIN_EXCEPTION_RESPONSES


def setup_domain_exception_errors(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_exception_handler(  # noqa: WPS430
        _: Request,
        error: DomainError,
    ) -> JSONResponse:
        api_error_response = _get_domain_error_response(error)

        return JSONResponse(
            status_code=api_error_response.status_code,
            content={"detail": api_error_response.description},
        )


def _get_domain_error_response(error: DomainError) -> ErrorAPISchema:
    for domain_error, response in DOMAIN_EXCEPTION_RESPONSES.items():
        if isinstance(error, domain_error):
            return response

    return ErrorAPISchema(status_code=status.HTTP_400_BAD_REQUEST, description="Unknown error")
