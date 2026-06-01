import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _find_data_file(local_data_path: Optional[str] = None) -> Optional[Path]:
    if local_data_path:
        path = Path(local_data_path)
        return path if path.exists() else None

    candidates = [
        Path("data.json"),
        Path("src/tools/data.json"),
        Path("../data.json"),
        Path.cwd() / "data.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _load_data(local_data_path: Optional[str] = None) -> Dict[str, Any]:
    data_path = _find_data_file(local_data_path)
    if not data_path:
        return _sample_data()

    with data_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _sample_data() -> Dict[str, Any]:
    return {
        "best_flights": [
            {
                "flights": [
                    {
                        "departure_airport": {
                            "name": "Paris Charles de Gaulle Airport",
                            "id": "CDG",
                            "time": "2026-03-03 10:10",
                        },
                        "arrival_airport": {
                            "name": "Heathrow Airport",
                            "id": "LHR",
                            "time": "2026-03-03 10:40",
                        },
                        "duration": 90,
                        "airline": "British Airways",
                        "flight_number": "BA 301",
                    },
                    {
                        "departure_airport": {
                            "name": "Heathrow Airport",
                            "id": "LHR",
                            "time": "2026-03-03 12:10",
                        },
                        "arrival_airport": {
                            "name": "Austin-Bergstrom International Airport",
                            "id": "AUS",
                            "time": "2026-03-03 16:50",
                        },
                        "duration": 640,
                        "airline": "British Airways",
                        "flight_number": "BA 191",
                    },
                ],
                "layovers": [{"duration": 90, "name": "Heathrow Airport", "id": "LHR"}],
                "total_duration": 820,
                "price": 520,
                "type": "One way",
                "booking_token": "sample_token_1",
                "extensions": ["Full refund for cancellations", "Free change, possible fare difference"],
            },
            {
                "flights": [
                    {
                        "departure_airport": {
                            "name": "Paris Charles de Gaulle Airport",
                            "id": "CDG",
                            "time": "2026-03-03 11:55",
                        },
                        "arrival_airport": {
                            "name": "Austin-Bergstrom International Airport",
                            "id": "AUS",
                            "time": "2026-03-03 20:05",
                        },
                        "duration": 610,
                        "airline": "British Airways",
                        "flight_number": "BA 303",
                    }
                ],
                "layovers": [],
                "total_duration": 610,
                "price": 525,
                "type": "One way",
                "booking_token": "sample_token_2",
                "extensions": ["Checked baggage for a fee"],
            },
        ]
    }


def _minutes_to_hhmm(minutes: Optional[int]) -> str:
    if minutes is None:
        return "N/A"
    hours, mins = divmod(int(minutes), 60)
    return f"{hours}h {mins}m" if mins else f"{hours}h"


def _normalize_airport(value: str) -> str:
    code = str(value).strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise ValueError(f"Airport must be a 3-letter IATA code, got {value!r}.")
    return code


def _parse_option(option: Dict[str, Any], currency: str) -> Optional[Dict[str, Any]]:
    segments = option.get("flights", [])
    if not segments:
        return None

    first = segments[0]
    last = segments[-1]
    booking_token = option.get("booking_token")
    flight_numbers = [segment.get("flight_number", "N/A") for segment in segments]
    flight_id = f"flight-{abs(hash(booking_token or json.dumps(option, sort_keys=True))) % 1_000_000}"

    return {
        "flight_id": flight_id,
        "airline": first.get("airline", "Unknown"),
        "flight_numbers": flight_numbers,
        "departure_airport": (first.get("departure_airport") or {}).get("id"),
        "arrival_airport": (last.get("arrival_airport") or {}).get("id"),
        "departure_time": (first.get("departure_airport") or {}).get("time"),
        "arrival_time": (last.get("arrival_airport") or {}).get("time"),
        "duration": _minutes_to_hhmm(option.get("total_duration")),
        "stops": max(0, len(segments) - 1),
        "stop_info": ", ".join(layover.get("id", "?") for layover in option.get("layovers", [])) or None,
        "price": float(option.get("price", 0)),
        "currency": currency,
        "booking_token": booking_token,
        "booking_link": (
            f"https://www.google.com/travel/flights?booking_token={booking_token}"
            if booking_token
            else "https://www.google.com/travel/flights"
        ),
        "hold_supported": bool(booking_token),
    }


def search_flights(
    departure_airport: str,
    arrival_airport: str,
    departure_date: str,
    return_date: Optional[str] = None,
    passengers: int = 1,
    travel_class: str = "economy",
    currency: str = "USD",
    local_data_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search flight options from local Google Flights/SerpAPI-style mock data.

    Args:
        departure_airport: 3-letter IATA origin code, e.g. CDG.
        arrival_airport: 3-letter IATA destination code, e.g. AUS.
        departure_date: Outbound date in YYYY-MM-DD format.
        return_date: Optional return date.
        passengers: Number of passengers.
        travel_class: economy, premium_economy, business, or first.
        currency: Currency code for display.

    Returns:
        A dict containing matching flight options and their booking_token values.
    """
    try:
        origin = _normalize_airport(departure_airport)
        destination = _normalize_airport(arrival_airport)
        datetime.strptime(str(departure_date), "%Y-%m-%d")
        passenger_count = int(passengers)
        if passenger_count < 1:
            raise ValueError("passengers must be at least 1.")
    except Exception as exc:
        return {"status": "error", "error_code": "invalid_search_params", "message": str(exc)}

    data = _load_data(local_data_path)
    flights: List[Dict[str, Any]] = []

    for section in ("best_flights", "other_flights"):
        for option in data.get(section, []):
            parsed = _parse_option(option, currency.upper())
            if not parsed:
                continue

            # SerpAPI records may be cached for one route/date. Keep the filter soft so
            # class demos still work with small mock files.
            route_matches = parsed["departure_airport"] == origin and parsed["arrival_airport"] == destination
            if route_matches or not data.get("strict_route_filter"):
                flights.append(parsed)

    flights.sort(key=lambda item: item["price"])

    if not flights:
        return {
            "status": "success",
            "count": 0,
            "message": "No flights found matching the criteria.",
            "query": {
                "departure_airport": origin,
                "arrival_airport": destination,
                "departure_date": departure_date,
                "return_date": return_date,
                "passengers": passenger_count,
                "travel_class": travel_class,
                "currency": currency.upper(),
            },
            "flights": [],
        }

    return {
        "status": "success",
        "count": len(flights),
        "message": f"Found {len(flights)} flight option(s).",
        "query": {
            "departure_airport": origin,
            "arrival_airport": destination,
            "departure_date": departure_date,
            "return_date": return_date,
            "passengers": passenger_count,
            "travel_class": travel_class,
            "currency": currency.upper(),
        },
        "flights": flights[:10],
    }
