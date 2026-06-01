# ✈️ Flight Carnegie ReAct Agent — Workflow Documentation

> **Source:** [`src/agent/agent.py`](./src/agent/agent.py)  
> **Class:** `ReActAgent`  
> **Pattern:** ReAct (Reasoning + Acting) — Thought → Action → Observation loop

---

## Overview

The **Flight Carnegie ReAct Agent** is a conversational AI agent that helps users **search for flights** and **place temporary holds** on selected itineraries. It follows the **ReAct (Reason + Act)** paradigm: the LLM reasons about what to do next, issues a structured action (tool call), and receives an observation from the environment before proceeding.

---

## Architecture at a Glance

```
User Input
    │
    ▼
┌─────────────────────────────────────────────────────┐
│                   ReActAgent.run()                  │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │         Conversation Context (string)        │   │
│  └──────────────────┬──────────────────────────┘   │
│                     │                               │
│          ┌──────────▼──────────┐                   │
│          │  LLM (FallbackChain) │  ← System Prompt  │
│          └──────────┬──────────┘                   │
│                     │ LLM Response                  │
│          ┌──────────▼──────────────────────────┐   │
│          │          Parse Response              │   │
│          │  ┌──────────────┐  ┌──────────────┐ │   │
│          │  │ Final Answer?│  │   Action?    │ │   │
│          │  └──────┬───────┘  └──────┬───────┘ │   │
│          └─────────│────────────────│──────────┘   │
│                    │                │               │
│            Return  │         ┌──────▼──────┐       │
│            answer  │         │ Execute Tool│       │
│                    │         └──────┬──────┘       │
│                    │                │ Observation   │
│                    │         Append to context      │
│                    │         (next step)            │
│                    │                │               │
│          ┌─────────▼────────────────▼──────────┐   │
│          │     Loop (max_steps = 5 default)     │   │
│          └─────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## Step-by-Step Workflow

### 1. 🚀 Agent Start — `run(user_input)`

```
User Input → conversation_context = "User Request: <input>\n"
           → logger.log_event("AGENT_START", ...)
```

The agent initialises the **conversation context** as a plain string that accumulates the full dialogue history (prompts + observations). A structured event is emitted to the telemetry logger.

---

### 2. 🤖 LLM Call — Thought Generation

```
LLM.generate(
    prompt        = conversation_context,
    system_prompt = get_system_prompt()
)
→ content (string)
```

The **system prompt** defines the agent's identity, its rules, and the exact `Thought / Action / Final Answer` format the LLM must follow.

**Key constraints injected via system prompt:**
| Rule | Purpose |
|---|---|
| Use only listed tools | Prevent hallucinated tool names |
| Never invent flight data | Grounding constraint |
| Always call `search_flights` before `hold_flight` | Ordered dependency |
| Ask clarification if origin/destination/date missing | Safety guardrail |
| Never process payments or collect sensitive data | Compliance boundary |

---

### 3. 🔍 Parse LLM Response — Two Branches

The raw LLM output is inspected with regex:

#### Branch A — `Final Answer:` detected
```python
re.search(r"Final Answer:\s*(.*)", content, re.DOTALL)
→ logger.log_event("AGENT_END", {"status": "success"})
→ return final_answer
```
The loop exits immediately and the clean answer is returned to the caller.

#### Branch B — `Action: tool_name(args)` detected
```python
re.search(r"Action:\s*([a-zA-Z0-9_]+)(?:\((.*)\))?", content)
→ tool_name, tool_args extracted
→ _execute_tool(tool_name, tool_args)
→ conversation_context += f"\n{content}\nObservation: {observation}\n"
```
The tool result (observation) is appended back into the conversation context, and the loop continues.

#### Fallback — Neither pattern found
```python
→ logger.log_event("AGENT_END", {"status": "no_action_fallback"})
→ return content  (raw LLM content treated as final answer)
```

---

### 4. 🔧 Dynamic Tool Execution — `_execute_tool(tool_name, args_str)`

The agent features a highly robust, fault-tolerant dynamic execution system. When the LLM emits `Action: tool_name(args)`, the agent handles execution through a two-stage process:

```
           LLM Output Action: tool_name(args_str)
                           │
                           ▼
             ┌───────────────────────────┐
             │     _resolve_tool()       │
             └─────────────┬─────────────┘
                           │
      ┌────────────────────┴────────────────────┐
      ▼                                         ▼
