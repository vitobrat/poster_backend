from src.application.checkout.dto import CheckoutResult, ProtectionQuote
from src.presentation.checkout.dto import (
    CheckoutBookingResponse,
    CheckoutResponse,
    CheckoutSeatResponse,
    PaymentQuoteResponse,
    ProtectionQuoteResponse,
)


def to_checkout_response(application_result: CheckoutResult) -> CheckoutResponse:
    """Маппер для результата checkout"""

    return CheckoutResponse(
        booking=CheckoutBookingResponse(
            id=application_result.booking_id,
            event_title=application_result.event_title,
            starts_at=application_result.starts_at,
            seats=[CheckoutSeatResponse(seat_id=seat.seat_id, price=seat.price) for seat in application_result.seats],
            base_amount=application_result.base_amount,
            payment_commission=application_result.payment.commission,
            protection_price=application_result.protection.price if application_result.protection else None,
            with_protection=False,
            reserved_until=application_result.reserved_until,
        ),
        payment=PaymentQuoteResponse(
            commission=application_result.payment.commission,
            total=application_result.payment.total,
            payment_methods=application_result.payment.payment_methods,
            expires_at=application_result.payment.expires_at,
        ),
        protection=(
            ProtectionQuoteResponse(
                available=application_result.protection.available,
                price=application_result.protection.price,
                covered_amount=application_result.protection.covered_amount,
                description=application_result.protection.description,
            )
            if isinstance(application_result.protection, ProtectionQuote)
            else None
        ),
    )
