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
- **LLM Client**: provider-switching LLM wrapper (Gemini AI Studio or Vertex AI) with fallback model behavior and safe error responses.
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
  - Best-effort JSON parsing is used (`safe_json_parse`) to recover when the model wraps JSON in extra text.

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

- `file.read`: multi-format filesystem reader via Unstructured (size-capped).
  - Supports common formats like `pdf`, `docx`, `txt`, `pptx`, and more.
  - For image files (e.g. `png`, `jpg`), `file.read` attempts layout+OCR extraction (requires the `tesseract` executable on PATH).
  - Output is capped for safety at 10,000 characters and may include `[TRUNCATED]`.
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

### Providers

- **Default provider**: Gemini (AI Studio) via `ChatGoogleGenerativeAI`.
- **Optional provider**: Vertex AI (Gemini on Vertex) via `google-cloud-aiplatform` / `vertexai`.
- **Provider switch**: set `LLM_PROVIDER=vertex` to use Vertex; otherwise defaults to `gemini`.

### Environment variables

- **Gemini (AI Studio)**:
  - `GOOGLE_API_KEY`
  - `GOOGLE_MODEL` (default `gemini-3.1-pro`)
  - `GOOGLE_TEMPERATURE`
- **Vertex AI**:
  - `GOOGLE_APPLICATION_CREDENTIALS` (service account JSON path)
  - `GOOGLE_PROJECT_ID`
  - `GOOGLE_REGION` (default `asia-south1`)
  - `GOOGLE_MODEL` (treated as the preferred Vertex model name when `LLM_PROVIDER=vertex`)

### Fallback behavior

- **Gemini (AI Studio)**: on model-not-found attempts `gemini-2.5-flash` then `gemini-2.0-flash`.
- **Vertex AI**: attempts the requested model, then falls back to `gemini-1.5-pro`, then `gemini-1.5-flash`.

### Failure safety

- Auth/quota/model errors should not crash the agent loop; the system returns a safe final response like:
  - `{"final": true, "response": "LLM temporarily unavailable."}`

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

