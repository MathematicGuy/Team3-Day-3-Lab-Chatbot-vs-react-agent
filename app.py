import os
import sys
import json
import re
from datetime import datetime
import streamlit as st

# Add src directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.llm_provider import get_fallback_provider, LLMProvider
from src.agent.agent import ReActAgent
from src.telemetry.metrics import tracker

# ----------------- AESTHETICS & CUSTOM CSS -----------------
st.set_page_config(
    page_title="ReAct Travel Agent Playground",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Premium dark slate, indigo gradient, and glassmorphism styling
st.markdown("""
<style>
    /* Main app background */
    .stApp {
        background-color: #0E1117;
        color: #E2E8F0;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Custom premium card */
    .glass-card {
        background: rgba(30, 41, 59, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
        backdrop-filter: blur(8px);
        margin-bottom: 20px;
    }
    
    /* Gradients and typography */
    .gradient-text {
        background: linear-gradient(135deg, #6366F1 0%, #A855F7 50%, #EC4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }
    
    /* Thought block */
    .thought-block {
        background-color: #1E1B4B;
        border-left: 4px solid #6366F1;
        padding: 12px;
        margin: 10px 0;
        border-radius: 4px;
        font-family: 'Courier New', Courier, monospace;
    }
    
    /* Action block */
    .action-block {
        background-color: #311042;
        border-left: 4px solid #A855F7;
        padding: 12px;
        margin: 10px 0;
        border-radius: 4px;
        font-family: 'Courier New', Courier, monospace;
    }
    
    /* Observation block */
    .observation-block {
        background-color: #064E3B;
        border-left: 4px solid #10B981;
        padding: 12px;
        margin: 10px 0;
        border-radius: 4px;
        font-family: 'Courier New', Courier, monospace;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- MOCK PROVIDER FOR DEMO -----------------
class DemoMockLLMProvider(LLMProvider):
    """Mock LLM to simulate steps in case API keys are absent."""
    def __init__(self, query_type: str = "comprehensive"):
        super().__init__(model_name="mock-react-llm")
        self.query_type = query_type
        self.step_count = 0

    def generate(self, prompt: str, system_prompt: str = None, stop: list = None) -> dict:
        self.step_count += 1
        
        # Scenario 1: Productivity Comfort Finder
        if "productivity-friendly" in prompt.lower() and "ba 191" not in prompt.lower():
            if self.step_count == 1:
                content = "Thought: The user is looking for the most comfort and productivity-friendly flight options.\nAction: find_productivity_flights()"
            else:
                content = "Thought: I have retrieved the rankings. I will compile the response.\nFinal Answer: Based on amenities, the top-rated flight is Delta segments DL 83 / DL 1491 scoring 250/100, which offers Free Wi-Fi and power outlets at a cost of $1588."
                
        # Scenario 2: Time Remaining Countdown
        elif "time" in prompt.lower() and "productivity-friendly" not in prompt.lower():
            if self.step_count == 1:
                content = "Thought: I need to calculate the departure time difference.\nAction: time_until_flight('BA 303', '2026-03-03 08:30')"
            else:
                content = "Thought: I have calculated the delta. I will answer.\nFinal Answer: Flight BA 303 departs in 3 hours and 25 minutes relative to your reference time of 2026-03-03 08:30."
                
        # Scenario 3: Details Audit
        elif "itinerary details" in prompt.lower() and "productivity-friendly" not in prompt.lower():
            if self.step_count == 1:
                content = "Thought: I will extract segment specifics.\nAction: parse_flight_details('BA 191')"
            else:
                content = "Thought: Details retrieved successfully.\nFinal Answer: Flight BA 191 is a 2-segment British Airways itinerary: CDG -> LHR on BA 301, and LHR -> AUS on BA 191 (using a premium Airbus A350 with USB/power charging)."
                
        # Scenario 4: Comprehensive Multi-Step
        else:
            if self.step_count == 1:
                content = "Thought: Complex query requested. First I will find the top productivity flights.\nAction: find_productivity_flights()"
            elif self.step_count == 2:
                content = "Thought: Comfort flight options resolved. Next, I will parse the segment itinerary details for flight 'BA 191'.\nAction: parse_flight_details('BA 191')"
            elif self.step_count == 3:
                content = "Thought: Routing parsed. Lastly, I will calculate the countdown time delta for BA 303.\nAction: time_until_flight('BA 303', '2026-03-03 08:30')"
            else:
                content = (
                    "Thought: All facts gathered.\nFinal Answer: Comprehensive Travel Summary:\n"
                    "- **Top Comfort Flight**: Delta (Score: 250/100, Free Wi-Fi, $1588).\n"
                    "- **BA 191 Itinerary**: 2 legs: CDG -> LHR (BA 301) and LHR -> AUS (BA 191, Airbus A350 with full power outlets).\n"
                    "- **BA 303 Countdown**: Departs in 3 hours and 25 minutes relative to 2026-03-03 08:30."
                )
                
        return {
            "content": content,
            "latency_ms": 120,
            "usage": {"prompt_tokens": 150, "completion_tokens": 80, "total_tokens": 230}
        }

    def stream(self, prompt: str, system_prompt: str = None):
        yield "Mock streaming"


# ----------------- STREAMLIT INTERFACE -----------------

if "query" not in st.session_state:
    st.session_state["query"] = "Find the top productivity-friendly flight options from CDG to AUS."

st.markdown('<h1>✈️ <span class="gradient-text">ReAct Flight Agent Assistant</span></h1>', unsafe_allow_html=True)
st.markdown("---")

# Sidebar Configuration Layout
st.sidebar.markdown('<h3>⚙️ System Configurations</h3>', unsafe_allow_html=True)

api_key_input = st.sidebar.text_input(
    "OpenAI API Key",
    value=os.getenv("OPENAI_API_KEY", ""),
    type="password",
    help="Default is loaded from your environment."
)

openrouter_key_input = st.sidebar.text_input(
    "OpenRouter API Key",
    value=os.getenv("OPENAI_ROUTER", ""),
    type="password",
    help="Used to call efficient/cheap Gemini models from OpenRouter."
)

mode = st.sidebar.radio(
    "Reasoning Model Mode",
    ["Live Fallback Chain (OpenAI -> Gemini -> Local)", "High-Fidelity Mock Chain (Simulation)"],
    help="Live Mode runs the LLM fallback chain. Mock Mode runs a local, fast simulation without consuming keys."
)

max_steps_slider = st.sidebar.slider("Maximum ReAct Steps", 1, 15, 8)

# 🧠 Model Customization
st.sidebar.markdown('<h3>🧠 Model Customization</h3>', unsafe_allow_html=True)

# Dynamically retrieve supported models from metrics tracker
supported_models = tracker.get_supported_models()
openai_options = [m for m in supported_models if "gpt" in m] + ["Custom Model..."]
gemini_options = [f"google/{m}" if not m.startswith("google/") else m for m in supported_models if "gemini" in m] + ["Custom Model..."]

# Ensure default values are in the lists, or prepend/append them
if "gpt-4o" not in openai_options:
    openai_options.insert(0, "gpt-4o")
if "google/gemini-3.1-flash-lite" not in gemini_options:
    gemini_options.insert(0, "google/gemini-3.1-flash-lite")
if "google/gemini-2.5-flash" not in gemini_options:
    gemini_options.insert(1, "google/gemini-2.5-flash")

# OpenAI Selectbox
openai_selection = st.sidebar.selectbox(
    "OpenAI Model",
    options=openai_options,
    index=openai_options.index("gpt-4o") if "gpt-4o" in openai_options else 0,
    help="Select a supported OpenAI model from metrics.py or choose Custom Model..."
)

if openai_selection == "Custom Model...":
    openai_model_input = st.sidebar.text_input(
        "Custom OpenAI Model Name",
        value="gpt-4o",
        help="Specify any valid OpenAI model name."
    )
else:
    openai_model_input = openai_selection

# Gemini / OpenRouter Selectbox
gemini_selection = st.sidebar.selectbox(
    "Gemini / OpenRouter Model",
    options=gemini_options,
    index=gemini_options.index("google/gemini-3.1-flash-lite") if "google/gemini-3.1-flash-lite" in gemini_options else 0,
    help="Select a supported Gemini/OpenRouter model from metrics.py (e.g. google/gemini-3.1-flash-lite) or choose Custom Model..."
)

if gemini_selection == "Custom Model...":
    gemini_model_input = st.sidebar.text_input(
        "Custom Gemini/OpenRouter Model Name",
        value="google/gemini-3.1-flash-lite",
        help="Specify any valid OpenRouter model name (e.g., google/gemini-3.1-flash-lite)."
    )
else:
    gemini_model_input = gemini_selection

# Sync API Keys to Env if edited
if api_key_input:
    os.environ["OPENAI_API_KEY"] = api_key_input
if openrouter_key_input:
    os.environ["OPENAI_ROUTER"] = openrouter_key_input

# Provider Status Pill
st.sidebar.markdown('<h3>🔑 Provider Status</h3>', unsafe_allow_html=True)
openai_status = "🟢 Active" if os.getenv("OPENAI_API_KEY") else "🔴 Not Configured"
openrouter_status = "🟢 Active" if os.getenv("OPENAI_ROUTER") else "🔴 Not Configured"
local_status = "🟢 Active" if os.path.exists("./models/Phi-3-mini-4k-instruct-q4.gguf") else "🟡 Skipped"

st.sidebar.markdown(f"**OpenAI (GPT-4o)**: {openai_status}")
st.sidebar.markdown(f"**OpenRouter (Gemini)**: {openrouter_status}")
st.sidebar.markdown(f"**Local Model**: {local_status}")

# 🛠️ Agent Skills
st.sidebar.markdown('<h3>🛠️ Agent Skills</h3>', unsafe_allow_html=True)
st.sidebar.markdown("""
* 💻 **Comfort Finder**: Wi-Fi, power, and legroom scoring
* ⏳ **Departure Countdown**: Duration remaining scheduling
* 💼 **Segment Parser**: Price, carbon footprint, legroom audits
* 🕒 **Clock Sync**: Real-time reference timing calculations
""")

# 🤖 Agent System Prompt
st.sidebar.markdown('<h3>🤖 Agent System Prompt</h3>', unsafe_allow_html=True)
default_prompt = """You are an intelligent travel assistant. You must answer the user request by calling the appropriate tools.
You have access to the following tools:
- find_productivity_flights: Scores and ranks flight routes from the database based on comforts.
- time_until_flight: Calculates the duration remaining until a specific flight departs. Usage: time_until_flight(flight_number, current_time_str)
- parse_flight_details: Parses segment-by-segment itinerary, layover details, carbon footprint, and pricing. Usage: parse_flight_details(flight_number)
- get_current_time: Returns the current local date and time of the system.

Use the following exact format:
Thought: your line of reasoning about what you need to do next.
Action: tool_name(arguments)
Observation: the result returned by the tool.

... (repeat Thought, Action, Observation as many times as needed to resolve the request)

Thought: I have solved the request.
Final Answer: your final response to the user.

Ensure that:
1. Every time you want to execute a tool, write "Action: tool_name(arguments)" followed by a newline and nothing else.
2. Every time you write an "Action", you must STOP and wait for the "Observation:".
3. Write "Final Answer:" when you are finished and have the final resolution."""

system_prompt_input = st.sidebar.text_area(
    "Custom Reasoning Prompt:",
    value=default_prompt,
    height=250,
    help="You can customize the ReAct agent's core instructions here!"
)

st.markdown('<div class="glass-card"><h3>📚 Traveler Use Cases</h3><p>Choose an interactive travel planning use case below. Clicking a button will automatically populate the query input field with a optimized pre-defined prompt.</p></div>', unsafe_allow_html=True)

# Tabs for Use Cases
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("#### 💻 Productivity Finder")
    st.caption("Nomad's Comfort Audit")
    st.write("Searches the database, scores flight segments (Wi-Fi, power, legroom), and recommends high-comfort routes.")
    if st.button("Load Nomad Prompt", key="nomad"):
        st.session_state["query"] = "Find the top productivity-friendly flight options from CDG to AUS."
        st.rerun()

with col2:
    st.markdown("#### ⏳ Departure countdown")
    st.caption("Airport Lounge Sprints")
    st.write("Calculates the precise duration remaining until departure relative to the system or reference clock.")
    if st.button("Load Countdown Prompt", key="countdown"):
        st.session_state["query"] = "How much time is left before flight 'BA 303' departs if the reference time is '2026-03-03 08:30'?"
        st.rerun()

with col3:
    st.markdown("#### 💼 Segment Details Audit")
    st.caption("Flight Route Deep-dive")
    st.write("Extracts segment details, airport names, layover timings, airplane models, baggage, and change policies.")
    if st.button("Load Itinerary Prompt", key="details"):
        st.session_state["query"] = "Retrieve the complete segment-by-segment itinerary details for British Airways flight 'BA 191'."
        st.rerun()

with col4:
    st.markdown("#### 🚀 Combined Audit")
    st.caption("Multi-Step Reasoning")
    st.write("Performs all three tasks sequentially (Comfort Finder -> Route Details -> Timing Countdown) in a unified plan.")
    if st.button("Load Combined Prompt", key="combined"):
        st.session_state["query"] = (
            "Find the top productivity-friendly flight options from CDG to AUS. "
            "Also, retrieve the complete itinerary details for flight 'BA 191', "
            "and calculate how much time is left before flight 'BA 303' departs if the current reference time is '2026-03-03 08:30'."
        )
        st.rerun()

# Query Input Field
st.markdown("### 🔍 Query Runner")
user_query = st.text_area(
    "Query input:",
    key="query",
    height=80
)

# Expose tools descriptions
tools_metadata = [
    {"name": "find_productivity_flights", "description": "Scores and ranks flight routes from the database based on comforts."},
    {"name": "time_until_flight", "description": "Calculates the duration remaining until a specific flight departs. Usage: time_until_flight(flight_number, current_time_str)"},
    {"name": "parse_flight_details", "description": "Parses segment-by-segment itinerary, layover details, carbon footprint, and pricing. Usage: parse_flight_details(flight_number)"},
    {"name": "get_current_time", "description": "Returns the current local date and time of the system."}
]

# Run agent
if st.button("🚀 Run Agentic ReAct Loop", type="primary"):
    if not user_query.strip():
        st.error("Please enter a valid query prompt first.")
    else:
        # 1. Initialize Provider
        if "Live Fallback" in mode:
            with st.spinner("Initializing Fallback LLM Provider (OpenAI -> Gemini -> Local)..."):
                try:
                    llm = get_fallback_provider(
                        openai_model=openai_model_input,
                        gemini_model=gemini_model_input
                    )
                except Exception as e:
                    st.error(f"Failed to initialize live provider: {e}. Falling back to Mock mode automatically.")
                    llm = DemoMockLLMProvider()

            # Show active provider chain pills
            if hasattr(llm, 'providers') and llm.providers:
                provider_names = [p.__class__.__name__.replace('Provider', '') for p in llm.providers]
                model_names = [getattr(p, 'model_name', '?') for p in llm.providers]
                pills_html = " → ".join(
                    f'<span style="background:#6366F1;color:white;padding:3px 10px;border-radius:12px;font-size:0.8em;font-weight:600">{name}: {model}</span>'
                    for name, model in zip(provider_names, model_names)
                )
                st.markdown(f'<p style="margin:4px 0">🔗 <b>Active Fallback Chain:</b> {pills_html}</p>', unsafe_allow_html=True)
        else:
            llm = DemoMockLLMProvider()

        # 2. Build Agent
        agent = ReActAgent(llm=llm, tools=tools_metadata, max_steps=max_steps_slider)
        # Override the agent's system prompt dynamically with the value from the sidebar!
        agent.get_system_prompt = lambda: system_prompt_input
        
        st.markdown("### 🤖 Reasoning Execution Logs")
        
        # Override printing inside Streamlit
        # We hook into streamlit columns or containers to print logs live
        thinking_container = st.container()
        
        # Simple ReAct Loop Execution with visual streams
        logger_events = []
        
        with st.spinner("Agent thinking..."):
            # Intercept print outputs
            import io
            old_stdout = sys.stdout
            new_stdout = io.StringIO()
            sys.stdout = new_stdout
            
            try:
                final_res = agent.run(user_query)
                success_run = True
            except Exception as e:
                success_run = False
                final_res = f"Execution failed: {e}"
            finally:
                captured_out = new_stdout.getvalue()
                sys.stdout = old_stdout
                
            # Parse captured output blocks for rendering
            # Blocks are delimited by newlines
            lines = captured_out.split("\n")
            current_thought = []
            
            for line in lines:
                if not line.strip():
                    continue
                
                # ── Fallback chain events → highlighted banners ──
                if "[FallbackChain] Attempting" in line:
                    # Extract provider name e.g. OpenAIProvider, GeminiProvider
                    provider_part = line.split("provider:")[-1].strip() if "provider:" in line else line
                    st.markdown(
                        f'<div style="background:#1e3a5f;border-left:4px solid #38BDF8;padding:10px 14px;'
                        f'margin:6px 0;border-radius:6px;font-family:monospace">'
                        f'🔄 <b style="color:#38BDF8">SWITCHING MODEL →</b> '
                        f'<span style="color:#E2E8F0">{provider_part}</span></div>',
                        unsafe_allow_html=True
                    )
                elif "[FallbackChain]" in line and "failed" in line.lower():
                    # Extract failed provider
                    failed_part = line.split("Provider")[-1].split("failed")[0].strip() if "Provider" in line else line
                    st.markdown(
                        f'<div style="background:#3b1a1a;border-left:4px solid #F87171;padding:10px 14px;'
                        f'margin:6px 0;border-radius:6px;font-family:monospace">'
                        f'⚠️ <b style="color:#F87171">FALLBACK TRIGGERED</b> — '
                        f'<span style="color:#FCA5A5">{failed_part}</span> failed, trying next provider...</div>',
                        unsafe_allow_html=True
                    )
                # ── Standard ReAct blocks ──
                elif line.startswith("Thought:"):
                    st.markdown(f'<div class="thought-block">🧠 <b>{line}</b></div>', unsafe_allow_html=True)
                elif line.startswith("Action:"):
                    st.markdown(f'<div class="action-block">⚙️ <b>{line}</b></div>', unsafe_allow_html=True)
                elif line.startswith("Observation:"):
                    st.markdown(f'<div class="observation-block">👁️ <b>{line}</b></div>', unsafe_allow_html=True)
                else:
                    # Clean stdout lines
                    st.write(line)
                    
            if success_run:
                st.success("Reasoning loop successfully completed!")
                st.markdown("### 🏆 Final Agent Answer")
                st.info(final_res)
            else:
                st.error("Reasoning loop execution failed!")
                st.markdown("### ❌ Error Message")
                st.error(final_res)
