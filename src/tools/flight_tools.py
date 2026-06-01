import json
import os
import re
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


def find_productivity_flights(local_data_path: Optional[str] = None) -> str:
    """
    Scores and ranks flight options from the database based on productivity-enabling comforts.
    """
    data = _load_data(local_data_path)
    scored_options = []
    
    # Combine best_flights and other_flights
    options = data.get("best_flights", []) + data.get("other_flights", [])
    
    for idx, opt in enumerate(options):
        score = 0
        has_free_wifi = False
        has_paid_wifi = False
        has_power = False
        avg_legroom = 0
        legroom_count = 0
        
        segments = opt.get("flights", [])
        for segment in segments:
            exts = [str(e).lower() for e in segment.get("extensions", [])]
            
            # Wi-Fi check
            if any("free wi-fi" in e for e in exts):
                has_free_wifi = True
            elif any("wi-fi" in e for e in exts):
                has_paid_wifi = True
                
            # Power check
            if any("power" in e or "usb" in e or "outlet" in e for e in exts):
                has_power = True
                
            # Legroom check
            legroom_str = segment.get("legroom", "")
            if legroom_str:
                match = re.search(r"(\d+)", legroom_str)
                if match:
                    val = int(match.group(1))
                    avg_legroom += val
                    legroom_count += 1
                    
        # Apply score rules
        if has_free_wifi:
            score += 30
        elif has_paid_wifi:
            score += 15
            
        if has_power:
            score += 30
            
        if legroom_count > 0:
            avg_legroom = avg_legroom / legroom_count
            if avg_legroom > 30:
                score += 15
            elif avg_legroom < 30:
                score -= 15
        else:
            avg_legroom = 30 # default
            
        # Layover penalties
        layovers = opt.get("layovers", [])
        for layover in layovers:
            duration = layover.get("duration", 0)
            if duration > 180: # > 3 hours
                score -= 15
            if layover.get("overnight"):
                score -= 30
                
        # Format for output
        first_seg = segments[0] if segments else {}
        last_seg = segments[-1] if segments else {}
        flight_numbers = [s.get("flight_number", "N/A") for s in segments]
        booking_token = opt.get("booking_token", "")
        
        scored_options.append({
            "flight_id": f"flight-{abs(hash(booking_token or str(idx))) % 1_000_000}",
            "airline": first_seg.get("airline", "Unknown"),
            "flight_numbers": flight_numbers,
            "departure": first_seg.get("departure_airport", {}).get("id"),
            "arrival": last_seg.get("arrival_airport", {}).get("id"),
            "departure_time": first_seg.get("departure_airport", {}).get("time"),
            "arrival_time": last_seg.get("arrival_airport", {}).get("time"),
            "duration": _minutes_to_hhmm(opt.get("total_duration")),
            "stops": max(0, len(segments) - 1),
            "stop_info": ", ".join(layover.get("id", "?") for layover in opt.get("layovers", [])) or None,
            "price": opt.get("price"),
            "comfort_score": score,
            "booking_token": booking_token,
            "booking_link": (
                f"https://www.google.com/travel/flights?booking_token={booking_token}"
                if booking_token
                else "https://www.google.com/travel/flights"
            ),
            "details": {
                "free_wifi": has_free_wifi,
                "power_outlets": has_power,
                "avg_legroom_inches": round(avg_legroom, 1),
                "layovers_count": len(layovers),
            }
        })
        
    scored_options.sort(key=lambda x: (-x["comfort_score"], x["price"] if x["price"] is not None else 99999))
    
    return json.dumps({
        "status": "success",
        "count": len(scored_options),
        "flights": scored_options
    }, indent=2, ensure_ascii=False)


