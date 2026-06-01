import os
import sys
import json
import re
import time
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
        
        # Scenario 1: Flight Comparison & Scoring
        if "compare" in prompt.lower():
            if self.step_count == 1:
                content = (
                    "Thought: The user wants to compare flights from CDG to AUS. I will call the compare_flights tool.\n"
                    "Action: compare_flights(departure_airport=\"CDG\", arrival_airport=\"AUS\", departure_date=\"2026-03-03\", sort_by=\"recommended\")"
                )
            else:
                content = (
                    "Thought: Flight comparison results have been retrieved in a structured table. I will output the final answer.\n"
                    "Final Answer: Based on your request, I compared the flights from CDG to AUS on 2026-03-03. The best recommended flight is Option 1 (British Airways, $520.0) which scored highest on comfort metrics (RCM index):\n\n"
                    "+-----+-----------+----------+----------+----------+-------+-------+\n"
                    "| Pos | Airline   | Depart   | Arrival  | Duration | Price | RCM   |\n"
                    "+-----+-----------+----------+----------+----------+-------+-------+\n"
                    "| 1   | British A | CDG      | AUS      | 13h 40m  | $520  | YES   |\n"
                    "| 2   | British A | CDG      | AUS      | 10h 10m  | $525  |       |\n"
                    "+-----+-----------+----------+----------+----------+-------+-------+\n\n"
                    "The recommended flight features a comfortable 13h 40m duration with in-seat power, USB charging, and above-average legroom on the LHR-AUS segment (BA 191)."
                )
                
        # Scenario 2: Passenger Info Validation
        elif "validate" in prompt.lower() or "passenger info" in prompt.lower() or "personal info" in prompt.lower():
            if self.step_count == 1:
                content = (
                    "Thought: I need to collect and validate the passenger details using collect_personal_info.\n"
                    "Action: collect_personal_info(passenger_name=\"Nguyen Van A\", passenger_email=\"vana@email.com\", passenger_phone=\"0901234567\", date_of_birth=\"1995-10-15\")"
                )
            else:
                content = (
                    "Thought: Validation returned success. I will report the clean validated status to the traveler.\n"
                    "Final Answer: ✓ The passenger personal information is fully valid under our Pydantic validation checks:\n"
                    "- **Passenger Name**: Nguyen Van A\n"
                    "- **Email**: vana@email.com\n"
                    "- **Phone**: 0901234567\n"
                    "- **Date of Birth**: 1995-10-15\n\n"
                    "The model validates all regex-matched phone characters, email domain patterns, and YYYY-MM-DD DOB constraints successfully and is ready for ticketing."
                )
                
        # Scenario 3: Flight Hold
        elif "hold" in prompt.lower() and "validate" not in prompt.lower() and "invoice" not in prompt.lower():
            if self.step_count == 1:
                content = (
                    "Thought: To hold the cheapest flight, I first need to search flights from CDG to AUS.\n"
                    "Action: search_flights(departure_airport=\"CDG\", arrival_airport=\"AUS\", departure_date=\"2026-03-03\")"
                )
            elif self.step_count == 2:
                content = (
                    "Thought: Found 2 options. The cheapest is Option 1 ($520) with token 'sample_token_1'. Now I will put a 15-minute hold on it.\n"
                    "Action: hold_flight(booking_token=\"sample_token_1\", passenger_count=1, hold_minutes=15, expected_price=520.0)"
                )
            else:
                content = (
                    "Thought: Hold has been placed. I will report the hold details to the user.\n"
                    "Final Answer: I searched flights from CDG to AUS, found the cheapest option, and successfully placed a 15-minute temporary hold on it.\n"
                    "- **Airline**: British Airways\n"
                    "- **Booking Token**: sample_token_1\n"
                    "- **Hold Reference Code**: **HOLD-BA191-001**\n"
                    "- **Status**: Held (Expires in 15 minutes)\n\n"
                    "*This is a lab-safe simulation and is not a paid booking. No payment details were requested.*"
                )
                
        # Scenario 4: Invoice generation only
        elif "invoice" in prompt.lower() and "compare" not in prompt.lower():
            if self.step_count == 1:
                content = (
                    "Thought: I will generate the flight invoice receipt for the traveler.\n"
                    "Action: generate_invoice(passenger_name=\"Nguyen Van A\", passenger_email=\"vana@email.com\", passenger_phone=\"0901234567\", flight_id=\"flight-854624\", airline=\"British Airways\", departure_airport=\"CDG\", arrival_airport=\"AUS\", departure_time=\"2026-03-03 12:10\", arrival_time=\"2026-03-03 16:50\", duration=\"13h 40m\", price_per_person=520.0, passengers=1)"
                )
            else:
                content = (
                    "Thought: The receipt is generated. I will display the ASCII invoice.\n"
                    "Final Answer: Here is your travel receipt confirmation (Total $546.00, including a mock 5% service fee):\n\n"
                    "╔══════════════════════════════════════════════════════════════╗\n"
                    "║              ✈  XÁC NHẬN ĐẶT VÉ MÁY BAY                    ║\n"
                    "╚══════════════════════════════════════════════════════════════╝\n\n"
                    "  Mã đặt vé  : BK-A2B9C8E7\n"
                    "  Ngày xuất  : 2026-06-01 21:30:10\n"
                    "  Hành khách : Nguyen Van A\n"
                    "  Hãng bay   : British Airways (BA 191)\n"
                    "  Hành trình : CDG -> AUS\n"
                    "  Tổng cộng  : 546.00 USD (Service Fee 5% included)\n\n"
                    "══════════════════════════════════════════════════════════════"
                )

        # Scenario 5: Combined Booking Flow (Multi-Tool!)
        else:
            if self.step_count == 1:
                content = (
                    "Thought: The user wants a complete booking pipeline (Compare flights -> Select best -> Validate passenger info -> Create hold -> Generate invoice & PDF receipt). First, I will compare flights from CDG to AUS.\n"
                    "Action: compare_flights(departure_airport=\"CDG\", arrival_airport=\"AUS\", departure_date=\"2026-03-03\", sort_by=\"recommended\")"
                )
            elif self.step_count == 2:
                content = (
                    "Thought: The best recommended option is British Airways flight ($520). Next, I will validate the passenger's details.\n"
                    "Action: collect_personal_info(passenger_name=\"Nguyen Van A\", passenger_email=\"vana@email.com\", passenger_phone=\"0901234567\")"
                )
            elif self.step_count == 3:
                content = (
                    "Thought: Passenger details are validated. Now, I will put a 15-minute hold on the recommended flight.\n"
                    "Action: hold_flight(booking_token=\"sample_token_1\", passenger_count=1, hold_minutes=15, expected_price=520.0)"
                )
            elif self.step_count == 4:
                content = (
                    "Thought: The hold is created under HOLD-E5A2B9C1. Now I will generate the beautiful ASCII invoice receipt.\n"
                    "Action: generate_invoice(passenger_name=\"Nguyen Van A\", passenger_email=\"vana@email.com\", passenger_phone=\"0901234567\", flight_id=\"flight-854624\", airline=\"British Airways\", departure_airport=\"CDG\", arrival_airport=\"AUS\", departure_time=\"2026-03-03 12:10\", arrival_time=\"2026-03-03 16:50\", duration=\"13h 40m\", price_per_person=520.0, passengers=1, currency=\"USD\", booking_link=\"https://www.google.com/travel/flights?booking_token=sample_token_1\", stops=1)"
                )
            elif self.step_count == 5:
                content = (
                    "Thought: Invoice BK-2F9A1B8C generated successfully. Lastly, I will write the physical PDF receipt file to disk.\n"
                    "Action: generate_invoice_pdf(invoice_result={\"status\": \"success\", \"booking_ref\": \"BK-2F9A1B8C\", \"receipt_text\": \"...\", \"invoice_data\": {\"booking_ref\": \"BK-2F9A1B8C\", \"passenger\": {\"name\": \"Nguyen Van A\", \"email\": \"vana@email.com\", \"phone\": \"0901234567\"}, \"flight\": {\"flight_id\": \"flight-854624\", \"airline\": \"British Airways\", \"departure_airport\": \"CDG\", \"arrival_airport\": \"AUS\", \"departure_time\": \"2026-03-03 12:10\", \"arrival_time\": \"2026-03-03 16:50\", \"duration\": \"13h 40m\", \"stops\": 1}, \"pricing\": {\"price_per_person\": 520.0, \"passengers\": 1, \"subtotal\": 520.0, \"service_fee\": 26.0, \"total_price\": 546.0, \"currency\": \"USD\"}}})"
                )
            else:
                content = (
                    "Thought: The PDF file has been written to disk. The entire multi-tool process is completed successfully. I will output the final answer.\n"
                    "Final Answer: I have successfully completed the entire travel booking process:\n\n"
                    "1. **Flight Compared**: Recommending British Airways CDG -> AUS ($520.00).\n"
                    "2. **Passenger Validated**: Nguyen Van A (vana@email.com | 0901234567).\n"
                    "3. **Safe Hold Placed**: Placed a 15-minute temporary hold (Hold Code: **HOLD-E5A2B9C1**).\n"
                    "4. **Receipt Invoice**: Reference: **BK-2F9A1B8C** (Total: $546.00 USD, includes 5% service fee).\n"
                    "5. **Physical PDF Confirmation**: Written successfully to disk at: `invoice_BK-2F9A1B8C.pdf`.\n\n"
                    "Here is your travel invoice:\n\n"
                    "╔══════════════════════════════════════════════════════════════╗\n"
                    "║              ✈  XÁC NHẬN ĐẶT VÉ MÁY BAY                    ║\n"
                    "╚══════════════════════════════════════════════════════════════╝\n\n"
                    "  Mã đặt vé  : BK-2F9A1B8C\n"
                    "  Ngày xuất  : 2026-06-01\n"
                    "  Hành khách : Nguyen Van A\n"
                    "  Hành trình : CDG → AUS\n"
                    "  Hạng vé    : Phổ thông (Economy)\n"
                    "  Tổng cộng  : 546.00 USD (Includes 5% Service Fee)\n\n"
                    "══════════════════════════════════════════════════════════════"
                )
                
        return {
            "content": content,
            "latency_ms": 120,
            "usage": {"prompt_tokens": 150, "completion_tokens": 80, "total_tokens": 230}
        }

    def stream(self, prompt: str, system_prompt: str = None):
        yield "Mock streaming"


