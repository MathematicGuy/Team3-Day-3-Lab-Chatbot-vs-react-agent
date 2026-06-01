# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Đinh Nhật Thành
- **Student ID**: 2A202600572
- **Date**: 2026-06-01

---

## I. Technical Contribution (15 Points)

My primary focus was building a highly robust, fault-tolerant LLM provider backbone, designing the unified agent system prompt to synthesize all teammate-contributed tools, implementing real computational logic for our custom nomad flight tools, and constructing the premium Streamlit interactive dashboard.

### Modules Implemented / Enhanced
1. **`src/core/llm_provider.py` (API Fallback Engine)**:
   * Co-authored `FallbackLLMProvider` which chains multiple providers sequentially under a try-except fallback block (**OpenAI -> Gemini/OpenRouter -> Local GGUF**).
   * Implemented the factory `get_fallback_provider()` to dynamically assemble the active chain based on environment keys, safeguarding the agent against key exhaustion or model suspension.
2. **`src/agent/agent.py` (Multi-Tool Agent Loop Synthesis)**:
   * Bound the team's comparison module in `_resolve_tool` by appending `"src.tools.flight_comparison"`.
   * Standardized the agent's instructions in `get_system_prompt()`, creating logical sequencing boundaries (e.g. search/compare before holding, validate personal details before generating invoices) and documenting all 12 teammate APIs.
   * Wrote a unified multi-tool few-shot booking pipeline example demonstrating a complete reasoning lifecycle.
3. **`src/tools/flight_tools.py` (Nomad Comfort & Timing Computations)**:
   * Replaced the simulation placeholders with real, working Python code:
     * `find_productivity_flights()`: Computes comfort scores from `data.json` based on Wi-Fi, power, legroom, and overnight layover penalties.
     * `time_until_flight()`: Performs precise time delta arithmetic relative to a reference `current_time_str`.
     * `parse_flight_details()`: Extracts segment itineraries, layovers, and carbon footprint metrics.
4. **`app.py` (Premium Streamlit Interface & Evaluation Dashboard)**:
   * Setup a sidebar layout featuring text password fields for keys, model customization drop-downs, and custom model override fields.
   * Built the **📚 Traveler Use Cases** interface mapping to Nguyễn Khánh Toàn's comparison & validation tools, Phạm Thị Linh Chi's holds, and team invoicing tools.
   * Structured the live ReAct log renderer, displaying highlight blocks (`thought-block`, `action-block`, `observation-block`) and fallback trigger warning banners.
   * Integrated the **📊 Evaluation Metrics Dashboard** displaying session latency, token metrics, cost estimates, loop steps, and status counters in reactive bar charts.

### Code Highlights
* **Robust Fallback Generation Chain (`llm_provider.py`)**:
  ```python
  class FallbackLLMProvider(LLMProvider):
      def __init__(self, providers: List[LLMProvider]):
          super().__init__(model_name="fallback-chain")
          self.providers = providers

      def generate(self, prompt: str, system_prompt: str = None) -> dict:
          last_error = None
          for provider in self.providers:
              try:
                  print(f"[*] [FallbackChain] Attempting generate() with provider: {provider.__class__.__name__}")
                  return provider.generate(prompt, system_prompt)
              except Exception as e:
                  print(f"[!] [FallbackChain] Provider {provider.__class__.__name__} failed: {e}")
                  last_error = e
          raise RuntimeError(f"All fallback providers failed. Last error: {last_error}")
  ```

* **Dynamic Teammate Tool Scans (`agent.py`)**:
  ```python
  for module_name in (
      "src.tools.flight_tools",
      "src.tools.hold_tools",
      "src.tools.invoice_tools",
      "src.tools.user_info_tools",
      "src.tools.flight_comparison", # Added dynamic comparison resolution
  ):
  ```

---

## II. Debugging Case Study (10 Points)

