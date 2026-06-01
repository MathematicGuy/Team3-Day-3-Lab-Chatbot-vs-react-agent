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

### 4. 🔧 Tool Execution — `_execute_tool(tool_name, args_str)`

```
_execute_tool()
    │
    ├─ _resolve_tool()   ← look up callable by name
    │       │
    │       ├─ Check injected tool list (self.tools[].function)
    │       └─ Dynamic import from modules:
    │               src.tools.flight_tools
    │               src.tools.hold_tools
    │               src.tools.invoice_tools
    │               src.tools.user_info_tools
    │
    └─ _parse_tool_args()  ← parse the argument string
            │
            ├─ JSON object  → dict kwargs
            ├─ JSON array   → positional args
            └─ CSV key=value → kwargs + positional fallback
                    │
                    └─ _coerce_arg_value()
                            ├─ "none"/"null"  → None
                            ├─ "true"/"false" → bool
                            ├─ digits         → int
                            ├─ decimal        → float
                            └─ otherwise      → str
```

Errors during tool execution are caught and returned as an `Observation` string so the agent can recover gracefully.

---

### 5. 🔁 Loop Termination Conditions

| Condition | Status logged | Return value |
|---|---|---|
| `Final Answer:` found | `success` | Extracted final answer |
| No action and no final answer | `no_action_fallback` | Raw LLM content |
| `steps >= max_steps` (default: 5) | `timeout` | Timeout message |

---

## Available Flight Tools

The agent discovers tools either via **injected definitions** (`self.tools`) or **dynamic module import**:

| Module | Tools |
|---|---|
| `src.tools.flight_tools` | `search_flights`, `find_productivity_flights`, `parse_flight_details`, `time_until_flight` |
| `src.tools.hold_tools` | `hold_flight` |
| `src.tools.invoice_tools` | Invoice-related utilities |
| `src.tools.user_info_tools` | Passenger/user information utilities |

---

## Telemetry Events

Every major step emits a structured JSON event via `src.telemetry.logger`:

| Event | Trigger |
|---|---|
| `AGENT_START` | `run()` entry — logs user input & model name |
| `LLM_RESPONSE` | After each LLM call — logs content & latency |
| `TOOL_EXECUTE` | After each successful tool call — logs tool, args, observation |
| `TOOL_ERROR` | On tool exception — logs tool, args, error message |
| `UNKNOWN_TOOL` | When tool name cannot be resolved |
| `AGENT_END` | On exit — logs step count & termination status |

---

## Full ReAct Loop — Example Trace

```
User: Find the cheapest flight from CDG to AUS on 2026-03-03 and hold it for 15 minutes.

┌── Step 1 ──────────────────────────────────────────────┐
│ Thought: I need to search flights first because        │
│         holding requires a valid booking token.        │
│ Action: search_flights(departure_airport="CDG",        │
│         arrival_airport="AUS",                         │
│         departure_date="2026-03-03", currency="USD")   │
│ → _execute_tool("search_flights", ...)                 │
│ Observation: Found 2 options. Option 1: price 520 USD, │
│              booking_token token_1. Option 2: ...      │
└────────────────────────────────────────────────────────┘

┌── Step 2 ──────────────────────────────────────────────┐
│ Thought: The user wants the cheapest flight. Option 1  │
│         is cheapest and has a booking token.           │
│ Action: hold_flight(booking_token="token_1",           │
│         passenger_count="1", hold_minutes="15")        │
│ → _execute_tool("hold_flight", ...)                    │
│ Observation: Hold created. Hold code HOLD-BA191-001.   │
│              Expires in 15 minutes.                    │
└────────────────────────────────────────────────────────┘

┌── Step 3 ──────────────────────────────────────────────┐
│ Final Answer: I found and temporarily held the         │
│ cheapest flight from CDG to AUS.                       │
│ Hold code: HOLD-BA191-001.                             │
│ Expires in 15 minutes. This is not a paid booking.     │
└────────────────────────────────────────────────────────┘
```

---

## LLM Backend

The agent accepts any `LLMProvider` implementation. In production it uses a **FallbackChain**:

1. **OpenAIProvider** (primary) — GPT-4o / GPT-4o-mini
2. **GeminiProvider via OpenRouter** (fallback) — `deepseek/deepseek-v4-flash`

Costs and latency are tracked per-call by `src.telemetry.metrics`.

---

*Generated from [`src/agent/agent.py`](./src/agent/agent.py) — `ReActAgent` class.*
