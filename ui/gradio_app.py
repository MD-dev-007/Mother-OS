from __future__ import annotations

import os
import sys
import json
import time
import uuid
from typing import Any, List, Tuple

import gradio as gr


# Allow running via: python ui/gradio_app.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.agent import build_agent
from core.intent_router import detect_intent
from core.executor import Executor
from llm.client import LLMClient
from tools.registry import TOOL_REGISTRY


agent = build_agent()
llm = LLMClient()
executor = Executor()

#region debug logging
LOG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "debug-29a5ef.log"))


def _debug_log(hypothesisId: str, location: str, message: str, data: dict) -> None:
    # NDJSON append. Keep logs small and non-sensitive.
    try:
        payload = {
            "sessionId": "29a5ef",
            "id": f"log_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}",
            "timestamp": int(time.time() * 1000),
            "location": location,
            "message": message,
            "data": data,
            "hypothesisId": hypothesisId,
        }
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        # Never break the UI on logging issues.
        pass


#endregion

def format_steps(step_history: Any) -> str:
    if not step_history:
        return "No steps executed"

    output = ""
    for i, step in enumerate(step_history):
        output += f"Step {i+1}:\n{step}\n\n"
    return output.strip()


def _summarize_step(step: dict) -> Tuple[str, str, str]:
    step_type = step.get("type")

    # New multi-action planner step format.
    if step_type == "planner":
        node_type = "planner"
        actions = step.get("actions")
        if isinstance(actions, list) and actions:
            tools: List[str] = []
            for a in actions:
                if isinstance(a, dict) and isinstance(a.get("tool"), str):
                    tools.append(a["tool"])
            action = ", ".join(tools) if tools else ""
            summary = (
                f"Planner: {len(actions)} action(s)"
                + (f" -> {action}" if action else "")
            )
        else:
            summary = "Planner: final response" if step.get("final") else "Planner decision"
            action = ""
        return node_type, action, summary

    # New multi-action executor step format.
    if step_type == "executor":
        node_type = "executor"
        outputs = step.get("outputs")
        if isinstance(outputs, dict):
            output_keys = [k for k in outputs.keys() if isinstance(k, str)]
            action = ", ".join(output_keys[:5]) if output_keys else ""
            summary = f"Executor: produced {len(output_keys)} output(s)"
        else:
            # Fallback to old UI compat fields.
            ex = step.get("executor", {}) if isinstance(step.get("executor"), dict) else {}
            tool = ex.get("tool")
            action = str(tool) if tool else ""
            summary = f"Executor: ran tool '{tool}'" if tool else "Executor run"
        return node_type, action, summary

    # Backward-compat UI fallback.
    if "planner_json" in step or "planner_error" in step:
        node_type = "planner"
        action = ""
        summary = "Planner decision"
        pj = step.get("planner_json")
        if isinstance(pj, dict):
            if pj.get("final") is True:
                summary = "Planner: final response"
            elif pj.get("final") is False:
                act = pj.get("action", {})
                tool = act.get("tool")
                if tool:
                    action = str(tool)
                    summary = f"Planner: call tool '{tool}'"
        return node_type, action, summary

    if "executor" in step:
        node_type = "executor"
        ex = step.get("executor", {})
        tool = ex.get("tool")
        action = str(tool) if tool else ""
        summary = f"Executor: ran tool '{tool}'" if tool else "Executor run"
        return node_type, action, summary

    return "unknown", "", "Unknown step"


def _build_graph_markdown(intent: str) -> str:
    # Mermaid graph with explicit node styling so text stays readable.
    base = (
        "```mermaid\n"
        "graph LR\n"
        "  User[User]\n"
        "  Intent[Intent]\n"
        "  LLM[LLMClient]\n"
        "  Planner[Planner]\n"
        "  Executor[Executor]\n"
        "  End[End]\n"
        "  style User fill:#eb4034,stroke:#94a3b8,color:#020617\n"
        "  style Intent fill:#eb4034,stroke:#94a3b8,color:#020617\n"
        "  style LLM fill:#eb4034,stroke:#94a3b8,color:#020617\n"
        "  style Planner fill:#eb4034,stroke:#94a3b8,color:#020617\n"
        "  style Executor fill:#eb4034,stroke:#94a3b8,color:#020617\n"
        "  style End fill:#eb4034,stroke:#94a3b8,color:#020617\n"
    )
    if intent == "respond":
        body = (
            "  User --> Intent\n"
            "  Intent --> LLM[LLMClient]\n"
            "  LLM --> End\n"
        )
    else:
        body = (
            "  User --> Intent\n"
            "  Intent --> Planner\n"
            "  Planner --> Executor\n"
            "  Executor --> End\n"
        )
    return f"{base}{body}```"


