# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Pham Trung Hieu
- **Student ID**: 2A202600766
- **Date**: 2026-06-01

---

## I. Technical Contribution (15 Points)

### Modules Implemented

| File | Role |
|---|---|
| `src/agent/chatbot.py` | Chatbot baseline — full implementation |
| `tests/test_chatbot.py` | Capability test suite (simple + complex) |
| `report/chatbot_baseline_demo.md` | Gemini baseline run documentation |
| `report/chatbot_baseline_openai_demo.md` | OpenAI baseline run + provider comparison |

### Core Implementation: `src/agent/chatbot.py`

The `Chatbot` class wraps any `LLMProvider` and exposes a single `chat()` method. It maintains multi-turn conversation history and integrates the existing telemetry infrastructure (`IndustryLogger` + `PerformanceTracker`) without any modifications to shared modules.

**Key design decisions:**

**1. Provider-agnostic via dependency injection**
```python
class Chatbot:
    def __init__(self, llm: LLMProvider):
        self.llm = llm
```
The chatbot accepts any provider that implements the `LLMProvider` abstract base class, so switching between Gemini and OpenAI requires only changing `.env` — no code changes.

**2. Multi-turn history via prompt concatenation**
```python
def _build_prompt(self, user_input: str) -> str:
    if not self.conversation_history:
        return user_input
    lines = []
    for turn in self.conversation_history:
        role = "User" if turn["role"] == "user" else "Assistant"
        lines.append(f"{role}: {turn['content']}")
    lines.append(f"User: {user_input}")
    return "\n".join(lines)
```
Prior turns are serialised into the prompt on each call, giving the model conversational context without requiring stateful API sessions.

**3. Telemetry on every call**
```python
tracker.track_request(
    provider=result.get("provider", "unknown"),
    model=self.llm.model_name,
    usage=result.get("usage", {}),
    latency_ms=result.get("latency_ms", 0),
)
logger.log_event("CHATBOT_RESPONSE", {
    "response": response_text,
    "latency_ms": result.get("latency_ms"),
    "total_tokens": result.get("usage", {}).get("total_tokens"),
})
```
Every request logs a structured `LLM_METRIC` and `CHATBOT_RESPONSE` JSON event, making all runs fully traceable.

**4. `build_chatbot()` factory**
```python
def build_chatbot() -> Chatbot:
    provider = os.getenv("DEFAULT_PROVIDER", "google").lower()
    model = os.getenv("DEFAULT_MODEL", "gemini-1.5-flash")
    if provider == "google":
        llm = GeminiProvider(model_name=model, api_key=os.getenv("GEMINI_API_KEY"))
    elif provider == "openai":
        llm = OpenAIProvider(model_name=model, api_key=os.getenv("OPENAI_API_KEY"))
    ...
    return Chatbot(llm)
```
Reads all configuration from `.env` so the chatbot can be instantiated in one line anywhere in the codebase.

### Test Suite: `tests/test_chatbot.py`

Structured into two categories to demonstrate the chatbot's capability ceiling:

- **Simple tests** (5 cases): airport codes, travel documents, baggage policy, timezone arithmetic, multi-turn follow-up. Expected to pass — shows the chatbot is useful for factual Q&A.
- **Complex tests** (6 cases): live price lookup, price+tax+discount chain, carbon emissions comparison, seat availability, conditional booking logic, cross-query aggregation. All expected to fail — the chatbot has no tools and no access to live data, so it either admits inability or hallucinates.

The test runner includes retry-with-backoff for Gemini free-tier `429` rate limits, parsing the `retry in N seconds` field from the error response.

---

## II. Debugging Case Study (10 Points)

### Problem: Conversation history not carried across rate-limited turns

**Description**: During the simple test suite run, the multi-turn test fired three consecutive turns: "I am planning a trip from Paris to Austin" → "What airlines typically fly that route?" → "Which of those would you recommend for a budget traveller?". The first turn hit a `429` rate limit error and was never completed, meaning nothing was appended to `conversation_history`. When the second turn was called, the bot had an empty history and treated "that route" as a dangling reference with no context.

**Log evidence** (from `logs/2026-06-01.log`):
```json
{"event": "CHATBOT_INPUT", "data": {"input": "I am planning a trip from Paris to Austin.", "model": "gemini-2.5-flash"}}
{"event": "CHATBOT_INPUT", "data": {"input": "What airlines typically fly that route?", "model": "gemini-2.5-flash"}}
{"event": "LLM_METRIC",    "data": {"provider": "google", "model": "gemini-2.5-flash", "total_tokens": 316, "latency_ms": 2149}}
{"event": "CHATBOT_RESPONSE", "data": {"response": "I'm sorry, I don't have enough information... I don't know what 'that route' refers to yet."}}
```
Notice: `LLM_METRIC` only fires once, confirming the first call never completed. The second call succeeded but produced a confused response because history was empty.

