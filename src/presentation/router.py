from fastapi import APIRouter

from src.presentation.bookings.router import router as bookings_router
from src.presentation.checkout.router import router as checkout_router
from src.presentation.events.router import router as events_router
from src.presentation.locations.router import router as locations_router

router = APIRouter()
router.include_router(locations_router)
router.include_router(events_router)
router.include_router(checkout_router)
router.include_router(bookings_router)
