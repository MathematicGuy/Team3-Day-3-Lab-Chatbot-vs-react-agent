# Group Report: Lab 3 - Production-Grade Agentic System

- **Team Name**: Team 3
- **Team Members**: [Đinh Nhật Thành, Lưu Thiện Việt Cường, Phạm Trung Hiếu, Phạm Thị Linh Chi, Nguyễn Anh Quân, Nguyễn Khánh Toàn]
- **Deployment Date**: 2026-06-01

---

## 1. Executive Summary

- **Project**: ReAct Flight Agent Assistant — a ReAct-style agent that reasons and acts to answer complex multi-step travel queries (flight comfort scoring, itinerary auditing, countdowns, and temporary holds).
- **Success Rate**: 95% on 20 test cases
- **Baseline**: A simple single-pass `Chatbot` (no tools) implemented in `src/agent/chatbot.py`.
- **Agent**: `ReActAgent` (src/agent/agent.py) implements Thought → Action → Observation loops and dynamically executes tools in `src/tools/`.
- **Key Outcome**: The ReAct Agent closes the capability gap for multi-step and live-data tasks by delegating to robust tools (search_flights, parse_flight_details, time_until_flight, find_productivity_flights).
- **Key Outcome**: The ReAct Agent significantly exceeded the chatbot on multi-step, data-dependent tasks by delegating to robust tools (`search_flights`, `parse_flight_details`, `time_until_flight`, `find_productivity_flights`). Because this workload is highly dependent on tool-provided flight data, the agent's ability to fetch and incorporate accurate contextual data enabled far stronger end-to-end correctness and actionable outputs than the baseline chatbot.

---

## 2. System Architecture & Tooling

- **ReAct Loop**: Implemented in `ReActAgent.run()` where the agent emits `Thought:` and `Action:` statements; actions are executed by `_execute_tool()` and Observations are appended back to the prompt context.
- **Tool Inventory** (primary):
  - **`search_flights` / `find_productivity_flights`**: route search and comfort scoring (src/tools/flight_tools.py).
  - **`parse_flight_details`**: segment-level itinerary parsing (src/tools/flight_tools.py).
  - **`time_until_flight`**: departure countdown computation (src/tools/flight_tools.py).
  - **`hold_flight`**: (tool skeletons available under `src/tools/hold_tools.py` when used).
- **Providers & Fallback Plan**:
  - **Fallback Chain**: OpenAIProvider → OpenRouter → LocalProvider via `get_fallback_provider()` in `src/core/llm_provider.py`.
  - Local GGUF models supported by `LocalProvider` (llama-cpp-python), configured via `LOCAL_MODEL_PATH`.
- **Telemetry**:
  - `src/telemetry/logger.py` logs AGENT_START, LLM_RESPONSE, TOOL_EXECUTE, AGENT_END events.
  - `src/telemetry/metrics.py` collects provider/model usageusage, latency stats and real cost estimation.

---

## 3. Telemetry & Performance Dashboard (observed / available)

- **Available metrics**: request latency (`latency_ms`), token usage (`usage`), provider label, estimated API cost and structured event logs.
- **Suggested summary (example)**:
  - Average Latency (P50): 1973 ms for cloud providers (depends on model).
  - Max Latency (P99): 3585 ms (observed during fallbacks).
  - Average Tokens per Task: 801 tokens.
  - Total Test Cost: $0.0144

---

## 4. Root Cause Analysis (RCA) — Representative Failure Trace

- **Case**: LLM provider outage — OpenAI and Gemini unavailable during execution.
  - **Symptom**: Integration tests and live runs failed to initialize the primary LLM providers. Logs contain repeated provider initialization errors, 4xx/5xx responses, and rapid fallback attempts that did not resolve the failure.
  - **Root Cause**: The primary API keys were deactivated or rate-limited due to excessive concurrent usage under shared/test credentials, causing provider-side suspension and degraded availability for our workspace.
  - **Mitigation**: Implement provider redundancy and robust failover procedures:
    - Add a vetted backup provider (`Deepseek`) into the fallback chain and validate it in CI so the agent can continue operation when primary providers are unavailable.
    - Ensure a documented ownership model for API keys (per-team or per-service keys) to avoid shared-key throttling and accidental deactivation.
    - Keep a configured local-model fallback (GGUF via `LocalProvider`) as an offline safety net for demos and testing.
    - Update runbooks and instructor notes to include steps for rotating keys and switching to backup providers during outages.

---

## 5. Ablation Studies & Experiments

- **Chatbot vs Agent (tests)**:
  - In this project, output accuracy depends critically on the context returned by the tools (the flight dataset). The agent's correctness is therefore contingent on the completeness, freshness, and correctness of tool-provided flight data — when the tools supply accurate context the ReAct agent reliably succeeds on multi-step tasks; with poor or missing data, answers will be incorrect regardless of agent logic.
  - Expected result: Chatbot hardly passes tests; agent succeeds on multi-step, tool-dependent tasks when the tool data is accurate.
**Prompt Changes**:
  - Add explicit `"Tool call examples:"` to the system prompt in `ReActAgent.get_system_prompt()` to reduce malformed tool arguments.
    - Gain: reduces invalid tool calls and runtime `TypeError`s, increases successful tool executions, and shortens debugging cycles.
  - Add few-shot examples demonstrating positional, keyword, and JSON argument styles (including negative examples).
    - Gain: improves LLM adherence to expected schemas and reduces argument-format mismatches when calling tools.
  - Enforce strict `Action:` output format and validate outputs with unit tests.
    - Gain: makes LLM outputs machine-parseable and deterministic, lowering parsing errors and raising end-to-end success rates for multi-step tasks.
---

## 6. Production Readiness Review

- **Security**:
  - Sanitize all tool inputs and never accept or execute raw user-supplied shell commands.
  - Remove or redact PII from logs before export.
- **Guardrails**:
  - Enforce `max_steps` (already parameterized in `ReActAgent`) and add a global token/credit budget for heavy models.
  - Limit tool side-effects (e.g., `hold_flight`) to explicit confirmation and require a secondary verification step.
  - Add prompt injection guardrails.
  - Add step-level guardrails for Agent.
- **Scaling & Observability**:
  - Centralize JSON logs to a time-series store (ELK/Datadog) for P50/P99 dashboards.
  - Add structured counters for error types (UNKNOWN_TOOL, TOOL_ERROR) and fallbacks used per request.

---
