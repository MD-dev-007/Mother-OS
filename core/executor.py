from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

from core.arg_validator import validate_and_fix_args
from core.state import AgentState
from tools.registry import TOOL_REGISTRY
from utils.path_resolver import resolve_system_path
from utils.resolver import resolve_variables


class Executor:
    def __init__(self) -> None:
        pass

    def execute(self, state: AgentState) -> AgentState:
        # If planner already decided final, just pass through.
        if bool(state.get("final", False)):
            return state

        next_state: AgentState = dict(state)
        tool_outputs: Dict[str, Any] = dict(next_state.get("tool_outputs", {}))
        step_history = list(next_state.get("step_history", []))

        # Find the most recent planner step and read its planned actions.
        last_planner = None
        for item in reversed(step_history):
            if isinstance(item, dict) and item.get("type") == "planner":
                last_planner = item
                break

        if not isinstance(last_planner, dict):
            next_state["final"] = True
            next_state["response"] = "No planner step found."
            next_state["step_history"] = step_history
            return next_state

        actions = last_planner.get("actions")
        if not isinstance(actions, list) or not actions:
            next_state["final"] = True
            next_state["response"] = "Planner produced no actions."
            next_state["step_history"] = step_history
            return next_state

        # Phase 1: resolve + validate all actions (do not execute if any invalid).
        planned: List[Tuple[str, Dict[str, Any], str]] = []
        for i, action in enumerate(actions):
            if not isinstance(action, dict):
                continue

            tool_name = action.get("tool")
            args = action.get("args", {}) or {}
            output_key = action.get("output_key") or f"tool_output_{i+1}"

            if not isinstance(tool_name, str) or tool_name not in TOOL_REGISTRY:
                next_state["final"] = True
                next_state["response"] = f"Unknown tool: {tool_name}"
                next_state["step_history"] = step_history
                return next_state
            if not isinstance(args, dict):
                args = {}
            if not isinstance(output_key, str) or not output_key.strip():
                output_key = f"tool_output_{i+1}"

            tool = TOOL_REGISTRY[tool_name]
            resolved_args = resolve_variables(args, tool_outputs)
            check = validate_and_fix_args(tool, resolved_args)
            if not check.get("valid"):
                next_state["final"] = True
                next_state["response"] = check.get("message") or "Invalid tool arguments."
                next_state["pending_arg_prompt"] = {
                    "missing_fields": check.get("missing_fields") or [],
                    "message": check.get("message") or "",
                    "tool": tool_name,
                }
                next_state["step_history"] = step_history
                return next_state

            planned.append((tool_name, check["fixed_args"], output_key))

        # Phase 2: execute in order.
        outputs: Dict[str, Any] = {}
        executor_summary: Dict[str, Any] = {}

        for tool_name, fixed_args, output_key in planned:
            tool = TOOL_REGISTRY[tool_name]
            result: Dict[str, Any] = tool.run(fixed_args)

            outputs[output_key] = result
            tool_outputs[output_key] = result
            executor_summary: Dict[str, Any] = {
                "tool": tool_name,
                "args": fixed_args,
                "output": result,
            }
            if tool_name == "file.read":
                rp = result.get("resolved_path")
                if not isinstance(rp, str) or not rp.strip():
                    p_arg = fixed_args.get("path")
                    if isinstance(p_arg, str) and p_arg.strip():
                        try:
                            rp = resolve_system_path(p_arg.strip())
                        except Exception:
                            rp = p_arg.strip()
                    else:
                        rp = ""
                ext = os.path.splitext(rp)[1].lower() if rp else ""
                file_type = ext[1:] if ext.startswith(".") else (ext or "unknown")
                executor_summary["file_read"] = {
                    "resolved_path": rp,
                    "file_type": file_type or "unknown",
                    "read_status": result.get("status"),
                }

        # Store executor step.
        step_history.append(
            {
                "type": "executor",
                "outputs": outputs,
                # Compatibility for existing UI visualizer:
                "executor": executor_summary,
            }
        )
        next_state["tool_outputs"] = tool_outputs
        next_state["step_history"] = step_history

        # Increment loop counters only; planner controls finalization.
        next_state["step_count"] = int(next_state.get("step_count", 0)) + 1
        next_state["step"] = int(next_state.get("step", 0)) + 1
        return next_state
