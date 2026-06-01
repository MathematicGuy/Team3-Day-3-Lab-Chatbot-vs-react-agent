import json
import re
from typing import Any, Dict, List, Optional
from flight_tools import search_flights


def compare_flights(
    departure_airport: str,
    arrival_airport: str,
    departure_date: str,
    sort_by: str = "price",
) -> str:
    """
    Compares multiple flights with a sortable table.

    Args:
        departure_airport: IATA code of departure airport (e.g., 'CDG')
        arrival_airport: IATA code of arrival airport (e.g., 'AUS')
        departure_date: Date in YYYY-MM-DD format
        sort_by: Sort criteria - 'price', 'duration', 'stops', 'rating', 'recommended' (default: 'price')

    Returns:
        A formatted table comparing flights with recommendations
    """
    try:
        search_result = search_flights(departure_airport, arrival_airport, departure_date)
        if search_result["count"] == 0:
            return json.dumps({"status": "no_flights", "message": "No flights found"})

        flights = search_result["flights"]
    except Exception as e:
        return json.dumps({"error": str(e)})

    comparison_data = []

    for flight in flights:
        duration_str = flight.get("duration", "0h")
        duration_match = re.search(r"(\d+)h\s*(\d+)?m?", duration_str)
        duration_mins = 0
        if duration_match:
            hours = int(duration_match.group(1))
            minutes = int(duration_match.group(2) or 0)
            duration_mins = hours * 60 + minutes

        price = flight.get("price", 0)
        stops = flight.get("stops", 0)
        rating = flight.get("rating", 3.5)

        max_price = max(f["price"] for f in flights) if flights else 1
        max_duration = max(
            int(re.search(r"(\d+)h", f.get("duration", "0h")).group(1) or 0) * 60
            + int(re.search(r"(\d+)m", f.get("duration", "0h")).group(1) or 0)
            for f in flights
        ) if flights else 1

        price_score = (price / max_price) * 40 if max_price else 0
        duration_score = (duration_mins / max_duration) * 30 if max_duration else 0
        stops_score = stops * 20
        rating_score = (5 - (rating or 3.5)) * 10

        rcm_score = price_score + duration_score + stops_score + rating_score

        comparison_data.append({
            "flight_id": flight.get("flight_id"),
            "airline": flight.get("airline", "Unknown"),
            "departure": flight.get("departure_time", "Unknown"),
            "arrival": flight.get("arrival_time", "Unknown"),
            "duration": flight.get("duration", "N/A"),
            "duration_mins": duration_mins,
            "stops": stops,
            "stop_info": flight.get("stop_info", "Direct"),
            "price": price,
            "rating": rating,
            "rcm_score": rcm_score,
            "booking_link": flight.get("booking_link", ""),
        })

    if sort_by == "price":
        comparison_data.sort(key=lambda x: x["price"])
    elif sort_by == "duration":
        comparison_data.sort(key=lambda x: x["duration_mins"])
    elif sort_by == "stops":
        comparison_data.sort(key=lambda x: x["stops"])
    elif sort_by == "rating":
        comparison_data.sort(key=lambda x: x["rating"], reverse=True)
    elif sort_by == "recommended":
        comparison_data.sort(key=lambda x: x["rcm_score"])
    else:
        comparison_data.sort(key=lambda x: x["price"])

    table_rows = [
        "+-----+-----------+----------+----------+----------+-------+-------+",
        "| Pos | Airline   | Depart   | Arrival  | Duration | Price | RCM   |",
        "+-----+-----------+----------+----------+----------+-------+-------+"
    ]

    for idx, flight in enumerate(comparison_data, 1):
        airline = flight["airline"][:9]
        departure = flight["departure"][:8] if flight["departure"] != "Unknown" else "Unknown"
        arrival = flight["arrival"][:8] if flight["arrival"] != "Unknown" else "Unknown"
        duration = flight["duration"][:8]
        stops = f"{flight['stops']}" if flight["stops"] > 0 else "Direct"
        price = f"${flight['price']:.0f}"
        rating = f"{flight['rating']:.1f}" if flight['rating'] else "N/A"

        rcm_mark = "YES" if idx == 1 and sort_by == "recommended" else ""

        row = f"| {idx:<3} | {airline:<9} | {departure:<8} | {arrival:<8} | {duration:<8} | {price:<5} | {rcm_mark:<5} |"
        table_rows.append(row)

    table_rows.append("+-----+-----------+----------+----------+----------+-------+-------+")

    table_text = "\n".join(table_rows)

    summary = {
        "status": "success",
        "sort_by": sort_by,
        "total_flights": len(comparison_data),
        "recommended_flight": comparison_data[0] if comparison_data else None,
        "table": table_text,
        "all_flights": comparison_data
    }

    return json.dumps(summary, indent=2, ensure_ascii=False)


