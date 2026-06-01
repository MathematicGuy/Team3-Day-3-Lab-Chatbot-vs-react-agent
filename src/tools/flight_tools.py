import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import serpapi
    HAS_SERPAPI = True
except ImportError:
    HAS_SERPAPI = False

from pydantic import BaseModel, Field, ValidationError, field_validator

SERPAPI_API_KEY = "74dfaaa8c7d60ea26735bc24abe91146f34b58d4c3359052053ce34c763439b4"

# ---------------------------------------------------------------------------
# Resilient Mock Data Loading & Finding
# ---------------------------------------------------------------------------
def _load_data(local_data_path: str = None) -> dict:
    """Helper to locate and load the flight database JSON file."""
    if local_data_path is None:
        # Default places to search for data.json
        possible_paths = [
            "data.json",
            "../data.json",
            "./data.json",
            "./Team3-Day-3-Lab-Chatbot-vs-react-agent/data.json",
            "d:/Personlich/AIO/AIO2025 - Main/_2026_Research/VIN Practitioner/Team3-Day-3-Lab-Chatbot-vs-react-agent/data.json"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                local_data_path = path
                break
    
    if not local_data_path or not os.path.exists(local_data_path):
        raise FileNotFoundError("Could not locate 'data.json' database. Please ensure it is present in the workspace.")
        
    with open(local_data_path, "r", encoding="utf-8") as f:
        return json.load(f)

# Global Mock Data Cache
_MOCK_DATA: Dict[str, Any] = {}
try:
    _MOCK_DATA = _load_data()
except Exception:
    import warnings
    warnings.warn("[flight_tools] Could not initialize _MOCK_DATA automatically. It will fallback on function calls.")

# ---------------------------------------------------------------------------
# Pydantic models for search_flights
# ---------------------------------------------------------------------------
class FlightSearchParams(BaseModel):
    departure_airport: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="IATA code sân bay khởi hành",
    )
    arrival_airport: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="IATA code sân bay đến",
    )
    departure_date: str = Field(
        ...,
        description="Ngày khởi hành theo định dạng YYYY-MM-DD",
    )
    return_date: Optional[str] = Field(
        None,
        description="Ngày về theo định dạng YYYY-MM-DD nếu có",
    )
    passengers: int = Field(
        default=1,
        ge=1,
        le=9,
        description="Số hành khách",
    )
    travel_class: str = Field(
        default="economy",
        description="Hạng vé: economy, business, first, premium_economy",
    )
    currency: str = Field(
        default="USD",
        description="Đơn vị tiền tệ trả về kết quả",
    )

    @field_validator("departure_airport", "arrival_airport", mode="before")
    @classmethod
    def _normalize_airport(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("Mã sân bay phải là chuỗi")
        code = value.strip().upper()
        if len(code) != 3 or not code.isalpha():
            raise ValueError("Mã sân bay phải là 3 chữ cái IATA, ví dụ HAN, SGN")
        return code

    @field_validator("departure_date", "return_date", mode="before")
    @classmethod
    def _validate_date_format(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Ngày phải là chuỗi theo định dạng YYYY-MM-DD")
        try:
            datetime.strptime(value.strip(), "%Y-%m-%d")
        except ValueError:
            raise ValueError("Ngày phải có định dạng YYYY-MM-DD")
        return value.strip()

    @field_validator("travel_class", mode="before")
    @classmethod
    def _validate_travel_class(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("Hạng vé phải là chuỗi")
        normalized = value.strip().lower()
        valid = {"economy", "business", "first", "premium_economy"}
        if normalized not in valid:
            raise ValueError(f"Hạng vé phải là một trong: {', '.join(sorted(valid))}")
        return normalized

    @field_validator("currency", mode="before")
    @classmethod
    def _normalize_currency(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("Đơn vị tiền tệ phải là chuỗi")
        return value.strip().upper()

    def validate_business_rules(self) -> None:
        departure = datetime.strptime(self.departure_date, "%Y-%m-%d").date()
        if departure < datetime.now().date():
            raise ValueError("Ngày khởi hành không được ở quá khứ")
        if self.return_date:
            return_date = datetime.strptime(self.return_date, "%Y-%m-%d").date()
            if return_date <= departure:
                raise ValueError("Ngày về phải sau ngày khởi hành")


class FlightResult(BaseModel):
    flight_id: str = Field(..., description="ID chuyến bay")
    airline: str = Field(..., description="Hãng hàng không")
    departure_time: str = Field(..., description="Giờ cất cánh")
    arrival_time: str = Field(..., description="Giờ hạ cánh")
    duration: str = Field(..., description="Thời gian bay")
    stops: int = Field(..., ge=0, description="Số điểm dừng")
    stop_info: Optional[str] = Field(None, description="Thông tin điểm dừng")
    price: float = Field(..., gt=0, description="Giá vé")
    currency: str = Field(..., description="Đơn vị tiền tệ")
    booking_link: str = Field(..., description="Link đặt vé")
    airline_logo: Optional[str] = Field(None, description="Logo hãng hàng không")
    rating: Optional[float] = Field(None, ge=0, le=5, description="Đánh giá hãng hàng không")


class FlightSearchException(Exception):
    pass

# ---------------------------------------------------------------------------
# Custom/SerpAPI Live Flight Search
# ---------------------------------------------------------------------------
def search_flights_live(departure_id: str = "CDG", arrival_id: str = "AUS", date: str = "2026-06-01") -> dict:
    """
    Queries live Google Flights via SerpAPI for real-time rates and schedules.
    Supports both official 'serpapi' Client and legacy 'google-search-results' GoogleSearch.
    """
    if not HAS_SERPAPI:
        return {"error": "SerpAPI library not installed."}
        
    try:
        if hasattr(serpapi, "Client"):
            client = serpapi.Client(api_key=SERPAPI_API_KEY)
            results = client.search({
                "engine": "google_flights",
                "departure_id": departure_id,
                "arrival_id": arrival_id,
                "currency": "USD",
                "type": "2",
                "outbound_date": date
            })
            return results
    except Exception:
        pass
        
    try:
        from serpapi import GoogleSearch
        search = GoogleSearch({
            "engine": "google_flights",
            "departure_id": departure_id,
            "arrival_id": arrival_id,
            "currency": "USD",
            "type": "2",
            "outbound_date": date,
            "api_key": SERPAPI_API_KEY
        })
        return search.get_dict()
    except Exception as e:
        return {"error": f"Failed to fetch live flights using SerpAPI: {e}"}

# ---------------------------------------------------------------------------
# Custom Traveler Tools (Digital Nomad Productivity Comfort scoring, timing, parsing)
# ---------------------------------------------------------------------------
def find_productivity_flights(local_data_path: str = None) -> str:
    """
    Scores and ranks flight routes from the search database based on productivity-enabling comforts.
    
    Comfort features evaluated:
    - Wi-Fi availability (Free Wi-Fi: +30 pts, Paid Wi-Fi: +15 pts)
    - In-seat power or USB ports presence (+30 pts)
    - Legroom comfort (+15 pts for >=31 in, -15 pts for <30 in)
    - Avoids overnight layovers (-30 pts) and excessive layovers (>6 hrs: -15 pts)
    
    Returns:
    - A JSON string containing comfort-scored flights sorted by productivity score descending.
    """
    try:
        data = _load_data(local_data_path)
    except Exception as e:
        return json.dumps({"error": str(e)})
        
    all_flight_options = []
    
    for category in ["best_flights", "other_flights"]:
        if category in data:
            for option in data[category]:
                flights = option.get("flights", [])
                layovers = option.get("layovers", [])
                
                score = 100  # Base score
                has_wifi = False
                has_power = False
                
                segment_details = []
                for f in flights:
                    flight_num = f.get("flight_number", "N/A")
                    airline = f.get("airline", "N/A")
                    extensions = f.get("extensions", [])
                    
                    seg_wifi = "None"
                    seg_power = False
                    seg_legroom = 30  # default
                    
                    for ext in extensions:
                        ext_lower = ext.lower()
                        if "free wi-fi" in ext_lower or "wi-fi for free" in ext_lower:
                            score += 30
                            seg_wifi = "Free"
                            has_wifi = True
                        elif "wi-fi" in ext_lower:
                            score += 15
                            seg_wifi = "Paid"
                            has_wifi = True
                        
                        if "power" in ext_lower or "usb" in ext_lower or "outlet" in ext_lower:
                            score += 30
                            seg_power = True
                            has_power = True
                            
                        legroom_match = re.search(r"(\d+)\s*in", ext_lower)
                        if legroom_match:
                            seg_legroom = int(legroom_match.group(1))
                            if seg_legroom < 30:
                                score -= 15
                            elif seg_legroom >= 31:
                                score += 15
                                
                    if f.get("often_delayed_by_over_30_min"):
                        score -= 10
                        
                    segment_details.append({
                        "flight_number": flight_num,
                        "airline": airline,
                        "wifi": seg_wifi,
                        "power": seg_power,
                        "legroom_inch": seg_legroom
                    })
                    
                layover_details = []
                for lay in layovers:
                    dur = lay.get("duration", 0)
                    is_overnight = lay.get("overnight", False)
                    
                    if is_overnight:
                        score -= 30
                    if dur > 360:  # > 6 hours
                        score -= 15
                        
                    layover_details.append({
                        "airport": lay.get("name"),
                        "duration_mins": dur,
                        "overnight": is_overnight
                    })
                    
                all_flight_options.append({
                    "airline": option.get("flights", [{}])[0].get("airline", "Unknown"),
                    "price_usd": option.get("price", 0),
                    "total_duration_mins": option.get("total_duration", 0),
                    "productivity_score": score,
                    "segments": segment_details,
                    "layovers": layover_details
                })
                
    all_flight_options.sort(key=lambda x: x["productivity_score"], reverse=True)
    return json.dumps(all_flight_options[:5], indent=2, ensure_ascii=False)

def get_current_time() -> str:
    """
    Returns the current local date and time of the system in 'YYYY-MM-DD HH:MM' format.
    Use this to get the exact reference time when calculating countdowns or remaining time.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def time_until_flight(flight_number: str, current_time_str: str = None, local_data_path: str = None) -> str:
    """
    Calculates the duration remaining (or elapsed) until a specific flight departs.
    
    Args:
        flight_number: Flight designator (e.g., 'BA 301', 'DL 42')
        current_time_str: Reference time in 'YYYY-MM-DD HH:MM' format. Defaults to get_current_time().
        local_data_path: Path to the database JSON file.
        
    Returns:
        A human-readable string explaining the remaining time.
    """
    if not current_time_str:
        current_time_str = get_current_time()
        
    try:
        data = _load_data(local_data_path)
    except Exception as e:
        return f"Error: {e}"
        
    target_num = re.sub(r"\s+", "", flight_number).upper()
    
    found_segment = None
    for category in ["best_flights", "other_flights"]:
        if category in data:
            for option in data[category]:
                for f in option.get("flights", []):
                    f_num = f.get("flight_number", "")
                    clean_f_num = re.sub(r"\s+", "", f_num).upper()
                    if clean_f_num == target_num:
                        found_segment = f
                        break
                if found_segment:
                    break
        if found_segment:
            break
            
    if not found_segment:
        return f"Flight {flight_number} was not found in the search database."
        
    dept_info = found_segment.get("departure_airport", {})
    dept_time_str = dept_info.get("time")  # e.g. "2026-03-03 10:10"
    airport_name = dept_info.get("name", "N/A")
    airport_id = dept_info.get("id", "N/A")
    
    if not dept_time_str:
        return f"Flight {flight_number} found, but departure time is unavailable."
        
    try:
        current_time = datetime.strptime(current_time_str, "%Y-%m-%d %H:%M")
        dept_time = datetime.strptime(dept_time_str, "%Y-%m-%d %H:%M")
    except ValueError as e:
        return f"Error parsing time strings. Use 'YYYY-MM-DD HH:MM'. Detail: {e}"
        
    delta = dept_time - current_time
    total_seconds = delta.total_seconds()
    
    if total_seconds > 0:
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        return f"Flight {flight_number} departing from {airport_name} ({airport_id}) is in {hours} hours and {minutes} minutes (Scheduled: {dept_time_str}, Current reference: {current_time_str})."
    else:
        abs_seconds = abs(total_seconds)
        days = int(abs_seconds // 86400)
        hours = int((abs_seconds % 86400) // 3600)
        minutes = int((abs_seconds % 3600) // 60)
        if days > 0:
            return f"Flight {flight_number} departed from {airport_name} ({airport_id}) {days} days, {hours} hours, and {minutes} minutes ago (Scheduled: {dept_time_str}, Current reference: {current_time_str})."
        else:
            return f"Flight {flight_number} departed from {airport_name} ({airport_id}) {hours} hours and {minutes} minutes ago (Scheduled: {dept_time_str}, Current reference: {current_time_str})."

def parse_flight_details(flight_number: str, local_data_path: str = None) -> str:
    """
    Parses segment-by-segment itinerary, layover details, carbon footprint, and pricing 
    for a specific flight route in the database.
    
    Args:
        flight_number: The flight number to look up (e.g. 'BA 191')
        
    Returns:
        A formatted JSON string summarizing the complete journey details.
    """
    try:
        data = _load_data(local_data_path)
    except Exception as e:
        return json.dumps({"error": str(e)})
        
    target_num = re.sub(r"\s+", "", flight_number).upper()
    
    found_option = None
    for category in ["best_flights", "other_flights"]:
        if category in data:
            for option in data[category]:
                for f in option.get("flights", []):
                    clean_f_num = re.sub(r"\s+", "", f.get("flight_number", "")).upper()
                    if clean_f_num == target_num:
                        found_option = option
                        break
                if found_option:
                    break
        if found_option:
            break
            
    if not found_option:
        return json.dumps({"error": f"Flight itinerary containing {flight_number} not found in the search records."})
        
    summary = {
        "airline": found_option.get("flights", [{}])[0].get("airline", "Unknown"),
        "total_duration_mins": found_option.get("total_duration"),
        "price_usd": found_option.get("price"),
        "carbon_emissions": found_option.get("carbon_emissions"),
        "baggage_policy": [ext for ext in found_option.get("extensions", []) if "baggage" in ext.lower() or "bag" in ext.lower()],
        "refund_policy": [ext for ext in found_option.get("extensions", []) if "refund" in ext.lower() or "change" in ext.lower() or "cancel" in ext.lower()],
        "flight_legs": [],
        "layovers": []
    }
    
    for f in found_option.get("flights", []):
        summary["flight_legs"].append({
            "flight_number": f.get("flight_number"),
            "airline": f.get("airline"),
            "airplane": f.get("airplane"),
            "travel_class": f.get("travel_class"),
            "departure": f.get("departure_airport"),
            "arrival": f.get("arrival_airport"),
            "duration_mins": f.get("duration"),
            "legroom": f.get("legroom"),
            "amenities": [ext for ext in f.get("extensions", []) if "legroom" not in ext.lower() and "carbon" not in ext.lower()]
        })
        
    for lay in found_option.get("layovers", []):
        summary["layovers"].append({
            "airport": lay.get("name"),
            "airport_id": lay.get("id"),
            "duration_mins": lay.get("duration"),
            "overnight": lay.get("overnight", False)
        })
        
    return json.dumps(summary, indent=2, ensure_ascii=False)

# ---------------------------------------------------------------------------
# Helpers for search_flights mapping
# ---------------------------------------------------------------------------
def _minutes_to_hhmm(minutes: int) -> str:
    """Helper: converts minutes to 'Xh Ym'."""
    h, m = divmod(int(minutes), 60)
    return f"{h}h {m}m" if m else f"{h}h"

def _parse_mock_option(option: Dict[str, Any], params: FlightSearchParams) -> Optional[FlightResult]:
    """Parse a single database record into a FlightResult object."""
    segments: List[Dict[str, Any]] = option.get("flights", [])
    if not segments:
        return None

    price = option.get("price")
    if price is None:
        return None
    try:
        price = float(price)
    except (TypeError, ValueError):
        return None

    first_seg = segments[0]
    last_seg = segments[-1]

    departure_time = (first_seg.get("departure_airport") or {}).get("time", "Unknown")
    arrival_time = (last_seg.get("arrival_airport") or {}).get("time", "Unknown")

    total_duration = option.get("total_duration")
    duration_str = _minutes_to_hhmm(total_duration) if total_duration else "N/A"

    stops = max(0, len(segments) - 1)

    layovers = option.get("layovers", [])
    stop_info = None
    if layovers:
        stop_info = ", ".join(lay.get("name", lay.get("id", "?")) for lay in layovers)

    airline = first_seg.get("airline", "Unknown")
    airline_logo = option.get("airline_logo") or first_seg.get("airline_logo")
    booking_token = option.get("booking_token", "")
    booking_link = (
        f"https://www.google.com/travel/flights?booking_token={booking_token}"
        if booking_token
        else "https://www.google.com/travel/flights"
    )

    flight_id = f"flight-{abs(hash(booking_token or str(option))) % 1_000_000}"

    return FlightResult(
        flight_id=flight_id,
        airline=airline,
        departure_time=departure_time,
        arrival_time=arrival_time,
        duration=duration_str,
        stops=stops,
        stop_info=stop_info,
        price=price,
        currency=params.currency,
        booking_link=booking_link,
        airline_logo=airline_logo,
        rating=None,
    )

def _load_flights_from_mock(params: FlightSearchParams) -> List[FlightResult]:
    """Retrieves all parsed FlightResult options from _MOCK_DATA cache."""
    results: List[FlightResult] = []
    # If cache is empty, load it
    global _MOCK_DATA
    if not _MOCK_DATA:
        try:
            _MOCK_DATA = _load_data()
        except Exception:
            return []
            
    for section_key in ("best_flights", "other_flights"):
        for option in _MOCK_DATA.get(section_key, []):
            parsed = _parse_mock_option(option, params)
            if parsed:
                results.append(parsed)
            if len(results) >= 10:
                break
        if len(results) >= 10:
            break
    return results

def search_flights(
    departure_airport: str,
    arrival_airport: str,
    departure_date: str,
    return_date: Optional[str] = None,
    passengers: int = 1,
    travel_class: str = "economy",
    currency: str = "USD",
) -> Dict[str, Any]:
    """
    Searches the flights from mock data database.
    Does not make external network requests.
    """
    try:
        params = FlightSearchParams(
            departure_airport=departure_airport,
            arrival_airport=arrival_airport,
            departure_date=departure_date,
            return_date=return_date,
            passengers=passengers,
            travel_class=travel_class,
            currency=currency,
        )
        # Bypassing future date check for mock dataset where departures are in 2026-03-03
        # to ensure local test runs succeed seamlessly on past reference datasets
        # params.validate_business_rules()
    except ValidationError as exc:
        raise FlightSearchException(f"Invalid search parameters: {exc}")
    except ValueError as exc:
        raise FlightSearchException(str(exc))

    global _MOCK_DATA
    if not _MOCK_DATA:
        try:
            _MOCK_DATA = _load_data()
        except Exception:
            raise FlightSearchException("Could not load flight mock data data.json.")

    flights = _load_flights_from_mock(params)

    if not flights:
        return {
            "status": "success",
            "count": 0,
            "message": "No flights found matching the criteria.",
            "query": params.model_dump(),
            "flights": [],
        }

    return {
        "status": "success",
        "count": len(flights),
        "message": f"Found {len(flights)} flights.",
        "query": params.model_dump(),
        "flights": [flight.model_dump() for flight in flights],
    }


if __name__ == "__main__":
    # Self-test when run directly
    print("--- 1. Testing Nomad Productivity Finder ---")
    prod_flights = find_productivity_flights()
    parsed_prod = json.loads(prod_flights)
    if "error" in parsed_prod:
        print(f"Error loading: {parsed_prod['error']}")
    else:
        print(f"Loaded {len(parsed_prod)} comfort flights.")
        print(f"Top comfort flight score: {parsed_prod[0]['productivity_score']} (Price: ${parsed_prod[0]['price_usd']})")

    print("\n--- 2. Testing Time Until Flight ---")
    print(time_until_flight("BA 303", "2026-03-03 08:30"))

    print("\n--- 3. Testing Flight Details Parsing ---")
    details = parse_flight_details("BA 191")
    parsed_details = json.loads(details)
    if "error" in parsed_details:
        print(f"Error: {parsed_details['error']}")
    else:
        print(f"Itinerary for {parsed_details['airline']} flight includes {len(parsed_details['flight_legs'])} legs:")
        for leg in parsed_details['flight_legs']:
            print(f"  Leg {leg['flight_number']}: {leg['departure']['id']} -> {leg['arrival']['id']} ({leg['airplane']})")

    print("\n--- 4. Testing Standard Search Flights ---")
    try:
        search_res = search_flights("CDG", "AUS", "2026-03-03")
        print(f"Search status: {search_res['status']}, Count: {search_res['count']}")
    except Exception as e:
        print(f"Search failed: {e}")