def _build_step_summaries(step_history: Any) -> Tuple[str, List[str]]:
    if not step_history:
        return "No steps executed", []

    lines: List[str] = []
    labels: List[str] = []
    for i, step in enumerate(step_history):
        if not isinstance(step, dict):
            continue
        node_type, action, summary = _summarize_step(step)
        idx = i + 1
        label = f"Step {idx} - {node_type}"
        labels.append(label)
        lines.append(f"**{label}**")
        if action:
            lines.append(f"- **Action**: `{action}`")
        lines.append(f"- **Summary**: {summary}")
        lines.append("")
    return "\n".join(lines).strip() or "No steps executed", labels


def _format_step_details(step: Any) -> str:
    if not isinstance(step, dict):
        return "No details available."
    node_type, action, summary = _summarize_step(step)
    parts = [f"**Node type**: {node_type}", f"**Summary**: {summary}"]

    if node_type == "planner":
        step_desc = step.get("step_description")
        if isinstance(step_desc, str) and step_desc.strip():
            parts.append(f"**Step**: {step_desc.strip()}")

        actions = step.get("actions")
        if isinstance(actions, list) and actions:
            parts.append("\n**Planned actions**:")
            for a in actions:
                if not isinstance(a, dict):
                    continue
                tool = a.get("tool") or ""
                output_key = a.get("output_key") or ""
                args = a.get("args") or {}
                args_compact = ""
                if isinstance(args, dict):
                    pairs = []
                    for k, v in args.items():
                        if isinstance(k, str) and v is not None:
                            pairs.append(f"{k}={str(v)[:50]}")
                    args_compact = ", ".join(pairs[:6])
                line = f"- `{tool}` -> `{output_key}`"
                if args_compact:
                    line += f" | args: {args_compact}"
                parts.append(line)

        # Backward compat details
        planner_json = step.get("planner_json")
        if not (isinstance(actions, list) and actions) and isinstance(planner_json, dict):
            parts.append("\n**Planner (compat)**:")
            parts.append(f"- {planner_json}")

        planner_error = step.get("planner_error")
        if isinstance(planner_error, str) and planner_error.strip():
            parts.append(f"\n**Error**: {planner_error}")

        return "\n".join(parts)

    if node_type == "executor":
        outputs = step.get("outputs")
        if isinstance(outputs, dict) and outputs:
            parts.append("\n**Executor outputs**:")
            for k, v in outputs.items():
                if not isinstance(k, str):
                    continue
                if isinstance(v, dict) and "status" in v:
                    status = v.get("status")
                    count = ""
                    if "emails" in v and isinstance(v.get("emails"), list):
                        count = f" (emails: {len(v['emails'])})"
                    elif "results" in v and isinstance(v.get("results"), list):
                        count = f" (results: {len(v['results'])})"
                    elif "files" in v and isinstance(v.get("files"), list):
                        count = f" (files: {len(v['files'])})"
                    elif "events" in v and isinstance(v.get("events"), list):
                        count = f" (events: {len(v['events'])})"
                    parts.append(f"- `{k}`: {status}{count}")
                else:
                    parts.append(f"- `{k}`: {str(v)[:120]}")
            return "\n".join(parts)

        executor = step.get("executor")
        if isinstance(executor, dict):
            parts.append("\n**Executor (compat)**:")
            parts.append(f"- {executor}")

        return "\n".join(parts)

    # Fallback
    if action:
        parts.append(f"**Action/tool**: `{action}`")
    return "\n".join(parts)


