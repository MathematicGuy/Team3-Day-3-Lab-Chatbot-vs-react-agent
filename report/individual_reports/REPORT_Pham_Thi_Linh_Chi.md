# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Phạm Thị Linh Chi
- **Student ID**:  2A202600748
- **Date**: 2026-06-01

---
# I. Technical Contribution (15 Points)

My contributions to this project focused on improving the reasoning behavior of the ReAct Agent, implementing a new flight hold tool, and proposing improvements for system robustness.

## 1. System Prompt Enhancement in agent.py

One of my main contributions was modifying the `get_system_prompt()` method in `src/agent/agent.py`.

The ReAct Agent depends heavily on the quality of its system prompt because the prompt defines how the model reasons, when tools should be called, and how outputs should be formatted. To improve consistency, I revised the prompt structure and added more explicit instructions.

### Improvements Made

#### Clear Agent Role Definition

I specified that the agent is a **Flight Search and Hold ReAct Agent** whose responsibilities are limited to:

* Searching for flights.
* Comparing available options.
* Creating temporary flight holds when explicitly requested by the user.

I also added restrictions to prevent the agent from claiming that a reservation is a confirmed booking or requesting sensitive information such as payment details or passport information.

#### Tool Usage Rules

I added a set of operational rules, including:

* Only registered tools may be used.
* Flight data, booking tokens, and hold codes must never be fabricated.
* `search_flights` must be executed before `hold_flight`.
* The agent should not create a hold when the user only requests flight information.
* Missing travel information should trigger a clarification question.

These rules help align the model's reasoning process with the actual workflow implemented in the system.

#### Standardized ReAct Format

I explicitly required the model to follow the format:

```text
Thought:
Action:
Observation:
Final Answer:
```

This structure improves compatibility with the parser implemented inside the agent and makes the reasoning process easier to follow.

#### Few-Shot Example

I added a complete example showing how the agent should:

1. Search for flights.
2. Analyze the returned results.
3. Select the most appropriate option.
4. Create a temporary hold.
5. Generate the final response.

This example serves as guidance for the model when handling similar tasks.

---

## 2. Development of hold_tools.py

I implemented the file:

```python
src/tools/hold_tools.py
```

The purpose of this module is to simulate a temporary flight reservation process in a safe laboratory environment.

### hold_flight()

The `hold_flight()` function creates a temporary hold record and performs input validation before creating the reservation.

Implemented features include:

* UUID-based hold code generation.
* Passenger count validation.
* Hold duration validation.
* Verification that a booking reference exists.
* Automatic expiration time calculation.
* Temporary in-memory storage using `_HOLD_STORE`.

The function returns structured responses describing either a successful hold or a validation failure.

### get_hold()

The `get_hold()` function retrieves previously created hold records.

Its responsibilities include:

* Looking up hold information using a hold code.
* Returning hold details when available.
* Returning an error response when the hold does not exist.

### Error Handling

The implementation includes several validation checks such as:

* Invalid passenger count.
* Invalid hold duration.
* Missing booking reference.
* Invalid hold requests.
* Hold record not found.

These validations improve the reliability of the simulated booking workflow.

---

## 3. Error Handling Design Proposals

Beyond the implemented validations, I also explored additional error scenarios that could occur in a production environment.

Examples include:

* Expired booking tokens.
* Flight no longer available.
* Duplicate hold requests.
* Price changes between search and hold operations.
* System timeouts.

Although these scenarios were not fully implemented during the lab, documenting them helped identify potential weaknesses in the workflow and possible future improvements.

---

## 4. Flowchart Design

I created a flowchart illustrating the ReAct reasoning cycle used by the system.

The diagram describes how information moves through the agent:

```text
User Request
      ↓
   Thought
      ↓
    Action
      ↓
 Tool Execution
      ↓
 Observation
      ↓
 Next Thought
      ↓
 Final Answer
```