[Injected Definitions]                [Dynamic Module Imports]
- self.tools[].function               Check modules in order:
                                      1. src.tools.flight_tools
                                      2. src.tools.hold_tools
                                      3. src.tools.invoice_tools
                                      4. src.tools.user_info_tools
                                      5. src.tools.flight_comparison
                           │
                           ▼
             ┌───────────────────────────┐
             │    _parse_tool_args()     │
             └─────────────┬─────────────┘
                           │ Parse & Coerce
                           ▼
             ┌───────────────────────────┐
             │       Target Callable     │
             └───────────────────────────┘
```

#### A. Smart Argument Parsing & Data Coercion
The agent features a smart parser (`_parse_tool_args`) to handle diverse LLM output variations seamlessly:
1. **JSON Object parsing**: e.g., `{"passenger_name": "Nguyen Van A"}` -> parsed to keyword arguments (`kwargs`).
2. **JSON Array parsing**: e.g., `["CDG", "AUS"]` -> parsed to positional arguments.
3. **Standard Python/CSV signature parsing**: Parses traditional pythonic call structures like `passenger_name="Nguyen Van A", expected_price=520.0`.
4. **Strict Type Coercion**: Automatically coerces string representations of boolean values (`"true"` / `"false"`), integer values (`"15"`), decimals/floats (`"520.0"`), and null states (`"none"` / `"null"`) into native Python types before invoking underlying methods. This ensures full compatibility with teammate Pydantic validation decorators and avoids runtime exceptions.

---

### 5. 🔁 Loop Termination & Safety Guardrails

| Condition | Status Logged | Agent Output & Action |
|---|---|---|
| `Final Answer:` found | `success` | Stops loop immediately; returns clean parsed answer to user. |
| No action & no final answer | `no_action_fallback` | Emits event, uses raw text output as final fallback response. |
| Steps >= `max_steps` (5) | `timeout` | Safely halts loop to prevent run-away loops and token depletion. |
| Exception during Tool call | `TOOL_ERROR` | Catches exceptions, returns the traceback as an **Observation** to let the agent self-correct. |

---

## 🛠️ The 5-Step Master Booking Pipeline (Multi-Tool Flow)

This is the flagship developer feature of our team's workspace: an end-to-end multi-tool flow where the ReAct Agent chains **five specialized tool classes** to satisfy a single user flight booking request.

```mermaid
graph TD
    User([User Request]) ── "compare & hold" ──> Step1[1. compare_flights]
    Step1 ── "booking_token" ──> Step2[2. collect_personal_info]
    Step2 ── "validate profile" ──> Step3[3. hold_flight]
    Step3 ── "hold_code" ──> Step4[4. generate_invoice]
    Step4 ── "invoice dict" ──> Step5[5. generate_invoice_pdf]
    Step5 ── "pdf_path" ──> Final([Final Answer + PDF on Disk])

    style Step1 fill:#2C3E50,stroke:#34495E,stroke-width:2px,color:#fff
    style Step2 fill:#2980B9,stroke:#3498DB,stroke-width:2px,color:#fff
    style Step3 fill:#27AE60,stroke:#2ECC71,stroke-width:2px,color:#fff
    style Step4 fill:#D35400,stroke:#E67E22,stroke-width:2px,color:#fff
    style Step5 fill:#8E44AD,stroke:#9B59B6,stroke-width:2px,color:#fff