**Diagnosis**: The `chat()` method appends to `conversation_history` *after* a successful `llm.generate()` call. If `generate()` raises an exception (such as `429`), the turn is lost and the history is left in a stale state, making subsequent follow-up questions incoherent.

**Solution applied**: Added `max_retries` + backoff to the test runner's `run_test()` function, so a rate-limited first turn waits and retries before the follow-up turn fires:
```python
match = re.search(r"retry in (\d+)", err)
wait = int(match.group(1)) + 2 if match else 20
if "429" in err and attempt < max_retries - 1:
    time.sleep(wait)
```
A more robust long-term fix would be to add retry logic inside `Chatbot.chat()` itself so the history is always in a consistent state regardless of the caller.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

**1. Reasoning — what the `Thought` block changes**

The chatbot produces a single forward pass: the model reads the question and immediately generates an answer. If the answer requires information the model was not trained on (live prices, today's availability), the only options are to hallucinate or to refuse. There is no mechanism to *acquire* new information mid-response.

The ReAct `Thought` block changes this by making the model's reasoning an explicit intermediate step rather than an internal one. The model writes out *why* it needs a tool before calling it, which has two effects: it forces the model to decompose the problem ("I need the price first, then I can calculate tax"), and it gives the system a parseable signal to dispatch a real tool call. The observation returned by the tool then updates the model's context, making the next `Thought` grounded in real data.

**2. Reliability — where the chatbot actually wins**

For simple, knowledge-based questions — "What is the IATA code for CDG?", "What documents do I need to fly to the US?" — the chatbot is faster, cheaper, and equally accurate. The ReAct loop adds latency and token cost for every step. On a question that only needs one LLM pass, forcing a Thought-Action-Observation cycle is wasteful and introduces more failure modes (parsing errors, tool timeouts, malformed action strings).

The chatbot also handles open-ended advisory questions better. When asked "What should I consider when booking a budget flight?", a chatbot produces a clean, flowing answer. A ReAct agent may incorrectly try to invoke a tool for a question that needed no tool at all.

**3. Observation — how environment feedback shapes next steps**

The two provider runs on the same query ("Find the cheapest flight from CDG to AUS with 10% tax") illustrate how the *absence* of observations affects response quality:

- **Gemini 2.5 Flash**: short refusal, redirects to booking sites. 621 tokens, 4s.
- **GPT-5 Nano**: long, structured response that asks for clarifying details and shows the tax formula with example numbers. 3 442 tokens, 30s.

Both are operating without observations — they only have the system prompt and the user message. GPT-5 Nano compensates by generating synthetic examples (350 EUR → 385 EUR) to still be *somewhat* useful. In a ReAct loop, the first observation from `search_flights()` would replace all of this speculation with a real price, and the `calculate_tax()` call would produce the exact total — in far fewer tokens than GPT-5 Nano's verbose workaround.

---

## IV. Future Improvements (5 Points)

**Scalability — async tool execution**

The current `Chatbot.chat()` and the planned `ReActAgent.run()` are both synchronous: each tool call blocks until it returns. In a production system with many concurrent users, this creates a bottleneck. The fix is to make the agent loop `async` and use `asyncio.gather()` to run independent tool calls in parallel. For example, if the agent needs both a flight price and the carbon emissions for the same flight, those two API calls can be dispatched simultaneously rather than sequentially.

**Safety — supervisor LLM for action auditing**

A ReAct agent that can call booking tools is an agent that can potentially initiate real transactions. Before any tool call that has side effects (booking, payment), a lightweight "supervisor" LLM should validate the action against a policy ruleset: Is the price within the user's stated budget? Has the user explicitly confirmed? This supervisor runs as a separate, cheaper model call (e.g., a small classifier) and either approves or blocks the action before execution.

**Performance — tool retrieval via vector DB**

As the number of available tools grows (flights, hotels, car hire, visa checks, insurance), including all tool descriptions in the system prompt becomes expensive in tokens and confusing to the model. The production pattern is to store tool descriptions as embeddings in a vector database and retrieve only the top-k most relevant tools for each user query at runtime. This keeps the system prompt small, reduces cost per call, and makes the agent's tool selection more precise.