def time_until_flight(
    flight_number: str,
    current_time_str: str,
    local_data_path: Optional[str] = None
) -> str:
    """
    Calculates the duration remaining until a specific flight departs.
    """
    data = _load_data(local_data_path)
    options = data.get("best_flights", []) + data.get("other_flights", [])
    
    target_flight_number = str(flight_number).strip().upper()
    found_segment = None
    
    for opt in options:
        for segment in opt.get("flights", []):
            if segment.get("flight_number", "").strip().upper() == target_flight_number:
                found_segment = segment
                break
        if found_segment:
            break
            
    if not found_segment:
        return json.dumps({
            "status": "error",
            "message": f"Flight '{flight_number}' not found in the database."
        })
        
    dep_time_str = found_segment.get("departure_airport", {}).get("time")
    if not dep_time_str:
        return json.dumps({
            "status": "error",
            "message": f"Departure time for flight '{flight_number}' is missing."
        })
        
    try:
        current_time = datetime.strptime(current_time_str.strip(), "%Y-%m-%d %H:%M")
        departure_time = datetime.strptime(dep_time_str.strip(), "%Y-%m-%d %H:%M")
    except Exception as exc:
        try:
            current_time = datetime.strptime(current_time_str.strip(), "%Y-%m-%d %H:%M:%S")
            departure_time = datetime.strptime(dep_time_str.strip(), "%Y-%m-%d %H:%M:%S")
        except Exception:
            return json.dumps({
                "status": "error",
                "message": f"Time format mismatch. Ensure both are 'YYYY-MM-DD HH:MM'. Detail: {exc}"
            })
            
    delta = departure_time - current_time
    total_seconds = delta.total_seconds()
    
    if total_seconds < 0:
        elapsed = abs(total_seconds)
        hours, remainder = divmod(int(elapsed), 3600)
        minutes, _ = divmod(remainder, 60)
        return json.dumps({
            "status": "elapsed",
            "flight_number": flight_number,
            "departure_time": dep_time_str,
            "current_reference_time": current_time_str,
            "time_since_departure": f"{hours}h {minutes}m",
            "message": f"Flight {flight_number} already departed {hours} hours and {minutes} minutes ago."
        })
    else:
        hours, remainder = divmod(int(total_seconds), 3600)
        minutes, _ = divmod(remainder, 60)
        return json.dumps({
            "status": "pending",
            "flight_number": flight_number,
            "departure_time": dep_time_str,
            "current_reference_time": current_time_str,
            "time_remaining": f"{hours}h {minutes}m",
            "message": f"Flight {flight_number} departs in {hours} hours and {minutes} minutes."
        })


def parse_flight_details(
    flight_number: str,
    local_data_path: Optional[str] = None
) -> str:
    """
    Parses segment-by-segment itinerary, layover details, carbon footprint, and pricing for a flight.
    """
    data = _load_data(local_data_path)
    options = data.get("best_flights", []) + data.get("other_flights", [])
    
    target_flight_number = str(flight_number).strip().upper()
    found_option = None
    
    for opt in options:
        for segment in opt.get("flights", []):
            if segment.get("flight_number", "").strip().upper() == target_flight_number:
                found_option = opt
                break
        if found_option:
            break
            
    if not found_option:
        return json.dumps({
            "status": "error",
            "message": f"Flight route containing '{flight_number}' not found."
        })
        
    segments = found_option.get("flights", [])
    parsed_segments = []
    
    for s in segments:
        parsed_segments.append({
            "flight_number": s.get("flight_number"),
            "airline": s.get("airline"),
            "airplane": s.get("airplane"),
            "travel_class": s.get("travel_class"),
            "legroom": s.get("legroom"),
            "departure": {
                "airport": s.get("departure_airport", {}).get("id"),
                "airport_name": s.get("departure_airport", {}).get("name"),
                "time": s.get("departure_airport", {}).get("time"),
            },
            "arrival": {
                "airport": s.get("arrival_airport", {}).get("id"),
                "airport_name": s.get("arrival_airport", {}).get("name"),
                "time": s.get("arrival_airport", {}).get("time"),
            },
            "duration": _minutes_to_hhmm(s.get("duration")),
            "extensions": s.get("extensions", [])
        })
        
    layovers = []
    for l in found_option.get("layovers", []):
        layovers.append({
            "airport": l.get("id"),
            "airport_name": l.get("name"),
            "duration": _minutes_to_hhmm(l.get("duration")),
            "overnight": l.get("overnight", False)
        })
        
    return json.dumps({
        "status": "success",
        "flight_number": flight_number,
        "price": found_option.get("price"),
        "total_duration": _minutes_to_hhmm(found_option.get("total_duration")),
        "booking_token": found_option.get("booking_token"),
        "segments": parsed_segments,
        "layovers": layovers,
        "carbon_emissions": found_option.get("carbon_emissions", {}),
        "booking_link": f"https://www.google.com/travel/flights?booking_token={found_option.get('booking_token', '')}"
    }, indent=2, ensure_ascii=False)


def get_current_time() -> str:
    """Returns the current local date and time of the system in 'YYYY-MM-DD HH:MM' format."""
    return datetime.now().strftime("%Y-%m-%d %H:%M")