# ----------------- STREAMLIT INTERFACE -----------------

if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "assistant", "content": "Hello! I am your Flight Agent Assistant. How can I help you search, compare, or hold flights today?"}
    ]
if "pending_query" not in st.session_state:
    st.session_state["pending_query"] = None
if "eval_runs" not in st.session_state:
    st.session_state["eval_runs"] = []

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

max_steps_slider = st.sidebar.slider("Maximum ReAct Steps", 1, 15, 10)

# 🧠 Model Customization
st.sidebar.markdown('<h3>🧠 Model Customization</h3>', unsafe_allow_html=True)

# Dynamically retrieve supported models from metrics tracker
supported_models = tracker.get_supported_models()
openai_options = [m for m in supported_models if "gpt" in m] + ["Custom Model..."]
gemini_options = [f"google/{m}" if not m.startswith("google/") else m for m in supported_models if "gemini" in m] + ["Custom Model..."]

# Ensure default values are in the lists, or prepend/append them
if "gpt-5-nano-2025-08-07" not in openai_options:
    openai_options.insert(0, "gpt-5-nano-2025-08-07")
if "deepseek/deepseek-v4-flash" not in gemini_options:
    gemini_options.insert(0, "deepseek/deepseek-v4-flash")
if "google/gemini-2.5-flash" not in gemini_options:
    gemini_options.insert(1, "google/gemini-2.5-flash")

