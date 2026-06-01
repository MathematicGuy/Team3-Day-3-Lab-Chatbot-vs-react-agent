# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Nguyễn Khánh Toàn
- **Student ID**: 2A202600XXX
- **Date**: 2026-06-01

---

## I. Technical Contribution (15 Points)

My main contribution was implementing comprehensive data validation and intelligent flight comparison tools for the ReAct agent. These tools form the data layer that ensures passenger information is valid and helps the agent make intelligent flight recommendations.

- **Modules Implemented**
  - `src/tools/user_info_tools.py` (465 lines)
  - `src/tools/flight_tools.py` (238 lines)
  - `src/tools/flight_comparison.py` (300 lines)

- **Code Highlights**
  - **User Info Validation**: Implemented 5 Pydantic v2 models (PersonalInfo, AddressInfo, TravelPreferences, UserProfile, UserInfoException) with declarative field validators for email regex, phone format, and date validation.
  - **Structured Data Collection**: Created 6 functions (`collect_personal_info`, `collect_address_info`, `collect_travel_preferences`, `create_user_profile`, `validate_all_user_info`, `format_user_info_display`) that follow consistent `{status, message, data}` response pattern for reliable error handling.
  - **Flight Data Parsing**: Implemented `search_flights()` with IATA code validation, date format checking, and flexible data source (real file or sample fallback) that returns normalized flight objects with booking tokens.
  - **Intelligent Comparison**: Built `compare_flights()` with 5 sorting strategies (price, duration, stops, rating, recommended) and a weighted recommendation algorithm that balances multiple criteria.
  - **Recommendation Scoring**: Developed scoring algorithm:
    ```
    RCM Score = price_score(40%) + duration_score(30%) + 
                stops_score(20%) + rating_score(10%)
    ```
    This balances cost, travel time, and convenience without requiring user input.
  - **Display Formatting**: Added `format_user_info_display()` and ASCII table generation for user-friendly CLI output with Vietnamese localization (👤, 🏠, ✈️ emojis).

- **Documentation**
  - User info tools validate data at collection point to prevent invalid data from propagating downstream.
  - Flight search returns structured objects with booking tokens to enable hold operations.
  - Comparison scoring makes transparent recommendations by breaking down individual factor scores.
  - All functions include docstrings with example usage and return schema documentation.

---

## II. Debugging Case Study (10 Points)

- **Problem Description**

During integration testing, the agent attempted to create a user profile before collecting all required information. The PersonalInfo model requires `passenger_name` (mandatory), but the agent tried to create a profile with only email and phone, causing a validation error that wasn't clearly communicated to the user.

- **Log Source**

From test execution:

```json
{
  "event": "VALIDATION_ERROR",
  "data": {
    "function": "create_user_profile",
    "error": "ValidationError: 1 validation error for PersonalInfo\npassenger_name\n  Field required (type=missing)"
  }
}
```

- **Diagnosis**

The issue appeared in `create_user_profile()` when it tried to instantiate `PersonalInfo(**personal_info)` without checking if required fields existed first. The raw Pydantic error was technical and not user-friendly. The root cause was that the agent followed an order:

```
collect_email → collect_phone → create_profile (missing name!)
```

Instead of:

```
collect_name (required) → collect_email → collect_phone → create_profile
```

This shows that tool order matters when dealing with required vs. optional fields. The user didn't know `passenger_name` was mandatory until the validation failed.

- **Solution**

I made two improvements:

1. **Enhanced Error Messages**: Modified `collect_personal_info()` to provide clear field-level error messages:

```python
errors = [
    {"field": error["loc"][0], "message": error["msg"]}
    for error in exc.errors()
]
error_msg = "\n".join(f"  • {e['field']}: {e['message']}" for e in errors)
return {
    "status": "error",
    "message": f"❌ Thông tin không hợp lệ:\n{error_msg}",
    "personal_info": None,
}
```

2. **Batch Validation Function**: Added `validate_all_user_info()` to check all collected data simultaneously and return a validation summary:

```python
{
    "status": "success" | "error",
    "is_valid": True | False,
    "messages": [...],
    "validation_summary": {
        "personal_info": {"valid": bool, "message": str},
        "address_info": {"valid": bool, "message": str},
        "travel_preferences": {"valid": bool, "message": str}
    }
}
```

This allows the agent to collect all info first, then validate once, providing a complete picture of what's missing or invalid.

---

## III. Personal Insights: Data Validation in Agents (10 Points)

1. **Reliability Through Validation**

Unlike chatbots that can hand-wave answers, agents must work with real data. The ReAct agent depends on tools returning valid, structured data. If user info is incomplete or malformed, downstream tools (flight search, booking, invoice generation) fail silently or produce nonsensical results. By enforcing Pydantic validation upfront, I prevented "garbage in, garbage out" scenarios.

2. **Transparency in Recommendations**

The weighted scoring algorithm in `compare_flights()` is more trustworthy than a chatbot's "I recommend this flight" because:
- **Explainable**: Users can see how price, duration, stops, and rating each contributed
- **Reproducible**: Same inputs always produce same ranking
- **Adjustable**: Weights can be tuned for different user segments (budget travelers vs. time-sensitive)

A chatbot might recommend based on biased training data or hallucinated preferences. The agent's scoring is data-driven.

3. **Observation Quality Matters**

The observation from `search_flights()` is critical. If the data file is stale or incomplete, the agent gets poor quality observations. The tool returns booking tokens and structured flight objects, not human-readable text. This structure is essential for downstream tools like `hold_flight()`. A chatbot would just describe flights in prose and lose the actionable details.

4. **Field Optionality Complexity**

I learned that marking fields as optional is different from marking them as unimportant. Address and travel preferences are optional in UserProfile, but `passenger_name` is mandatory. This requires clear documentation and upfront validation. The agent's system prompt must tell it which fields to collect first vs. later.

---

## IV. Future Improvements (5 Points)

- **Real Data Integration**

Currently using mock data. Next step: connect to real flight APIs (Skyscanner, Google Flights, Amadeus) and validate against live pricing and availability.

- **Preference Learning**

Track user choices over time to personalize recommendation weights. If a user always picks the cheapest option, increase the price weight. If they book the fastest flight, increase duration weight.

- **Advanced Comparison**

Add carbon emissions scoring, airline safety rating, seat comfort metrics, and baggage allowance comparison. The weighted scoring framework can accommodate new factors easily.

- **Caching Strategy**

Cache `search_flights()` results by route + date to avoid repeated API calls. This reduces latency and API costs when multiple users or turns query the same route.

- **Validation Hooks**

Add pre-hooks (validate input before tool call) and post-hooks (validate output before returning to agent) to catch data quality issues early.

- **Internationalization**

Currently Vietnamese-localized. Extend to multi-language support (English, Chinese, Japanese) for broader accessibility.

- **Error Recovery**

When validation fails, the agent should ask the user to fill missing fields interactively instead of just reporting errors. This would feel more conversational.

---

## V. Code Quality Observations

- ✅ **Type Safety**: Full type hints in all functions (Python typing module)
- ✅ **DRY Principle**: Shared utility functions (`_minutes_to_hhmm`, `_normalize_airport`, `_parse_option`)
- ✅ **Modularity**: Tools are independently callable and testable
- ✅ **Localization**: Vietnamese field names and error messages for user base
- ✅ **Pattern Consistency**: Status pattern `{status, message, data}` used across all functions

**Code Metrics**:
- Total Lines: 1,003
- Functions: 15 public + 8 private
- Models: 5 Pydantic classes
- Test Coverage: 5 manual test cases in `flight_comparison.py` main block