The flowchart was useful for understanding the interaction between reasoning and tool execution and helped communicate the system architecture during team discussions.

---

# II. Debugging Case Study (10 Points)

## Problem Description

During development, one challenge was ensuring that the language model generated actions in a format that could be interpreted correctly by the system.

For example, the model could produce:

```text
Action: search_flights
```

instead of providing the arguments required by the tool.

Because the ReAct Agent depends on tool execution, incorrectly formatted actions can interrupt the reasoning process.

---

## Diagnosis

After reviewing the agent architecture, I concluded that the issue was primarily related to prompt design rather than tool implementation.

The model must generate outputs that satisfy two different requirements:

1. Natural language reasoning.
2. Machine-readable tool calls.

Without clear instructions, the model may prioritize natural language generation and omit details required by the parser.

I also observed that some tools require multiple parameters, making correct argument generation especially important.

---

## Solution

To address this issue, I focused on improving the system prompt.

The modifications included:

* Defining a strict output format.
* Adding explicit examples of valid tool calls.
* Providing a complete ReAct workflow example.
* Clarifying when each tool should be used.

Rather than changing the parser logic, I improved the instructions given to the model so that generated actions would be closer to the expected format.

This experience demonstrated that prompt engineering plays a significant role in the overall reliability of an agent-based system.

---

# III. Personal Insights: Chatbot vs ReAct Agent (10 Points)

## 1. Reasoning Capability

The most significant difference between a traditional chatbot and a ReAct Agent is the ability to perform structured reasoning.

A chatbot generally follows a simple process:

```text
Input → Response
```

The ReAct Agent follows a multi-step workflow:

```text
Input
→ Thought
→ Action
→ Observation
→ Thought
→ Final Answer
```

This allows the agent to gather information from external tools before generating a response.

In the flight assistant project, the agent can retrieve flight data and make decisions based on actual search results rather than relying only on the model's internal knowledge.

---

## 2. Reliability

The ReAct Agent is more capable when solving multi-step tasks, but it is also more dependent on external components.

Its performance depends on:

* Prompt quality.
* Tool availability.
* Tool correctness.
* Model output formatting.

A chatbot is simpler because it does not require external tool execution. However, it cannot reliably solve tasks that require real-time or structured data.

This project showed that increased capability often comes with increased system complexity.

---

## 3. Importance of Observations

The Observation stage is one of the most important aspects of the ReAct framework.

Observations provide feedback from the environment and become the basis for the next reasoning step.

Instead of making assumptions, the agent can adapt its behavior according to the information returned by the tools.

This feedback loop makes ReAct Agents more grounded and task-oriented than traditional chatbots.

---

# IV. Future Improvements (5 Points)

## Scalability

A natural next step would be integrating Retrieval-Augmented Generation (RAG).

Potential knowledge sources include:

* Airline policies.
* Airport information.
* Customer support documentation.
* Travel regulations.

This would allow the system to answer both operational and informational questions.

---

## Multi-Agent Architecture

The system could also be extended into a multi-agent architecture.

Possible specialized agents include:

### Planner Agent

Responsible for understanding user goals and creating execution plans.

### Flight Agent

Responsible for flight search and itinerary analysis.

### Booking Agent

Responsible for reservation-related actions.

### Supervisor Agent

Responsible for validating outputs and monitoring agent behavior.

This separation of responsibilities would improve maintainability and scalability.

---

## Safety and Performance

Future improvements may also include:

* Tool permission validation.
* Prompt injection protection.
* Confirmation mechanisms before critical actions.
* Result caching.
* Automated testing for tools and prompts.

These additions would make the system more suitable for real-world deployment.

---

## Personal Contribution Summary

My primary contributions to this project were:

* Enhancing the system prompt in `agent.py`.
* Implementing `hold_tools.py`.
* Designing and documenting additional error-handling scenarios.
* Creating a flowchart describing the ReAct workflow.
* Analyzing prompt-related issues affecting tool invocation and agent behavior.