# OpenAI Selectbox
openai_selection = st.sidebar.selectbox(
    "OpenAI Model",
    options=openai_options,
    index=openai_options.index("gpt-5-nano-2025-08-07") if "gpt-5-nano-2025-08-07" in openai_options else 0,
    help="Select a supported OpenAI model from metrics.py or choose Custom Model..."
)

if openai_selection == "Custom Model...":
    openai_model_input = st.sidebar.text_input(
        "Custom OpenAI Model Name",
        value="gpt-5-nano-2025-08-07",
        help="Specify any valid OpenAI model name."
    )
else:
    openai_model_input = openai_selection

# Gemini / OpenRouter Selectbox
gemini_selection = st.sidebar.selectbox(
    "Gemini / OpenRouter Model",
    options=gemini_options,
    index=gemini_options.index("deepseek/deepseek-v4-flash") if "deepseek/deepseek-v4-flash" in gemini_options else 0,
    help="Select a supported Gemini/OpenRouter model from metrics.py (e.g. deepseek/deepseek-v4-flash) or choose Custom Model..."
)

if gemini_selection == "Custom Model...":
    gemini_model_input = st.sidebar.text_input(
        "Custom Gemini/OpenRouter Model Name",
        value="deepseek/deepseek-v4-flash",
        help="Specify any valid OpenRouter model name (e.g., deepseek/deepseek-v4-flash)."
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

st.sidebar.markdown(f"**OpenAI (gpt-5-nano-2025-08-07)**: {openai_status}")
st.sidebar.markdown(f"**OpenRouter (Gemini)**: {openrouter_status}")
st.sidebar.markdown(f"**Local Model**: {local_status}")

# 🛠️ Agent Skills
st.sidebar.markdown('<h3>🛠️ Agent Skills</h3>', unsafe_allow_html=True)
st.sidebar.markdown("""
* 📊 **Flight comparison**: Ranks flights by price, rating, stops, duration, or recommendation score.
* 👤 **Passenger Validation**: Enforces structured Pydantic checks on traveler emails, phones, and profiles.
* ⏳ **Simulated Holds**: Sets safe flight holds for passenger convenience.
* 🧾 **Invoice Billing**: Automatically creates professional ASCII receipts and outputs physical PDF invoices.
""")

# 🤖 Agent System Prompt
st.sidebar.markdown('<h3>🤖 Agent System Prompt</h3>', unsafe_allow_html=True)
default_prompt = """You are a Flight Search, Compare, and Hold ReAct Agent.
Your job is to help users search, compare flights, collect & validate passenger information, manage temporary holds, and generate receipts (text invoices and physical PDFs).

Available tools:
- search_flights: Search flight options from local mock database. Usage: search_flights(departure_airport, arrival_airport, departure_date)
- compare_flights: Compares multiple flights with a sortable ASCII table. Usage: compare_flights(departure_airport, arrival_airport, departure_date, sort_by)
- find_productivity_flights: Scores and ranks flight routes from database based on comfort. Usage: find_productivity_flights()
- time_until_flight: Calculates duration remaining until departure. Usage: time_until_flight(flight_number, current_time_str)
- parse_flight_details: Parses segment itinerary details, price, layovers. Usage: parse_flight_details(flight_number)
- get_current_time: Returns current local date/time of system in YYYY-MM-DD HH:MM format.
- collect_personal_info: Collects & validates passenger details. Usage: collect_personal_info(passenger_name, passenger_email, passenger_phone)
- collect_address_info: Collects & validates street address. Usage: collect_address_info(street, city)
- collect_travel_preferences: Collects seating, meal, baggage preferences. Usage: collect_travel_preferences(preferred_class)
- validate_all_user_info: Validates all personal, address, preferences at once. Usage: validate_all_user_info(user_data)
- hold_flight: Temporarily hold flight using booking_token/flight_id. Usage: hold_flight(booking_token, passenger_count, hold_minutes)
- get_hold: Looks up temporary hold by code. Usage: get_hold(hold_code)
- generate_invoice: Creates beautiful ASCII flight receipt invoice. Usage: generate_invoice(passenger_name, flight_id, airline, departure_airport, arrival_airport, departure_time, arrival_time, duration, price_per_person)
- generate_invoice_pdf: Generates a formal PDF invoice file on disk from invoice_result. Usage: generate_invoice_pdf(invoice_result, output_path)

Use this exact format:
Thought: brief reasoning about what to do next
Action: tool_name(argument_name="value", another_argument="value")
Observation: result returned by tool

When finished, use:
Final Answer: your final response summarizing everything resolved.
"""

system_prompt_input = st.sidebar.text_area(
    "Custom Reasoning Prompt:",
    value=default_prompt,
    height=250,
    help="You can customize the ReAct agent's core instructions here!"
)

st.markdown('<div class="glass-card"><h3>📚 Traveler Use Cases</h3><p>Choose an interactive teammate travel use case below. Clicking a button will automatically populate the query runner with an optimized pre-defined prompt.</p></div>', unsafe_allow_html=True)

# Tabs for Use Cases
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown("#### 📊 Flight Comparison")
    st.caption("Nguyễn Khánh Toàn")
    st.write("Searches routes and returns a sortable, weighted RCM scoring comparison table.")
    if st.button("Compare Flights Prompt", key="compare_use"):
        st.session_state["pending_query"] = "Compare flights from CDG to AUS on 2026-03-03 sorted by recommended score."
        st.rerun()

with col2:
    st.markdown("#### 👤 Info Validation")
    st.caption("Nguyễn Khánh Toàn")
    st.write("Enforces declarative Pydantic v2 email, phone, and date constraints on passenger info.")
    if st.button("Validate Info Prompt", key="validate_use"):
        st.session_state["pending_query"] = "Validate passenger personal info for Nguyen Van A (email: vana@email.com, phone: 0901234567, DOB: 1995-10-15)."
        st.rerun()

with col3:
    st.markdown("#### ⏳ Simulated Hold")
    st.caption("Phạm Thị Linh Chi")
    st.write("Searches flight routes, selects the cheapest option, and creates a simulated hold reservation.")
    if st.button("Simulate Hold Prompt", key="hold_use"):
        st.session_state["pending_query"] = "Search flights from CDG to AUS on 2026-03-03, choose the cheapest option, and place a 15-minute temporary hold on it."
        st.rerun()

with col4:
    st.markdown("#### 🧾 Invoice & PDF Receipt")
    st.caption("Đinh Nhật Thành / Lưu Thiện Việt Cường")
    st.write("Generates custom booking confirmations, calculates total price + fee, and exports formal PDF files.")
    if st.button("Generate Invoice Prompt", key="inv# Chat History Container
st.markdown("### 💬 Flight Agent Assistant Chat")
for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Expose tools descriptions
tools_metadata = [
    {"name": "search_flights", "description": "Search flight options from local mock database. Usage: search_flights(departure_airport, arrival_airport, departure_date)"},
    {"name": "compare_flights", "description": "Compares flights with a sortable ASCII table. Usage: compare_flights(departure_airport, arrival_airport, departure_date, sort_by)"},
    {"name": "find_productivity_flights", "description": "Scores and ranks flight routes from database based on comfort. Usage: find_productivity_flights()"},
    {"name": "time_until_flight", "description": "Calculates duration remaining until departure. Usage: time_until_flight(flight_number, current_time_str)"},
    {"name": "parse_flight_details", "description": "Parses segment itinerary details. Usage: parse_flight_details(flight_number)"},
    {"name": "get_current_time", "description": "Returns current local date/time of system in YYYY-MM-DD HH:MM format."},
    {"name": "collect_personal_info", "description": "Collects & validates passenger details. Usage: collect_personal_info(passenger_name, passenger_email, passenger_phone)"},
    {"name": "collect_address_info", "description": "Collects & validates street address. Usage: collect_address_info(street, city)"},
    {"name": "collect_travel_preferences", "description": "Collects preferences. Usage: collect_travel_preferences(preferred_class)"},
    {"name": "validate_all_user_info", "description": "Validates personal, address, preferences at once. Usage: validate_all_user_info(user_data)"},
    {"name": "hold_flight", "description": "Temporarily hold flight using booking_token. Usage: hold_flight(booking_token, passenger_count, hold_minutes)"},
    {"name": "get_hold", "description": "Looks up temporary hold by code. Usage: get_hold(hold_code)"},
    {"name": "generate_invoice", "description": "Creates ASCII flight receipt invoice. Usage: generate_invoice(passenger_name, flight_id, airline, departure_airport, arrival_airport, departure_time, arrival_time, duration, price_per_person)"},
    {"name": "generate_invoice_pdf", "description": "Generates a formal PDF invoice file on disk from invoice_result. Usage: generate_invoice_pdf(invoice_result, output_path)"}
]

# Check for pending query from traveler use cases, or render standard chat input bar
user_query = None
if st.session_state["pending_query"]:
    user_query = st.session_state["pending_query"]
    st.session_state["pending_query"] = None
else:
    user_query = st.chat_input("Ask the Flight Agent anything...")

if user_query:
    # 1. Append User Message
    st.session_state["messages"].append({"role": "user", "content": user_query})
    
    # 2. Rerun to show user message immediately in chat
    st.rerun()

# If the last message is from the user, the assistant must reply
if st.session_state["messages"][-1]["role"] == "user":
    user_query_to_run = st.session_state["messages"][-1]["content"]
    
    with st.chat_message("assistant"):
        # A. Initialize Provider
        if "Live Fallback" in mode:
            with st.spinner("Initializing Fallback LLM Provider..."):
                try:
                    llm = get_fallback_provider(
                        openai_model=openai_model_input,
                        gemini_model=gemini_model_input
                    )
                except Exception as e:
                    st.error(f"Failed to initialize live provider: {e}. Falling back to Mock mode automatically.")
                    llm = DemoMockLLMProvider()
        else:
            llm = DemoMockLLMProvider()

        # B. Build Agent
        agent = ReActAgent(llm=llm, tools=tools_metadata, max_steps=max_steps_slider)
        agent.get_system_prompt = lambda: system_prompt_input

        # C. Capture reasoning steps live in a standard Streamlit Status box
        with st.status("🕵️ Flight Agent reasoning in progress...", expanded=True) as status_box:
            import io
            old_stdout = sys.stdout
            new_stdout = io.StringIO()
            sys.stdout = new_stdout

            run_start = time.time()
            try:
                final_res = agent.run(user_query_to_run)
                success_run = True
            except Exception as e:
                success_run = False
                final_res = f"Execution failed: {e}"
            finally:
                run_latency_ms = int((time.time() - run_start) * 1000)
                captured_out = new_stdout.getvalue()
                sys.stdout = old_stdout

            # Parse captured output blocks for rendering
            lines = captured_out.split("\n")
            for line in lines:
                if not line.strip():
                    continue
                
                # switching provider logs
                if "[FallbackChain] Attempting" in line:
                    provider_part = line.split("provider:")[-1].strip() if "provider:" in line else line
                    st.markdown(f"🔄 **SWITCHING MODEL →** `{provider_part}`")
                elif "[FallbackChain]" in line and "failed" in line.lower():
                    failed_part = line.split("Provider")[-1].split("failed")[0].strip() if "Provider" in line else line
                    st.markdown(f"⚠️ **FALLBACK TRIGGERED** — `{failed_part}` failed, trying next...")
                # ReAct step logs
                elif line.startswith("Thought:"):
                    st.markdown(f'<div class="thought-block">🧠 <b>{line}</b></div>', unsafe_allow_html=True)
                elif line.startswith("Action:"):
                    st.markdown(f'<div class="action-block">⚙️ <b>{line}</b></div>', unsafe_allow_html=True)
                elif line.startswith("Observation:"):
                    st.markdown(f'<div class="observation-block">👁️ <b>{line}</b></div>', unsafe_allow_html=True)
                else:
                    st.write(line)

            if success_run:
                status_box.update(label="✅ Reasoning successfully completed!", state="complete")
            else:
                status_box.update(label="❌ Reasoning loop execution failed!", state="error")

        # Save record for evaluation
        thought_count = captured_out.count("Thought:")
        action_count  = captured_out.count("Action:")
        last_metrics = tracker.session_metrics[-1] if tracker.session_metrics else {}
        total_tokens  = last_metrics.get("total_tokens", 0)
        prompt_tokens = last_metrics.get("prompt_tokens", 0)
        compl_tokens  = last_metrics.get("completion_tokens", 0)
        cost_est      = last_metrics.get("cost_estimate", 0.0)
        model_used    = last_metrics.get("model", gemini_model_input if "Live" in mode else "mock")

        failure_type = "✅ Success" if success_run else "❌ Error"
        run_record = {
            "run": len(st.session_state["eval_runs"]) + 1,
            "query_short": user_query_to_run[:45] + "..." if len(user_query_to_run) > 45 else user_query_to_run,
            "model": model_used,
            "latency_ms": run_latency_ms,
            "steps": thought_count,
            "actions": action_count,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": compl_tokens,
            "total_tokens": total_tokens,
            "cost_usd": round(cost_est, 6),
            "status": failure_type,
        }
        st.session_state["eval_runs"].append(run_record)

        # Output final result
        if success_run:
            st.success("Success!")
            st.markdown("### 🏆 Final Agent Answer")
            st.info(final_res)
            st.session_state["messages"].append({"role": "assistant", "content": final_res})
        else:
            st.error("Execution failed!")
            st.error(final_res)
            st.session_state["messages"].append({"role": "assistant", "content": f"⚠️ Error: {final_res}"})

        st.rerun()

# ═══════════════════════════════════════════════════════════
# 📊  EVALUATION METRICS DASHBOARD
# ═══════════════════════════════════════════════════════════
if st.session_state["eval_runs"]:
    st.markdown("---")
    st.markdown('<h2>📊 <span class="gradient-text">Evaluation Metrics Dashboard</span></h2>', unsafe_allow_html=True)
    st.caption("Tracks token efficiency, latency, loop count, and failure analysis across all runs in this session.")

    runs = st.session_state["eval_runs"]
    n = len(runs)
    avg_latency = sum(r["latency_ms"] for r in runs) / n
    avg_tokens  = sum(r["total_tokens"] for r in runs) / n
    success_pct = sum(1 for r in runs if "Success" in r["status"]) / n * 100
    total_cost  = sum(r["cost_usd"] for r in runs)

    # ── KPI Tiles ──
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🔁 Total Runs", n)
    k2.metric("⏱ Avg Latency", f"{avg_latency/1000:.2f}s",
              delta=f"{(runs[-1]['latency_ms'] - avg_latency)/1000:+.2f}s" if n > 1 else None)
    k3.metric("🪙 Avg Tokens", f"{avg_tokens:.0f}",
              delta=f"{runs[-1]['total_tokens'] - avg_tokens:+.0f}" if n > 1 else None)
    k4.metric("✅ Success Rate", f"{success_pct:.0f}%")

    st.markdown(f"""
    <div style='background:rgba(16,185,129,0.08);border:1px solid #10B981;border-radius:8px;
    padding:10px 16px;margin:8px 0;font-size:0.9em'>
    💰 <b>Estimated Total Session Cost:</b> <span style='color:#34D399'>${total_cost:.6f} USD</span>
    &nbsp;|&nbsp; 📦 <b>Total Tokens Used:</b> {sum(r['total_tokens'] for r in runs):,}
    </div>""", unsafe_allow_html=True)

    # ── Clear button ──
    if st.button("🗑 Clear Evaluation History", key="clear_eval"):
        st.session_state["eval_runs"] = []
        st.rerun()

    # ── Per-Run Table ──
    st.markdown("#### 📋 Per-Run Metrics")
    import pandas as pd
    df = pd.DataFrame(runs)[["run","model","latency_ms","steps","actions",
                               "prompt_tokens","completion_tokens","total_tokens","cost_usd","status","query_short"]]
    df.columns = ["Run","Model","Latency (ms)","Steps","Actions",
                  "Prompt Tokens","Completion Tokens","Total Tokens","Cost (USD)","Status","Query"]
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Charts ──
    if n >= 1:
        chart_c1, chart_c2 = st.columns(2)

        with chart_c1:
            st.markdown("#### ⏱ Latency per Run (ms)")
            latency_df = pd.DataFrame({"Run": [f"#{r['run']}" for r in runs],
                                        "Latency (ms)": [r["latency_ms"] for r in runs]})
            st.bar_chart(latency_df.set_index("Run"), color="#6366F1", use_container_width=True)

        with chart_c2:
            st.markdown("#### 🪙 Token Usage per Run")
            token_df = pd.DataFrame({
                "Run": [f"#{r['run']}" for r in runs],
                "Prompt": [r["prompt_tokens"] for r in runs],
                "Completion": [r["completion_tokens"] for r in runs],
            })
            st.bar_chart(token_df.set_index("Run"), use_container_width=True)

        step_df = pd.DataFrame({"Run": [f"#{r['run']}" for r in runs],
                                 "Steps (Thought→Action)": [r["steps"] for r in runs]})
        st.markdown("#### 🔄 Loop Count (ReAct Steps) per Run")
        st.bar_chart(step_df.set_index("Run"), color="#A855F7", use_container_width=True)

    # ── Failure Analysis ──
    st.markdown("#### 🔍 Failure Analysis")
    from collections import Counter
    status_counts = Counter(r["status"] for r in runs)
    fa_cols = st.columns(len(status_counts) or 1)
    for col, (status, count) in zip(fa_cols, status_counts.items()):
        color = "#10B981" if "Success" in status else "#F87171" if "Error" in status or "Timeout" in status else "#FBBF24"
        col.markdown(
            f'<div style="background:rgba(30,41,59,0.6);border:1px solid {color};border-radius:10px;'
            f'padding:14px;text-align:center">'
            f'<div style="font-size:1.8em;font-weight:800;color:{color}">{count}</div>'
            f'<div style="font-size:0.85em;color:#94A3B8">{status}</div></div>',
            unsafe_allow_html=True
        )
