import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


_HOLD_STORE: Dict[str, Dict[str, Any]] = {}


def hold_flight(
    booking_token: Optional[str] = None,
    flight_id: Optional[str] = None,
    passenger_count: int = 1,
    hold_minutes: int = 15,
    expected_price: Optional[float] = None,
    currency: str = "USD",
) -> Dict[str, Any]:
    """
    Temporarily hold a flight option.

    This is a lab-safe simulation. It does not process payment and does not create
    a confirmed ticket. The hold must be based on a booking_token or flight_id
    returned by search_flights.
    """
    try:
        passengers = int(passenger_count)
        minutes = int(hold_minutes)
    except Exception as exc:
        return {
            "status": "failed",
            "error_code": "invalid_hold_request",
            "message": str(exc),
        }

    if passengers < 1:
        return {
            "status": "failed",
            "error_code": "invalid_passenger_count",
            "message": "Passenger count must be at least 1.",
        }

    if minutes < 1 or minutes > 60:
        return {
            "status": "failed",
            "error_code": "invalid_hold_duration",
            "message": "Hold duration must be between 1 and 60 minutes.",
        }

    if not booking_token and not flight_id:
        return {
            "status": "failed",
            "error_code": "missing_booking_reference",
            "message": "A booking_token or flight_id from search_flights is required before creating a hold.",
        }

    hold_code = "HOLD-" + uuid.uuid4().hex[:8].upper()
    created_at = datetime.now()
    expires_at = created_at + timedelta(minutes=minutes)

    hold_record = {
        "status": "held",
        "hold_code": hold_code,
        "booking_token": booking_token,
        "flight_id": flight_id,
        "passenger_count": passengers,
        "hold_minutes": minutes,
        "expires_at": expires_at.strftime("%Y-%m-%d %H:%M:%S"),
        "expected_price": expected_price,
        "currency": currency.upper(),
        "message": "Temporary hold created. This is not a paid booking or confirmed ticket.",
    }

    _HOLD_STORE[hold_code] = hold_record
    return hold_record


def get_hold(hold_code: str) -> Dict[str, Any]:
    """Look up a temporary hold by hold code."""
    normalized_code = str(hold_code).strip().upper()
    hold_record = _HOLD_STORE.get(normalized_code)
    if not hold_record:
        return {
            "status": "not_found",
            "error_code": "hold_not_found",
            "message": f"Hold code {normalized_code} was not found.",
        }
    return hold_record