def format_comparison_table(
    flights: List[Dict[str, Any]],
    sort_by: str = "price"
) -> str:
    """
    Format a list of flights into a comparison table (ASCII).

    Args:
        flights: List of flight dictionaries
        sort_by: Sorting criteria

    Returns:
        Formatted ASCII table string
    """
    if not flights:
        return "No flights to compare"

    comparison_data = []

    for flight in flights:
        duration_str = flight.get("duration", "0h")
        duration_match = re.search(r"(\d+)h\s*(\d+)?m?", duration_str)
        duration_mins = 0
        if duration_match:
            hours = int(duration_match.group(1))
            minutes = int(duration_match.group(2) or 0)
            duration_mins = hours * 60 + minutes

        price = flight.get("price", 0)
        stops = flight.get("stops", 0)
        rating = flight.get("rating", 3.5)

        comparison_data.append({
            "flight_id": flight.get("flight_id"),
            "airline": flight.get("airline", "Unknown"),
            "departure": flight.get("departure_time", "Unknown"),
            "arrival": flight.get("arrival_time", "Unknown"),
            "duration": flight.get("duration", "N/A"),
            "duration_mins": duration_mins,
            "stops": stops,
            "price": price,
            "rating": rating,
        })

    if sort_by == "price":
        comparison_data.sort(key=lambda x: x["price"])
    elif sort_by == "duration":
        comparison_data.sort(key=lambda x: x["duration_mins"])
    elif sort_by == "stops":
        comparison_data.sort(key=lambda x: x["stops"])
    elif sort_by == "rating":
        comparison_data.sort(key=lambda x: x["rating"], reverse=True)

    table_rows = [
        "+-----+-----------+----------+----------+----------+-------+",
        "| Pos | Airline   | Depart   | Arrival  | Duration | Price |",
        "+-----+-----------+----------+----------+----------+-------+"
    ]

    for idx, flight in enumerate(comparison_data, 1):
        airline = flight["airline"][:9]
        departure = flight["departure"][:8] if flight["departure"] != "Unknown" else "Unknown"
        arrival = flight["arrival"][:8] if flight["arrival"] != "Unknown" else "Unknown"
        duration = flight["duration"][:8]
        price = f"${flight['price']:.0f}"

        row = f"| {idx:<3} | {airline:<9} | {departure:<8} | {arrival:<8} | {duration:<8} | {price:<5} |"
        table_rows.append(row)

    table_rows.append("+-----+-----------+----------+----------+----------+-------+")
    return "\n".join(table_rows)


def get_recommendation(
    flights: List[Dict[str, Any]],
    weights: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Get the best recommended flight based on weighted criteria.

    Args:
        flights: List of flight dictionaries
        weights: Custom weight dict with keys: 'price', 'duration', 'stops', 'rating'
                Default: {'price': 0.4, 'duration': 0.3, 'stops': 0.2, 'rating': 0.1}

    Returns:
        Dictionary with recommended flight and its score
    """
    if not flights:
        return {"error": "No flights to analyze"}

    if weights is None:
        weights = {
            "price": 0.4,
            "duration": 0.3,
            "stops": 0.2,
            "rating": 0.1
        }

    scored_flights = []

    for flight in flights:
        duration_str = flight.get("duration", "0h")
        duration_match = re.search(r"(\d+)h\s*(\d+)?m?", duration_str)
        duration_mins = 0
        if duration_match:
            hours = int(duration_match.group(1))
            minutes = int(duration_match.group(2) or 0)
            duration_mins = hours * 60 + minutes

        price = flight.get("price", 0)
        stops = flight.get("stops", 0)
        rating = flight.get("rating", 3.5)

        max_price = max(f["price"] for f in flights) if flights else 1
        max_duration = max(
            int(re.search(r"(\d+)h", f.get("duration", "0h")).group(1) or 0) * 60
            + int(re.search(r"(\d+)m", f.get("duration", "0h")).group(1) or 0)
            for f in flights
        ) if flights else 1

        price_score = (price / max_price) if max_price else 0
        duration_score = (duration_mins / max_duration) if max_duration else 0
        stops_score = (stops / max(f["stops"] for f in flights)) if flights else 0
        rating_score = (5 - rating) / 5  # Inverted: lower is better

        total_score = (
            price_score * weights.get("price", 0.4) +
            duration_score * weights.get("duration", 0.3) +
            stops_score * weights.get("stops", 0.2) +
            rating_score * weights.get("rating", 0.1)
        )

        scored_flights.append({
            "flight": flight,
            "score": total_score,
            "breakdown": {
                "price_score": price_score,
                "duration_score": duration_score,
                "stops_score": stops_score,
                "rating_score": rating_score
            }
        })

    best = min(scored_flights, key=lambda x: x["score"])
    return {
        "recommended_flight": best["flight"],
        "score": best["score"],
        "breakdown": best["breakdown"]
    }


if __name__ == "__main__":
    print("--- Testing Flight Comparison Tool ---\n")

    print("1. Compare by recommended:")
    result = compare_flights("CDG", "AUS", "2026-03-03", sort_by="recommended")
    parsed = json.loads(result)
    if "error" not in parsed:
        print(parsed["table"])
        print(f"\nRecommended flight: {parsed['recommended_flight']['airline']} - ${parsed['recommended_flight']['price']}")

    print("\n\n2. Compare by price:")
    result = compare_flights("CDG", "AUS", "2026-03-03", sort_by="price")
    parsed = json.loads(result)
    if "error" not in parsed:
        print(parsed["table"])

    print("\n\n3. Compare by duration:")
    result = compare_flights("CDG", "AUS", "2026-03-03", sort_by="duration")
    parsed = json.loads(result)
    if "error" not in parsed:
        print(parsed["table"])
