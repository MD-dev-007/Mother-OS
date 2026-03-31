# MotherOS – Current System (MVP)

## 1. Overview

- Queries are routed by intent:
  - `respond`: direct LLM response.
  - `act`: LangGraph agent execution.
- Agent flow is a LangGraph with validation and modes:
  - Reasoning mode: `planner -> validator -> executor -> planner` (loop until stop).
  - Fast mode: `planner -> validator -> executor -> end` (single pass).

## 2. Architecture (Current)

- **Intent Router**: keyword-based `respond` vs `act` split.
- **Planner**: LLM-based planner that emits structured JSON with a `mode` (`fast` or `reasoning`) and either a final response or an action list.
- **Argument Validator**: normalizes and validates tool arguments against each tool's `args_schema` (auto-fix types/defaults, detect missing required fields).
- **Safety Validator**: checks actions requiring user approval (sensitive operations and path normalization).
- **Executor**: executes one or more planned tool actions after variable/path resolution and argument validation, and records outputs.
- **Tool System**: base `Tool` class + centralized `TOOL_REGISTRY`.
- **LLM Client**: shared Gemini wrapper with fallback model behavior and safe error responses.
- **Interfaces**:
  - CLI entrypoint (`app/main.py`).
  - Gradio UI (`ui/gradio_app.py`) with step inspection and approval/arg-prompt flows.

## 3. Flow (Step-by-step)

- **Respond path**: User Query -> `LLMClient.generate()` -> text response.
- **Act path**:
  1) Planner creates final response or planned actions.
  2) Validator checks actions for approval requirements.
  3) If approval is required, graph ends with `pending_action`.
  4) Else Executor runs planned tools and stores outputs.
  5) Control loops back to Planner until stop condition.

## 4. Graph Stop Conditions

- Planner returns `{"final": true, ...}`.
- Validator sets a `pending_action` that requires user approval.
- `step_count` reaches `MAX_STEPS` (currently `5`).

## 5. State Structure

- **query**: user input string.
- **step_history**: planner/executor records.
- **tool_outputs**: accumulated output map keyed by `output_key`.
- **pending_action**: first sensitive action awaiting approval (if any).
- **step_count**: executor-loop counter.
- **final**: execution finalized flag.
- **response**: final response text (planner/direct response).
- **step**: generic step counter for planner/executor updates.

## 6. Planner Behavior

- Receives tool metadata from `TOOL_REGISTRY` (`name`, `description`, `args_schema`).
- Receives recent context (`tool_outputs` + recent `step_history`).
- Supports:
  - Final format: `{"final": true, "response": "..."}`
  - Action format: `{"final": false, "step_description": "...", "actions": [...]}`
- Backward compatibility:
  - Accepts old single `action` payload and normalizes to `actions`.
- Robustness:
  - Malformed planner output is treated as final with error-safe fallback.

## 7. Validator Behavior

- Sensitive tools currently gated:
  - `file.write`, `file.update`, `file.delete`
  - `email.send`, `drive.upload`, `calendar.create`
- If a planned action uses a sensitive tool:
  - `pending_action` is set and execution stops for explicit user approval.

## 8. Executor Behavior

- Reads latest planner step and executes planned actions in order.
- Resolves each action against `TOOL_REGISTRY`.
- Stores results under action `output_key` and in cumulative `tool_outputs`.
- Appends an executor step summary to `step_history`.
- Increments `step_count` and `step`.

## 9. Tools Implemented

- `file.read`: real filesystem read (size-capped).
- `file.write`: write file (approval required).
- `file.update`: overwrite/update file (approval required).
- `file.delete`: delete file (approval required).
- `web.search`: Serper-backed web search (`SERPER_API_KEY`).
- `email.read`: Gmail read via connected Google account credentials.
- `drive.list`: list Drive files for connected account.
- `calendar.get`: upcoming calendar events for connected account.
- `accounts.list`: list saved Google account nicknames.
- `google.account.add`: OAuth account connect flow and credential persistence.

## 10. LLM Setup

- **Provider**: Gemini via `ChatGoogleGenerativeAI`.
- **Configured in**: `config/settings.py` and `llm/client.py`.
- **Current default model**: `gemini-3.1-pro` (override with `GOOGLE_MODEL`).
- Fallback logic attempts `gemini-2.5-flash` then `gemini-2.0-flash` for model-not-found errors.

## 11. Current Limitations

- Memory modules exist but are currently placeholders (not integrated in runtime loop).
- Intent routing is keyword-based and can misclassify edge cases.
- Tool argument quality depends on planner output; no strict schema validator for all tools.
- Some UI graph labels are simplified and do not fully show validator/loop transitions.

## 12. Next Planned Improvements

- Integrate memory store/retrieval into planner context.
- Add stricter planner/tool argument validation.
- Improve intent detection beyond keyword heuristics.
- Expand approval UX and policy controls.
- Strengthen tool-specific error reporting and retries.

