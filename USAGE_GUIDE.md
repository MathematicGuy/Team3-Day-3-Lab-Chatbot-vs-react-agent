# ReAct Flight Agent Assistant (Industry Edition)

Welcome to the **Flight Agent Assistant** repository! This project implements a fully autonomous **ReAct (Reasoning and Action)** agent designed to solve complex multi-step travel queries (comfort scoring, routing auditing, and countdown timing) using SerpAPI Google Flights and local flight search databases.

---

## 🛠️ Specialized Flight Agent Tools

The assistant utilizes 4 custom-engineered tools located in `src/tools/flight_tools.py`:
1. **`find_productivity_flights()`**: Scans flight segment details (Wi-Fi, USB power, legroom comfort) and calculates a **Productivity Score** to find comfort-optimized flights for digital nomads.
2. **`time_until_flight()`**: Computes a live countdown or elapsed time remaining until a flight departs.
3. **`parse_flight_details()`**: Extracts deep, segment-by-segment itinerary facts, layover details, baggage rules, cancellation terms, and carbon footprint.
4. **`get_current_time()`**: Fetches system time in `YYYY-MM-DD HH:MM` format so the agent has live clock awareness.

---

## ⚙️ Environment Setup

1. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and fill in your credentials:
   ```env
   # API Keys
   OPENAI_API_KEY=your_openai_api_key_here
   GEMINI_API_KEY=your_gemini_api_key_here
   
   # Local GGUF Configuration
   LOCAL_MODEL_PATH=./models/Phi-3-mini-4k-instruct-q4.gguf
   ```

2. **API Model Fallback Plan**:
   The engine automatically initializes a robust **Fallback Provider Chain**: `OpenAI -> Gemini -> Local`.
   - If OpenAI rate limits or key exceptions occur, it seamlessly falls back to Gemini.
   - If both fail, it falls back to your Local CPU model.
   - Wraps local compilation packages gracefully—ensuring the chain works even if `llama-cpp-python` is not compiled on your system.

---

## 🧪 Running & Verifying the System

### 1. Test Tools in Isolation
Verify that your database parsing, countdown mathematics, and SerpAPI interfaces operate with 100% correctness:
```bash
python src/tools/flight_tools.py
```

### 2. Test Agent Loop (High-Fidelity Mock Simulation)
Validate the ReAct parser, history tracking, tool calling, and termination conditions without consuming API keys:
```bash
python tests/test_agent_mock.py
```

### 3. Test Agent Loop (Live OpenAI GPT-4o Run)
Run the complete end-to-end live reasoning sequence with your system API keys:
```bash
# In PowerShell (Windows)
$env:OPENAI_API_KEY="your-active-api-key"; python tests/test_agent.py

# In Bash (Mac/Linux)
export OPENAI_API_KEY="your-active-api-key" && python tests/test_agent.py
```

### 4. Run the Streamlit Web Dashboard (Interactive UI)
Launch a premium, custom-styled travel agent web simulator to click pre-defined use case prompts, config models, and watch intermediate Thoughts, Actions, and tool Observations rendered live:
```bash
streamlit run app.py
```

---

## 📊 Live Verification Output Preview

Below is the actual, verified output from a live end-to-end test session using **GPT-4o**, demonstrating **autonomous self-correction** and multi-step reasoning:

```text
=== Initializing Fallback LLM Provider ===
[*] [FallbackChain] OpenAIProvider registered.
Fallback Provider chain built successfully. Initial model: fallback-chain

=== Initializing ReAct Agent ===

User Query: Find the top productivity-friendly flight options from CDG to AUS. Also, retrieve the complete itinerary details for flight 'BA 191', and calculate how much time is left before flight 'BA 303' departs if the current reference time is '2026-03-03 08:30'.

--- Running Agentic Loop ---
[*] [FallbackChain] Attempting generate() with provider: OpenAIProvider

Thought: To find the top productivity-friendly flight options from CDG to AUS, I will start by using the "find_productivity_flights" tool. Then, I will retrieve the complete itinerary details for flight 'BA 191' using the "parse_flight_details" tool. Finally, I'll calculate the remaining time before flight 'BA 303' departs if the current reference time is '2026-03-03 08:30'. 

Action: find_productivity_flights(from='CDG', to='AUS')
Observation: Error executing tool 'find_productivity_flights' with args 'from='CDG', to='AUS'': find_productivity_flights() got an unexpected keyword argument 'from'
[*] [FallbackChain] Attempting generate() with provider: OpenAIProvider

Thought: It seems there was an error with the argument naming. I will try using positional arguments instead of keyword arguments for the "find_productivity_flights" tool.

Action: find_productivity_flights('CDG', 'AUS')
Observation: Error executing tool 'find_productivity_flights' with args ''CDG', 'AUS'': find_productivity_flights() takes from 0 to 1 positional arguments but 2 were given
[*] [FallbackChain] Attempting generate() with provider: OpenAIProvider

Thought: The "find_productivity_flights" tool might not require specific from and to parameters, and might instead provide options from a set route database. I will call it without any arguments.

Action: find_productivity_flights()
Observation: [
  {
    "airline": "Delta",
    "price_usd": 1588,
    "total_duration_mins": 942,
    "productivity_score": 250,
    "segments": [
      { "flight_number": "DL 83", "wifi": "Free", "power": true, "legroom_inch": 31 }
    ]
  },
  ...
]
[*] [FallbackChain] Attempting generate() with provider: OpenAIProvider

Thought: I have found the top productivity-friendly flight options from CDG to AUS. Next, I will retrieve the complete itinerary details for flight 'BA 191' using the "parse_flight_details" tool.

Action: parse_flight_details('BA 191')
Observation: {
  "airline": "British Airways",
  "total_duration_mins": 820,
  "price_usd": 520,
  "flight_legs": [
    { "flight_number": "BA 301", "departure": "CDG", "arrival": "LHR" },
    { "flight_number": "BA 191", "departure": "LHR", "arrival": "AUS", "airplane": "Airbus A350" }
  ]
}
[*] [FallbackChain] Attempting generate() with provider: OpenAIProvider

Thought: I have retrieved the complete itinerary details for flight 'BA 191'. Now, I will calculate how much time is left before flight 'BA 303' departs if the current reference time is '2026-03-03 08:30'.

Action: time_until_flight('BA 303', '2026-03-03 08:30')
Observation: Flight BA 303 departing from Paris Charles de Gaulle Airport (CDG) is in 3 hours and 25 minutes (Scheduled: 2026-03-03 11:55, Current reference: 2026-03-03 08:30).
[*] [FallbackChain] Attempting generate() with provider: OpenAIProvider

Thought: I have gathered all the necessary information to respond to the user's request.

Final Answer: 
1. **Top Productivity-Friendly Flights (CDG -> AUS):**
   - Delta Airlines (Price: $1588, Score: 250/100, Free Wi-Fi, in-seat power)
   - Air France / Delta (Price: $1589, Score: 235/100)
2. **Itinerary Details for BA 191:**
   - Two legs: BA 301 (CDG -> LHR) & BA 191 (LHR -> AUS, Airbus A350, power outlets, Wi-Fi)
   - Baggage: Checked bag for a fee | Cancellations: Fully refundable
3. **Flight Countdown (BA 303):**
   - Scheduled: 2026-03-03 11:55 AM. Time left relative to reference: **3 hours and 25 minutes**.

================ FINAL AGENT ANSWER ================
[Success Response displayed above]
```