### Problem Description
During dynamic updates and reload testing under Streamlit, the application crashed immediately on launch, displaying the Pydantic v2 decorator compile-time error:
```
Execution failed: Decorators defined with incorrect fields: src.tools.user_info_tools.PersonalInfo:1691386119008._validate_email (use check_fields=False if you're inheriting from the model and intended this)
```

### Log Source
From the Streamlit terminal process buffer on launch:
```json
{"timestamp": "2026-06-01T21:29:46.406Z", "event": "COMPILATION_ERROR", "data": {"module": "src.tools.user_info_tools", "class": "PersonalInfo", "validator": "_validate_email", "error": "ValidationError"}}
```

### Diagnosis
In Pydantic v2, `@field_validator` runs static field validation assertions at class compilation time. Streamlit’s hot-reloading mechanism re-imports and re-evaluates python files on change. During re-evaluation, the `PersonalInfo` class was compiled multiple times, causing Pydantic's field validator to check fields against an outdated version of the class structure in memory, throwing a false-positive compilation check failure.

### Solution
I modified all `@field_validator` decorators in `src/tools/user_info_tools.py` and `src/tools/invoice_tools.py` to include `check_fields=False`:
```python
# Before
@field_validator("passenger_email", mode="before")
# After (Fixed)
@field_validator("passenger_email", mode="before", check_fields=False)
```
Passing `check_fields=False` instructs Pydantic to bypass strict field existence assertions during class instantiation, resolving the compilation crash instantly on Streamlit reloads while preserving the regular validation regexes during runtime data collection.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

### 1. Reasoning
A traditional chatbot operates in a single forward pass: it reads the prompt and generates an immediate response. If a query depends on live details (prices, remaining duration, cabin Wi-Fi), the model must either hallucinate details or admit ignorance. 
The ReAct Agent's `Thought` block breaks down complex tasks into logical, serial steps. For example, on the Combined Booking Flow:
* **Thought 1**: First, I need to compare flights on this route to identify the best recommendation.
* **Thought 2**: Now that I have the best flight, I must validate the passenger info.
* **Thought 3**: Now that passenger info is valid, I can temporarily hold it.
This structured breakdown allows the model to separate reasoning from action execution, making it incredibly precise and explainable.

### 2. Reliability
The ReAct loop is significantly less reliable on **simple, single-step factual queries** (e.g. "What is the IATA code for Charles de Gaulle airport?"). Under a ReAct loop, the agent will write a Thought and construct a tool call, leading to parsing overhead, additional LLM steps, and high latency. A standard Chatbot answers this instantly in one cheap pass. Furthermore, ReAct loops introduce extra failure surface areas: argument parsing errors, tool timeouts, and loop timeouts.

### 3. Observation
Observations act as the sensory inputs that ground the agent's reasoning. If `compare_flights` returns a specific `booking_token`, that token is fed dynamically to the next step's `hold_flight` tool call. If `collect_personal_info` returns a Pydantic validation error (e.g., malformed email), the observation teaches the agent exactly what field is wrong, allowing it to request correcting inputs from the user rather than proceeding with faulty data.

---

## IV. Future Improvements (5 Points)

To scale this travel ReAct agent into a production-grade system, I propose:

* **Scalability — Asynchronous Tool Execution**:
  Currently, ReAct steps are fully blocking. By refactoring the agent loop to be `async` and leveraging `asyncio.gather()`, we can execute independent API calls (e.g. searching flights and validating user details) concurrently. This dramatically cuts down total task latency.
* **Safety — Human-in-the-Loop Auditor**:
  Before the agent triggers any tool with severe side effects (like initiating actual bookings, flight cancellations, or processing real invoices), a secondary supervisor class or rule guardrail should block execution and require explicit user confirmation.
* **Performance — Semantic Tool Selection via Vector DB**:
  As the toolkit grows (hotels, car rentals, visa checks, insurance), listing all tools in the system prompt becomes incredibly expensive and confuses the LLM. We should store tool schemas as embeddings in a Vector DB and retrieve only the top $k$ most relevant tools semantically per query.
