# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Luu Thien Viet Cuong
- **Student ID**: 2A202600730
- **Date**: 2026-06-01

---

## I. Technical Contribution (15 Points)

My contribution focused on experiment execution, business metrics implementing, statistical tracking, API backup planning, workflow coordination, and the Streamlit ReAct runner.

- **Modules Implementated**:
  - `app.py`
  - `src/telemetry/metrics.py`
  - `src/core/llm_provider.py` planning and fallback experiment workflow
  - `report/group_report/GROUP_REPORT_TEAM_3.md` experiment result synthesis

- **Code Highlights**:
  - Added/organized the interactive ReAct experiment runner in `app.py`, including live fallback mode, mock mode, model selection, `max_steps`, predefined use-case prompts, and visual rendering of `Thought`, `Action`, `Observation`, and `Final Answer`.
  - Supported the editable experiment system prompt through:
    ```python
    agent = ReActAgent(llm=llm, tools=tools_metadata, max_steps=max_steps_slider)
    agent.get_system_prompt = lambda: system_prompt_input
    ```
  - Helped define the provider backup strategy used by `get_fallback_provider()`:
    ```text
    OpenAIProvider -> Gemini/OpenRouter -> LocalProvider
    ```
  - Wrote/organized business metrics in `src/telemetry/metrics.py`: model, provider, prompt tokens, completion tokens, total tokens, latency, and estimated cost.
  - Built the experiment dashboard logic in `app.py`: total runs, average latency, average tokens, success rate, total cost, per-run table, token/latency charts, loop count, and failure analysis.

- **Documentation**:
  - Helped coordinate the experiment pipeline: define use case -> run chatbot/ReAct -> capture trace -> collect metrics -> compare results.
  - From the group report, the ReAct system reached **95% success rate on 20 test cases**, with **1973 ms average latency**, **3585 ms max fallback latency**, **801 average tokens per task**, and **$0.0144 total estimated test cost**.
  - The measured chatbot baselines showed why the agent was needed: Gemini 2.5 Flash used **621 tokens / 4124 ms / $0.00621**, while GPT-5 Nano used **3442 tokens / 30396 ms / $0.03442**, but neither could reliably complete tool-dependent flight tasks.

---

## II. Debugging Case Study (10 Points)

- **Problem Description**: During live experiments, provider instability could break the ReAct run. API keys could be invalid, rate-limited, suspended, or missing. This was a bigger problem for ReAct than for a chatbot because one user task may require several LLM calls across multiple `Thought -> Action -> Observation` steps.

- **Log Source**:
  ```text
  [*] [FallbackChain] Attempting generate() with provider: OpenAIProvider
  [!] [FallbackChain] Provider OpenAIProvider failed: ...
  [*] [FallbackChain] Attempting generate() with provider: GeminiProvider
  ```

- **Diagnosis**: The failure was not only a model issue. It was an experiment reliability issue. If one provider failed, the team could not fairly judge agent quality because the run failed before the reasoning loop completed. The Streamlit runner also needed to expose fallback events so failed runs could be explained.

- **Solution**: I helped plan the fallback and experiment flow around `FallbackLLMProvider`: OpenAI first, Gemini/OpenRouter second, and LocalProvider as the offline backup. In `app.py`, fallback events are captured from stdout and displayed in the reasoning log. Mock mode was also kept for deterministic demonstrations when APIs were unavailable.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

1. **Reasoning**: The `Thought` block helps the agent split a complex request into smaller steps. A chatbot gives one direct answer, but the ReAct agent can decide to call `find_productivity_flights`, then `parse_flight_details`, then `time_until_flight`, and combine the observations into one final answer.

2. **Reliability**: The agent can perform worse than the chatbot on simple questions because it adds more latency, token cost, parser risk, and provider failure points. For basic travel advice, a single chatbot response is faster and cheaper. For multi-step flight tasks, the agent is better because it uses real tool outputs instead of guessing. However, in this specific case of our problem, for such a highly data dependant problem, AI react agent is much better an option to lean on.

3. **Observation**: Observations make the answer grounded. The agent can base the next step on flight data, itinerary details, countdown results, or tool errors. Developer-side observations also matter: latency, token usage, cost, loop count, and status showed whether a run was practical, not only whether it was correct.

---

## IV. Future Improvements (5 Points)

- **Scalability**: Add a batch experiment runner that executes all test prompts across multiple providers and exports results to CSV/JSON for automatic comparison.
- **Safety**: Add a supervisor check before side-effect tools such as `hold_flight` or invoice generation, and redact passenger information from logs.
- **Performance**: Track  fallback rate, parser error rate, cost per successful task, and average ReAct loop count in a central dashboard instead of only local Streamlit session state.

---