def chat(
    user_input: str,
    history: Any | None,
    steps_state: Any | None,
    pending_action_state: Any | None,
):
    raw_history = history or []
    normalized_history: List[dict] = []
    for item in raw_history:
        if isinstance(item, dict) and "role" in item and "content" in item:
            normalized_history.append(item)
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            user, bot = item
            normalized_history.append({"role": "user", "content": str(user)})
            normalized_history.append({"role": "assistant", "content": str(bot)})
    history = normalized_history

    steps_state = steps_state or []

    # --- Pending approval flow ---
    if pending_action_state is not None:
        action = pending_action_state if isinstance(pending_action_state, dict) else {}
        tool_name = action.get("tool") if isinstance(action, dict) else None
        args = action.get("args", {}) if isinstance(action, dict) else {}
        output_key = action.get("output_key") or "tool_output"
        prior_tool_outputs = action.get("_tool_outputs", {}) if isinstance(action, dict) else {}
        pre_actions = action.get("_pre_actions", []) if isinstance(action, dict) else []
        if not isinstance(prior_tool_outputs, dict):
            prior_tool_outputs = {}
        if not isinstance(pre_actions, list):
            pre_actions = []

        normalized = (user_input or "").strip().lower()
        is_yes = normalized in ("yes", "y")
        is_no = normalized in ("no", "n", "cancel")

        # Build UX message from the pending action.
        path = ""
        if isinstance(args, dict):
            path_val = args.get("path")
            if isinstance(path_val, str):
                path = path_val

        approval_msg = "⚠️ **Action requires approval**\n"
        if tool_name:
            approval_msg += f"Tool: {tool_name}\n"
        if path:
            approval_msg += f"Path: {path}\n"
        approval_msg += "Do you want to proceed? Reply with **yes** or **no**"

        if not (is_yes or is_no):
            history = history + [{"role": "user", "content": user_input}]
            history = history + [{"role": "assistant", "content": approval_msg}]
            steps_md, step_labels = _build_step_summaries(steps_state)
            return (
                history,
                _build_graph_markdown("act"),
                steps_md,
                _format_step_details(steps_state[-1]) if steps_state else "No step details.",
                steps_state,
                gr.update(choices=step_labels, value=None),
                pending_action_state,
            )

        if is_no:
            history = history + [{"role": "user", "content": user_input}]
            history = history + [{"role": "assistant", "content": "Action cancelled."}]
            steps_md, step_labels = _build_step_summaries(steps_state)
            details_md = _format_step_details(steps_state[-1]) if steps_state else "No step details."
            steps_selector_update = gr.update(
                choices=step_labels, value=step_labels[-1] if step_labels else None
            )
            return (
                history,
                _build_graph_markdown("act"),
                steps_md,
                details_md,
                steps_state,
                steps_selector_update,
                None,
            )

        # Approved -> execute pending action directly.
        if not isinstance(action, dict) or not isinstance(tool_name, str):
            history = history + [{"role": "user", "content": user_input}]
            history = history + [{"role": "assistant", "content": "Invalid pending action."}]
            return (
                history,
                _build_graph_markdown("act"),
                "**Approval failed: invalid action.**",
                "Invalid pending action.",
                steps_state,
                gr.update(choices=[], value=None),
                None,
            )

        try:
            _debug_log(
                hypothesisId="H6_UI_approved_pending_action",
                location="ui/gradio_app.py:chat/approval/execute",
                message="Executing approved pending action",
                data={"tool": tool_name, "output_key": output_key, "args_keys": list(args.keys()) if isinstance(args, dict) else []},
            )
        except Exception:
            pass

        exec_args: dict = {}
        if isinstance(args, dict):
            exec_args = dict(args)
        exec_args["_approved"] = True

        # Execute using the existing executor against a synthetic planner step,
        # so only the pending action is run.
        planned_actions: List[dict] = []
        for item in pre_actions:
            if isinstance(item, dict):
                planned_actions.append(dict(item))
        planned_actions.append(
            {
                "tool": tool_name,
                "args": exec_args,
                "output_key": str(output_key),
            }
        )

        temp_planner_step = {
            "type": "planner",
            "step_description": "Approved pending action",
            "actions": planned_actions,
            "final": False,
        }

        temp_state = {
            "query": user_input,
            "step_history": [temp_planner_step],
            "tool_outputs": dict(prior_tool_outputs),
            "pending_action": None,
            "final": False,
            "response": "",
            "step": 0,
            "step_count": 0,
        }
        exec_result_state = executor.execute(temp_state)

        # Extract the produced executor step.
        produced_steps = exec_result_state.get("step_history", []) if isinstance(exec_result_state, dict) else []
        executor_step = produced_steps[-1] if produced_steps else None
        result = (exec_result_state.get("tool_outputs") or {}).get(str(output_key))
        if not isinstance(executor_step, dict):
            executor_step = {
                "type": "executor",
                "outputs": {str(output_key): result},
                "executor": {"tool": tool_name, "args": {k: v for k, v in exec_args.items() if k != "_approved"}, "output": result},
            }

        steps_state = list(steps_state) + [executor_step]

        success_text = ""
        if isinstance(result, dict) and result.get("status") == "success":
            success_text = "File written successfully." if tool_name in ("file.write", "file.update") else "Action completed successfully."
        else:
            success_text = f"Action execution failed: {(result or {}).get('message') or (result or {})}"

        history = history + [{"role": "user", "content": user_input}]
        history = history + [{"role": "assistant", "content": success_text}]

        steps_md, step_labels = _build_step_summaries(steps_state)
        details_md = _format_step_details(steps_state[-1]) if steps_state else "No step details."
        steps_selector_update = gr.update(
            choices=step_labels, value=step_labels[-1] if step_labels else None
        )
        return (
            history,
            _build_graph_markdown("act"),
            steps_md,
            details_md,
            steps_state,
            steps_selector_update,
            None,
        )

    # --- Normal agent/LLM flow ---
    intent = detect_intent(user_input)
    if intent == "respond":
        response = llm.generate(user_input)
        steps = []
        graph_md = _build_graph_markdown(intent)
        history = history + [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": response},
        ]
        steps_md = "**Direct LLM response (no agent steps).**"
        details_md = "No step details."
        steps_state = []
        steps_selector_update = gr.update(choices=[], value=None)
        return history, graph_md, steps_md, details_md, steps_state, steps_selector_update, None

    # Agent path
    state = {
        "query": user_input,
        "step_history": [],
        "tool_outputs": {},
        "pending_action": None,
        "pending_arg_prompt": None,
        "final": False,
        "response": "",
        "step": 0,
        "step_count": 0,
    }
    result = agent.invoke(state)
    response = (result or {}).get("response") or ""
    steps = (result or {}).get("step_history", []) or []
    pending_action = (result or {}).get("pending_action")
    pending_arg_prompt = (result or {}).get("pending_arg_prompt")

    history = history + [
        {"role": "user", "content": user_input},
    ]

    graph_md = _build_graph_markdown("act")

    if pending_arg_prompt is not None and isinstance(pending_arg_prompt, dict):
        prompt_text = (pending_arg_prompt.get("message") or response or "").strip()
        if not prompt_text:
            prompt_text = "Some required information is missing for this action."
        history = history + [{"role": "assistant", "content": prompt_text}]
        steps_md, step_labels = _build_step_summaries(steps)
        details_md = _format_step_details(steps[-1]) if steps else "No step details."
        steps_selector_update = gr.update(
            choices=step_labels, value=step_labels[-1] if step_labels else None
        )
        return (
            history,
            graph_md,
            steps_md,
            details_md,
            steps,
            steps_selector_update,
            None,
        )

    # If validator stopped for approval, ask in chat.
    if pending_action is not None:
        if isinstance(pending_action, dict):
            pending_action = dict(pending_action)
            tool_outputs_map = (result or {}).get("tool_outputs", {})
            if isinstance(tool_outputs_map, dict):
                pending_action["_tool_outputs"] = tool_outputs_map
        args = pending_action.get("args", {}) if isinstance(pending_action, dict) else {}
        tool_name = pending_action.get("tool") if isinstance(pending_action, dict) else ""
        path = ""
        if isinstance(args, dict) and isinstance(args.get("path"), str):
            path = args.get("path")

        approval_msg = "⚠️ **Action requires approval**\n"
        approval_msg += f"Tool: {tool_name}\n"
        if path:
            approval_msg += f"Path: {path}\n"
        approval_msg += "Do you want to proceed? Reply with **yes** or **no**"

        history = history + [{"role": "assistant", "content": approval_msg}]

        steps_md, step_labels = _build_step_summaries(steps)
        details_md = _format_step_details(steps[-1]) if steps else "No step details."
        steps_selector_update = gr.update(
            choices=step_labels, value=step_labels[-1] if step_labels else None
        )

        _debug_log(
            hypothesisId="H7_UI_pending_action_set",
            location="ui/gradio_app.py:chat/pending_action",
            message="Pending action detected from agent result",
            data={"tool": tool_name, "has_path": bool(path), "output_key": pending_action.get("output_key") if isinstance(pending_action, dict) else None},
        )

        return (
            history,
            graph_md,
            steps_md,
            details_md,
            steps or [],
            steps_selector_update,
            pending_action,
        )

    # Final/no-approval response
    history = history + [{"role": "assistant", "content": response}]
    steps_md, step_labels = _build_step_summaries(steps)
    steps_state = steps or []
    details_md = _format_step_details(steps_state[-1]) if steps_state else "No step details."
    steps_selector_update = gr.update(
        choices=step_labels, value=step_labels[-1] if step_labels else None
    )
    return (
        history,
        graph_md,
        steps_md,
        details_md,
        steps_state,
        steps_selector_update,
        None,
    )


