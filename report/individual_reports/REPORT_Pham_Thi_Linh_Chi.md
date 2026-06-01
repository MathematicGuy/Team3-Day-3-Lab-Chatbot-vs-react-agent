# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Phạm Thị Linh Chi
- **Student ID**:  2A202600748
- **Date**: 2026-06-01

---

## I. Technical Contribution (15 Points)

My main contribution was implementing and improving the ReAct agent for the **Flight Search and Hold Agent** topic. The goal of this agent is to search flight options and create a temporary hold only when the user clearly asks for it. A hold is treated as a safe simulation, not a real paid booking.

- **Modules Implemented**
  - `src/agent/agent.py`
  - `src/tools/flight_tools.py`
  - `src/tools/hold_tools.py`

- **Code Highlights**
  - Completed the ReAct loop in `ReActAgent.run()`, including LLM response generation, action parsing, tool execution, observation appending, and final answer detection.
  - Added support for function-call style actions such as:

```text
Action: search_flights(departure_airport="CDG", arrival_airport="AUS", departure_date="2026-03-03", currency="USD")
```

  - Added a safer tool execution layer that resolves tools from `self.tools` and from tool modules such as `flight_tools` and `hold_tools`.
  - Implemented `search_flights`, which returns structured flight options from local mock data.
  - Implemented `hold_flight`, which creates a temporary hold code and expiry time without processing payment.
  - Added telemetry events for `AGENT_START`, `LLM_RESPONSE`, `TOOL_EXECUTE`, `PARSER_ERROR`, `UNKNOWN_TOOL`, `TOOL_ERROR`, and `AGENT_END`.

- **Documentation**
  - The ReAct loop uses the format `Thought -> Action -> Observation -> Final Answer`.
  - `search_flights` provides real evidence for flight options, including price, route, duration, and booking token.
  - `hold_flight` depends on the `booking_token` returned by `search_flights`, which prevents the agent from holding a flight that was never found.

---

## II. Debugging Case Study (10 Points)

- **Problem Description**

During testing, the agent attempted to call `hold_flight` before running `search_flights`. This is a natural failure in a flight hold system because a temporary hold requires a valid `booking_token` or `flight_id` from a previous search result.

- **Log Source**

From `logs/2026-06-01.log`:

```json
{
  "event": "TOOL_EXECUTE",
  "data": {
    "tool": "hold_flight",
    "args": "passenger_count=\"1\", hold_minutes=\"15\"",
    "observation": "{\"status\": \"failed\", \"error_code\": \"missing_booking_reference\", \"message\": \"A booking_token or flight_id from search_flights is required before creating a hold.\"}"
  }
}
```

- **Diagnosis**

The failure was not caused by the API or the hold tool itself. The tool behaved correctly by rejecting a hold request without a booking reference. The root cause was that the agent tried to take an action without first grounding the decision in a flight search observation.

This shows why ReAct agents need strong tool sequencing rules. For this domain, `hold_flight` must never be called before `search_flights`, because the booking token is created by the search step.

- **Solution**

I updated the system prompt and tool design so the agent follows this rule:

```text
Always call search_flights before hold_flight.
```

I also added validation inside `hold_flight`. If no `booking_token` or `flight_id` is provided, the tool returns a structured failure:

```json
{
  "status": "failed",
  "error_code": "missing_booking_reference"
}
```

This makes the failure observable in telemetry and allows the agent to recover by explaining the issue or asking for missing flight search information.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

1. **Reasoning**

The `Thought` step helped the agent break the user request into smaller actions. A normal chatbot may directly answer with guessed flight information, but the ReAct agent first identifies what information is missing, calls the correct tool, and then uses the observation to decide the next step.

2. **Reliability**

The agent can perform worse than a chatbot for simple questions because it may take extra steps and increase latency. For example, if the user only asks a general travel question, a chatbot can answer immediately, while an agent might overuse tools. The agent also depends on parser quality and tool availability, so malformed actions or unavailable tools can cause failures.

3. **Observation**

Observation is the most important difference between a chatbot and an agent. The chatbot relies mostly on model knowledge, while the ReAct agent receives external feedback from tools. In this lab, the observation from `search_flights` gave the agent actual flight options and booking tokens. The observation from `hold_flight` confirmed whether a temporary hold succeeded or failed.

---

## IV. Future Improvements (5 Points)

- **Scalability**

Use asynchronous tool execution and caching for flight search results. This would reduce latency and avoid repeated calls for the same route and date.

- **Safety**

Add a `check_hold_policy` tool before `hold_flight`. This would verify whether a fare supports temporary hold and prevent invalid actions. The agent should also continue to avoid payment processing and sensitive passenger document collection.

- **Performance**

Add better ranking logic for flight options, such as cheapest, fastest, fewest layovers, lowest carbon emission, or best comfort score. This would help the agent select better flights instead of simply choosing the first or cheapest result.

- **Production Readiness**

In a production system, I would connect the search tool to a real flight API, store hold records in a database, add retry logic for expired tokens, and monitor natural flight system errors such as `price_changed`, `sold_out`, `booking_token_expired`, and API timeouts.
