import os
import re
import json
import csv
import importlib
from typing import List, Dict, Any, Optional
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger

class ReActAgent:
    """
    A ReAct-style Agent that follows the Thought-Action-Observation loop.
    Implements the core loop logic and flight tool execution.
    """
    
    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 5):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.history = []

    def get_system_prompt(self) -> str:
        """
        System prompt for the Flight Search and Hold ReAct Agent.
        """
        tool_descriptions = "\n".join([f"- {t['name']}: {t['description']}" for t in self.tools])
        return f"""You are a Flight Search, Compare, and Hold ReAct Agent.

Your job is to help users search, compare flights, collect & validate passenger information, manage temporary holds, and generate receipts (text invoices and physical PDFs).

Available tools:
{tool_descriptions}

Rules & Guidelines:
1. **Always search or compare flights first** before attempting a booking, hold, or invoice.
2. **Flight Search & Comparison**: Use `search_flights` for basic route searching or `compare_flights` for a detailed ASCII comparison matrix. For productivity-oriented nomads, use `find_productivity_flights` to find flights scored by Wi-Fi, outlets, and legroom comfort.
3. **Passenger Info Validation**: You must collect passenger details (Name, Email, Phone) and validate them before generating an invoice or booking confirmation. Use `collect_personal_info`, `collect_address_info`, or `collect_travel_preferences` for single categories. For comprehensive inputs, use `validate_all_user_info` for maximum efficiency.
4. **Flight Holds**: Only place holds when explicitly requested. Use `hold_flight` based on a valid booking token or flight number. A temporary hold is not a paid booking — do not request passport or credit card numbers.
5. **Invoice & PDF Receipts**: After a hold is created or the traveler confirms selection, generate an invoice using `generate_invoice`. Immediately after generating the invoice, call `generate_invoice_pdf` to write a physical PDF receipt on disk and output the path to the user.
6. **No Hallucinations**: Never fabricate flight data, booking tokens, hold codes, prices, or PDF paths. Always use actual observations returned by tools.

Use this exact format:
Thought: brief reasoning about what to do next
Action: tool_name(argument_name="value", another_argument="value")

After writing an Action, stop immediately and wait for Observation.

When finished, use:
Final Answer: clear response summarizing everything resolved for the user.

Few-Shot Example (Combined Booking Pipeline):
User: Search and compare flights from CDG to AUS on 2026-03-03. Find the best recommended one. Then, validate passenger Nguyen Van A (email: vana@email.com, phone: 0901234567), put a 15-minute hold on it, and generate an invoice with PDF.

Thought: First, I will search and compare flights from CDG to AUS sorted by the recommended score.
Action: compare_flights(departure_airport="CDG", arrival_airport="AUS", departure_date="2026-03-03", sort_by="recommended")

Observation: Found 2 options. Option 1: British Airways, price 520 USD, booking_token sample_token_1, flight_id flight-854624, airline "British Airways", flight_number "BA 191", departure_time "2026-03-03 12:10", arrival_time "2026-03-03 16:50", duration "13h 40m", stops 1.

Thought: The best recommended flight is Option 1. Now I will collect and validate the passenger's personal info.
Action: collect_personal_info(passenger_name="Nguyen Van A", passenger_email="vana@email.com", passenger_phone="0901234567")

Observation: {{"status": "success", "message": "✓ Thông tin cá nhân hợp lệ.", "personal_info": {{"passenger_name": "Nguyen Van A", "passenger_email": "vana@email.com", "passenger_phone": "0901234567"}}}}

Thought: Passenger details validated successfully. Next, I will place a 15-minute hold on the recommended flight using its booking token and flight details.
Action: hold_flight(booking_token="sample_token_1", passenger_count=1, hold_minutes=15, expected_price=520.0)

Observation: {{"status": "held", "hold_code": "HOLD-E5A2B9C1", "booking_token": "sample_token_1", "passenger_count": 1, "hold_minutes": 15, "expires_at": "2026-03-03 12:25:00", "message": "Temporary hold created."}}

Thought: The hold is created with hold_code HOLD-E5A2B9C1. Now I will generate the text invoice using the flight details.
Action: generate_invoice(passenger_name="Nguyen Van A", passenger_email="vana@email.com", passenger_phone="0901234567", flight_id="flight-854624", airline="British Airways", departure_airport="CDG", arrival_airport="AUS", departure_time="2026-03-03 12:10", arrival_time="2026-03-03 16:50", duration="13h 40m", price_per_person=520.0, passengers=1, currency="USD", booking_link="https://www.google.com/travel/flights?booking_token=sample_token_1", stops=1)

Observation: {{"status": "success", "booking_ref": "BK-2F9A1B8C", "receipt_text": "...[beautiful ASCII receipt]...", "invoice_data": {{"booking_ref": "BK-2F9A1B8C", "passenger": {{"name": "Nguyen Van A", "email": "vana@email.com", "phone": "0901234567"}}, "flight": {{"flight_id": "flight-854624", "airline": "British Airways", "departure_airport": "CDG", "arrival_airport": "AUS", "departure_time": "2026-03-03 12:10", "arrival_time": "2026-03-03 16:50", "duration": "13h 40m", "stops": 1}}, "pricing": {{"price_per_person": 520.0, "passengers": 1, "subtotal": 520.0, "service_fee": 26.0, "total_price": 546.0, "currency": "USD"}}}}}}

Thought: Invoice generated successfully with booking_ref BK-2F9A1B8C. Now I will generate the physical PDF invoice using the invoice_result dictionary.
Action: generate_invoice_pdf(invoice_result={{"status": "success", "booking_ref": "BK-2F9A1B8C", "receipt_text": "...", "invoice_data": {{"booking_ref": "BK-2F9A1B8C", "passenger": {{"name": "Nguyen Van A", "email": "vana@email.com", "phone": "0901234567"}}, "flight": {{"flight_id": "flight-854624", "airline": "British Airways", "departure_airport": "CDG", "arrival_airport": "AUS", "departure_time": "2026-03-03 12:10", "arrival_time": "2026-03-03 16:50", "duration": "13h 40m", "stops": 1}}, "pricing": {{"price_per_person": 520.0, "passengers": 1, "subtotal": 520.0, "service_fee": 26.0, "total_price": 546.0, "currency": "USD"}}}}}}, output_path="invoice_BK-2F9A1B8C.pdf")

Observation: {{"status": "success", "pdf_path": "/absolute/path/invoice_BK-2F9A1B8C.pdf", "booking_ref": "BK-2F9A1B8C"}}

Thought: I have successfully completed the entire travel booking process and have all confirmation details.
Final Answer: I have successfully completed your travel request:
1. **Best Flight Recommended**: British Airways flight from CDG to AUS ($520.00).
2. **Passenger Validated**: Nguyen Van A (vana@email.com | 0901234567).
3. **Flight Hold Placed**: Placed a 15-minute hold. Hold Code: **HOLD-E5A2B9C1**.
4. **Invoice Generated**: Booking Reference: **BK-2F9A1B8C**. Total: $546.00 USD (includes 5% service fee).
5. **PDF Receipt**: Written successfully to disk at: `invoice_BK-2F9A1B8C.pdf`.
    """.strip()

    def run(self, user_input: str) -> str:
        """
        # Executes the ReAct Thought-Action-Observation loop.
        """
        logger.log_event("AGENT_START", {"input": user_input, "model": self.llm.model_name})
        
        conversation_context = f"User Request: {user_input}\n"
        steps = 0

        while steps < self.max_steps:
            # Generate response from the LLM fallback chain
            response = self.llm.generate(
                prompt=conversation_context,
                system_prompt=self.get_system_prompt(),
            )
            
            content = response.get("content", "").strip()
            latency = response.get("latency_ms", 0)
            logger.log_event("LLM_RESPONSE", {"content": content, "latency_ms": latency})
            
            print(f"\n{content}")
            
            # 1. Check if the LLM reached a Final Answer
            if "Final Answer:" in content:
                final_answer_match = re.search(r"Final Answer:\s*(.*)", content, re.DOTALL)
                final_answer = final_answer_match.group(1).strip() if final_answer_match else content
                logger.log_event("AGENT_END", {"steps": steps + 1, "status": "success"})
                return final_answer
                
            # 2. Check if the LLM decided to take an Action
            action_match = re.search(r"Action:\s*([a-zA-Z0-9_]+)(?:\((.*)\))?", content)
            if action_match:
                tool_name = action_match.group(1).strip()
                tool_args = action_match.group(2).strip() if action_match.group(2) else ""
                
                # Execute the tool
                observation = self._execute_tool(tool_name, tool_args)
                logger.log_event("TOOL_EXECUTE", {"tool": tool_name, "args": tool_args, "observation": observation})
                
                print(f"Observation: {observation}")
                
                # Append to conversation context
                conversation_context += f"\n{content}\nObservation: {observation}\n"
            else:
                # If neither is found, fallback to treating content as the answer
                logger.log_event("AGENT_END", {"steps": steps + 1, "status": "no_action_fallback"})
                return content
                
            steps += 1
            
        logger.log_event("AGENT_END", {"steps": steps, "status": "timeout"})
        return "The agent timed out before reaching a final answer."

    def _execute_tool(self, tool_name: str, args_str: str) -> str:
        """
        Helper method to execute tools dynamically. Parses various argument string formats.
        """
        func = self._resolve_tool(tool_name)
        if not func:
            logger.log_event("UNKNOWN_TOOL", {"tool": tool_name})
            return f"Tool {tool_name} not found."
        
        try:
            kwargs, positional_args = self._parse_tool_args(args_str)
            if kwargs:
                result = func(*positional_args, **kwargs)
            elif positional_args:
                result = func(*positional_args)
            else:
                result = func()
            return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        except Exception as e:
            logger.log_event("TOOL_ERROR", {"tool": tool_name, "args": args_str, "error": str(e)})
            return f"Error executing tool '{tool_name}' with args '{args_str}': {e}"

    def _resolve_tool(self, tool_name: str):
        """Resolve tools from injected tool definitions or known tool modules."""
        for tool in self.tools:
            if tool.get("name") == tool_name and callable(tool.get("function")):
                return tool["function"]

        for module_name in (
            "src.tools.flight_tools",
            "src.tools.hold_tools",
            "src.tools.invoice_tools",
            "src.tools.user_info_tools",
            "src.tools.flight_comparison",
        ):
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                continue
            func = getattr(module, tool_name, None)
            if callable(func):
                return func
        return None

    def _parse_tool_args(self, args_str: str):
        """Parse JSON args or function-call style key=value arguments."""
        cleaned_args = args_str.strip()
        if cleaned_args.startswith("{") and cleaned_args.endswith("}"):
            args = json.loads(cleaned_args)
            if isinstance(args, dict):
                return args, []
            if isinstance(args, list):
                return {}, args

        if cleaned_args.startswith("(") and cleaned_args.endswith(")"):
            cleaned_args = cleaned_args[1:-1]
        if not cleaned_args:
            return {}, []

        reader = csv.reader([cleaned_args], skipinitialspace=True)
        args = next(reader)

        kwargs = {}
        positional_args = []
        for arg in args:
            arg_cleaned = arg.strip()
            if "=" in arg_cleaned:
                key, value = arg_cleaned.split("=", 1)
                kwargs[key.strip()] = self._coerce_arg_value(value.strip().strip('\'"'))
            else:
                positional_args.append(self._coerce_arg_value(arg_cleaned.strip('\'"')))
        return kwargs, positional_args

    def _coerce_arg_value(self, value: str):
        lowered = value.lower()
        if lowered in {"none", "null"}:
            return None
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if re.fullmatch(r"-?\d+", value):
            return int(value)
        if re.fullmatch(r"-?\d+\.\d+", value):
            return float(value)
        return value