def select_step(selected: str, steps_state: Any) -> str:
    if not selected or not steps_state:
        return "No step selected."
    try:
        idx_str = selected.split()[1]
        idx = int(idx_str) - 1
    except Exception:
        return "Invalid step selection."
    if idx < 0 or idx >= len(steps_state):
        return "Invalid step selection."
    return _format_step_details(steps_state[idx])


def connect_google_account(nickname: str) -> str:
    nickname = (nickname or "").strip()
    if not nickname:
        return "Please enter an account nickname first."

    tool = TOOL_REGISTRY.get("google.account.add")
    if tool is None:
        return "google.account.add tool is not available."

    result = tool.run({"nickname": nickname})
    if (result or {}).get("status") == "success":
        account_name = (result or {}).get("account") or nickname
        return f"Connected Google account: **{account_name}**"
    return f"Failed to connect account: {(result or {}).get('message') or 'Unknown error'}"


with gr.Blocks() as app:
    with gr.Row():
        with gr.Column(scale=2):
            chatbot = gr.Chatbot(label="MotherOS Chat")
            msg = gr.Textbox(placeholder="Ask something...", label="Message")
            send = gr.Button("Send")
            account_nickname = gr.Textbox(label="Enter Account Nickname", placeholder="e.g. personal")
            connect_btn = gr.Button("Connect Google Account")
            connect_status = gr.Markdown()

        with gr.Column(scale=1):
            graph_output = gr.Markdown(label="Execution Graph")
            steps_output = gr.Markdown(label="Execution Steps")
            step_selector = gr.Radio(label="Select Step", choices=[], interactive=True)
            step_details = gr.Markdown(label="Step Details")
            steps_state = gr.State([])
            pending_action_state = gr.State(None)

    # Style the Gradio label container to have a red background for visibility.
    gr.HTML(
        "<style>.basic.label-container { background-color: #f87171 !important; }</style>"
    )

    send.click(
        chat,
        inputs=[msg, chatbot, steps_state, pending_action_state],
        outputs=[
            chatbot,
            graph_output,
            steps_output,
            step_details,
            steps_state,
            step_selector,
            pending_action_state,
        ],
    )
    msg.submit(
        chat,
        inputs=[msg, chatbot, steps_state, pending_action_state],
        outputs=[
            chatbot,
            graph_output,
            steps_output,
            step_details,
            steps_state,
            step_selector,
            pending_action_state,
        ],
    )

    step_selector.change(select_step, inputs=[step_selector, steps_state], outputs=step_details)
    connect_btn.click(connect_google_account, inputs=[account_nickname], outputs=[connect_status])


if __name__ == "__main__":
    app.launch()