```

1. **Flight Search & Comparison**: Agent compares flights using teammate `compare_flights` which ranks options via duration, layovers, stops, price, and recommended scores.
2. **Passenger Validation**: Agent collects traveler info and validates it through `collect_personal_info` using declarative Pydantic schemas.
3. **Simulated Hold Locking**: Upon validation success, agent calls `hold_flight` to secure a 15-minute temporary reservation.
4. **ASCII Invoice Drafting**: Agent invokes `generate_invoice` to build a clean text confirmation table summarizing segment times, base fares, tax, and a 5% service fee.
5. **Printable PDF Export**: Finally, agent executes `generate_invoice_pdf` to write a fully styled confirmation document (`.pdf`) into the workspace.

---

## 📋 Comprehensive Integrated Tool Suite (14 Tools)

Our combined system merges individual teammate contributions and custom nomad utilities into a unified, discoverable toolkit.

| Module File | Tool Name | Method Signature & Input Parameters | Key Feature & Problem Solved | Developer Attribution |
| :--- | :--- | :--- | :--- | :--- |
| `flight_comparison.py` | `compare_flights` | `departure_airport, arrival_airport, departure_date, sort_by` | Ranks flights using a dynamic weighted score (`40% price`, `30% duration`, `20% stops`, `10% rating`). | Nguyễn Khánh Toàn |
| `user_info_tools.py` | `collect_personal_info` | `passenger_name, passenger_email, passenger_phone, date_of_birth` | Performs strict regex format checks (Email & Phone length/prefix) to prevent transactional failures. | Nguyễn Khánh Toàn |
| `user_info_tools.py` | `collect_address_info` | `street, city, state, postal_code, country` | Declarative validation for traveler home addresses. | Nguyễn Khánh Toàn |
| `user_info_tools.py` | `collect_travel_preferences` | `preferred_airline, seat_preference, meal_preference, max_budget` | Captures passenger special dietary or seating requests. | Nguyễn Khánh Toàn |
| `user_info_tools.py` | `validate_all_user_info` | `user_data` | Performs a single batch validation pass over the entire passenger profile. | Nguyễn Khánh Toàn |
| `hold_tools.py` | `hold_flight` | `booking_token, passenger_count, hold_minutes, expected_price` | Temporarily locks seat allocations and outputs a mock reference code `HOLD-XXXXXXXX`. | Phạm Thị Linh Chi |
| `hold_tools.py` | `get_hold` | `hold_code` | Inspects current status, price metrics, and expiration timestamps for holds. | Phạm Thị Linh Chi |
| `invoice_tools.py` | `generate_invoice` | `passenger_name, flight_id, airline, departure_airport, arrival_airport, departure_time, arrival_time, duration, price_per_person, ...` | Automatically calculates subtotal, 5% service fee, total price, and outputs an ASCII text receipt. | Đinh Nhật Thành & Lưu Thiện Việt Cường |
| `invoice_tools.py` | `generate_invoice_pdf` | `invoice_result, output_path` | Generates a premium Helvetica PDF confirmation document in the workspace. | Đinh Nhật Thành & Lưu Thiện Việt Cường |
| `flight_tools.py` | `search_flights` | `departure_airport, arrival_airport, departure_date, currency` | Scans flights using a live mock JSON database. | Team 3 Shared |
| `flight_tools.py` | `find_productivity_flights` | `departure_airport, arrival_airport, departure_date` | Ranks flights by digital nomad criteria (Wi-Fi: `+30`, Legroom >30": `+15`, Layovers: `-30`). | Đinh Nhật Thành & Lưu Thiện Việt Cường |
| `flight_tools.py` | `parse_flight_details` | `flight_id` | Audit-checks refund rules, baggage allowance, and cancellation policies. | Nguyễn Khánh Toàn |
| `flight_tools.py` | `time_until_flight` | `departure_time` | Calculates real-time countdown to takeoff across timezones. | Phạm Thị Linh Chi |

---

## 📊 Telemetry Events

Every ReAct step is observed and logged in JSON format to `src.telemetry.logger` for analytical tracking:

| Telemetry Event | Injected Properties | Operational Significance |
|---|---|---|
| `AGENT_START` | `input`, `model` | Tracks start of agent execution loop. |
| `LLM_RESPONSE` | `content`, `latency_ms` | Audits text outputs, token counts, and LLM provider latency. |
| `TOOL_EXECUTE` | `tool`, `args`, `observation` | Records arguments and output responses for every successful step. |
| `TOOL_ERROR` | `tool`, `args`, `error` | Captures full stack traces and exceptions during dynamic execution. |
| `UNKNOWN_TOOL` | `tool` | Flags when LLM tries to call a hallucinated tool name. |
| `AGENT_END` | `steps`, `status` | Records total iteration cycles and exit status (`success` / `timeout`). |

---

## 🔁 Master Pipeline ReAct Loop — Real Trace

The following shows a comprehensive 5-step execution trace of the agent successfully chaining the master pipeline.

```
User: Search CDG to AUS flights on 2026-03-03. Validate passenger 'Nguyen Van A' (email: vana@email.com, phone: 0901234567). Put a 15-minute hold on the best option, and print a formatted invoice PDF to "invoice_BK-2F9A1B8C.pdf".

