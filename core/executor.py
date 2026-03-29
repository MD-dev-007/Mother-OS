from __future__ import annotations

from typing import Any, Dict

from core.state import AgentState
from tools.registry import TOOL_REGISTRY
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

        outputs: Dict[str, Any] = {}
        executor_summary: Dict[str, Any] = {}

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

            resolved_args = resolve_variables(args, tool_outputs)

            tool = TOOL_REGISTRY[tool_name]
            result: Dict[str, Any] = tool.run(resolved_args)

            outputs[output_key] = result
            tool_outputs[output_key] = result
            executor_summary = {
                "tool": tool_name,
                "args": resolved_args,
                "output": result,
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

