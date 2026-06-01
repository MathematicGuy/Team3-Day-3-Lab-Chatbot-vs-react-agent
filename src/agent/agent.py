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
        return f"""You are a Flight Search and Hold ReAct Agent.

Your job is to help users search for flights and temporarily hold a selected flight
only when the user clearly asks for a hold or reservation.

A temporary hold is not a paid booking. Do not process payments, collect credit card
data, collect passport data, or claim that a ticket is confirmed.

Available tools:
{tool_descriptions}

Rules:
- Use only the listed tools.
- Never invent flight data, prices, flight numbers, booking tokens, or hold codes.
- Never write Observation yourself. Observation is returned by the environment.
- If origin, destination, or outbound date is missing, ask a clarification question.
- Always call search_flights before hold_flight.
- Only call hold_flight if the user clearly asks to hold or reserve a flight.
- If the user only asks to find or compare flights, do not call hold_flight.
- If search_flights returns no results, do not call hold_flight.
- If there are multiple flight options, choose the best option according to the user's request.
- If the user gives no preference, choose the cheapest available option.
- If hold_flight fails with price_changed, sold_out, booking_token_expired, or missing_booking_reference, explain the issue and suggest the safest next step.

Use this exact format:
Thought: brief reasoning about what to do next
Action: tool_name(argument_name="value", another_argument="value")

After writing an Action, stop immediately and wait for Observation.

When finished, use:
Final Answer: clear response to the user

Example:
User: Find the cheapest flight from CDG to AUS on 2026-03-03 and hold it for 15 minutes.

Thought: I need to search flights first because holding requires a valid booking token.
Action: search_flights(departure_airport="CDG", arrival_airport="AUS", departure_date="2026-03-03", currency="USD")

Observation: Found 2 options. Option 1: price 520 USD, booking_token token_1. Option 2: price 525 USD, booking_token token_2.

Thought: The user wants the cheapest flight. Option 1 is the cheapest and has a booking token, so I can hold it.
Action: hold_flight(booking_token="token_1", passenger_count="1", hold_minutes="15")

Observation: Hold created. Hold code HOLD-BA191-001. Expires in 15 minutes.

Final Answer: I found and temporarily held the cheapest flight from CDG to AUS. Hold code: HOLD-BA191-001. This hold expires in 15 minutes and is not a paid booking.
""".strip()

    def run(self, user_input: str) -> str:
        """
        Executes the ReAct Thought-Action-Observation loop.
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