┌── Step 1 ─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Thought: First, I will compare the flights from CDG to AUS sorted by the recommended score.               │
│ Action: compare_flights(departure_airport="CDG", arrival_airport="AUS", departure_date="2026-03-03")      │
│ Observation: Found 2 options.                                                                             │
│ ┌───┬───────────────────┬─────────┬───────┬─────────┬──────────┬──────────┬──────────┐                    │
│ │ # │ Airline           │ Flight  │ Stops │ Price   │ Duration │ Rating   │ Score    │                    │
│ ├───┼───────────────────┼─────────┼───────┼─────────┼──────────┼──────────┼──────────┤                    │
│ │ 1 │ British Airways   │ BA 191  │ 1     │ $520.00 │ 13h 40m  │ 8.2/10   │ 87.2     │ [sample_token_1]   │
│ │ 2 │ Delta Air Lines   │ DL 238  │ 2     │ $610.00 │ 15h 10m  │ 7.9/10   │ 74.5     │ [sample_token_2]   │
│ └───┴───────────────────┴─────────┴───────┴─────────┴──────────┴──────────┴──────────┘                    │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌── Step 2 ─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Thought: The best recommended flight is Option 1. Now I will collect and validate the passenger's profile.│
│ Action: collect_personal_info(passenger_name="Nguyen Van A", passenger_email="vana@email.com",            │
│                               passenger_phone="0901234567")                                               │
│ Observation: {"status": "success", "message": "✓ Passenger profile validated successfully."}               │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌── Step 3 ─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Thought: Profile is validated. Now I will place a temporary 15-minute hold on Option 1's booking token.   │
│ Action: hold_flight(booking_token="sample_token_1", passenger_count=1, hold_minutes=15, expected_price=520)│
│ Observation: {"status": "held", "hold_code": "HOLD-E5A2B9C1", "expires_at": "2026-03-03 12:25:00"}         │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌── Step 4 ─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Thought: Hold is secured. I will generate a formatted ASCII text invoice with the booking details.        │
│ Action: generate_invoice(passenger_name="Nguyen Van A", passenger_email="vana@email.com",                  │
│                          passenger_phone="0901234567", flight_id="flight-854624", airline="British Airways",│
│                          departure_airport="CDG", arrival_airport="AUS", departure_time="2026-03-03 12:10",│
│                          arrival_time="2026-03-03 16:50", duration="13h 40m", price_per_person=520.0,     │
│                          passengers=1, currency="USD", stops=1)                                           │
│ Observation: {"status": "success", "booking_ref": "BK-2F9A1B8C", "receipt_text": "...[Receipt Table]...", │
│               "invoice_data": {"booking_ref": "BK-2F9A1B8C", "total_price": 546.0}}                       │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌── Step 5 ─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Thought: Invoice is drafted. Now I will render it as a physical PDF receipt saved to disk.                │
│ Action: generate_invoice_pdf(invoice_result={"status": "success", "booking_ref": "BK-2F9A1B8C",           │
│         "invoice_data": {"booking_ref": "BK-2F9A1B8C", "pricing": {"total_price": 546.0}}},               │
│         output_path="invoice_BK-2F9A1B8C.pdf")                                                            │
│ Observation: {"status": "success", "pdf_path": "invoice_BK-2F9A1B8C.pdf", "booking_ref": "BK-2F9A1B8C"}    │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌── Final Response ─────────────────────────────────────────────────────────────────────────────────────────┐
│ Final Answer: I have successfully completed your entire booking workflow:                                │
│ 1. Flight selected: British Airways flight from CDG to AUS ($520.00).                                     │
│ 2. Profile validated: Nguyen Van A (vana@email.com | 0901234567).                                         │
│ 3. Seat hold created: Placed a 15-minute hold. Hold Code: HOLD-E5A2B9C1.                                  │
│ 4. Invoice compiled: Booking Ref: BK-2F9A1B8C. Total (incl. 5% service fee): $546.00 USD.                 │
│ 5. PDF Saved: Physical Helvetica invoice exported to workspace at invoice_BK-2F9A1B8C.pdf                │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔌 Robust LLM Backend & Fallback Chain

To maintain 100% uptime and resilience against API rate-limits or network failures, the agent uses a unified `FallbackChain`:

1. **OpenAI Provider** (Primary) — Invokes `gpt-4o` or `gpt-4o-mini` with default system prompt instructions.
2. **OpenRouter Provider** (Secondary Fallback) — If primary OpenAI keys fail or are empty, the agent transparently falls back to `deepseek/deepseek-v4-flash` via OpenRouter to seamlessly complete the traveler request.

---

*Generated from [`src/agent/agent.py`](./src/agent/agent.py) — `ReActAgent` class.*
