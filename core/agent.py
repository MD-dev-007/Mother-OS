from __future__ import annotations

from langgraph.graph import END, StateGraph

from core.arg_validator import validate_and_fix_args
from core.executor import Executor
from core.planner import Planner
from core.state import AgentState
from core.validator import validate_action
from llm.client import LLMClient
from tools.registry import TOOL_REGISTRY
from utils.resolver import resolve_variables


MAX_STEPS = 5


def build_agent():
    llm = LLMClient()
    planner = Planner(llm=llm)

    executor = Executor()

    graph = StateGraph(AgentState)

    def planner_node(state: AgentState) -> AgentState:
        return planner.plan(state)

    def executor_node(state: AgentState) -> AgentState:
        return executor.execute(state)

    def validator_node(state: AgentState) -> AgentState:
        next_state: AgentState = dict(state)
        # Validator checks planned actions from the latest planner step.
        pending = None
        step_history = list(next_state.get("step_history", []))
        tool_outputs = dict(next_state.get("tool_outputs", {}))
        last_planner = None
        last_planner_idx = -1
        for i in range(len(step_history) - 1, -1, -1):
            item = step_history[i]
            if isinstance(item, dict) and item.get("type") == "planner":
                last_planner = item
                last_planner_idx = i
                break
        actions = []
        if isinstance(last_planner, dict) and isinstance(last_planner.get("actions"), list):
            actions = last_planner.get("actions", [])

        # 1) Argument validation + auto-fix (before approval rules).
        if actions and last_planner_idx >= 0:
            updated_actions: list = []
            for action in actions:
                if not isinstance(action, dict):
                    updated_actions.append(action)
                    continue
                tool_name = action.get("tool")
                raw_args = action.get("args", {}) or {}
                if not isinstance(tool_name, str) or tool_name not in TOOL_REGISTRY:
                    updated_actions.append(action)
                    continue
                if not isinstance(raw_args, dict):
                    raw_args = {}
                tool = TOOL_REGISTRY[tool_name]
                resolved = resolve_variables(dict(raw_args), tool_outputs)
                check = validate_and_fix_args(tool, resolved)
                if not check.get("valid"):
                    next_state["pending_arg_prompt"] = {
                        "missing_fields": check.get("missing_fields") or [],
                        "message": check.get("message") or "",
                        "tool": tool_name,
                    }
                    next_state["response"] = check.get("message") or "Invalid tool arguments."
                    next_state["final"] = True
                    next_state["pending_action"] = None
                    return next_state
                new_action = dict(action)
                new_action["args"] = check["fixed_args"]
                updated_actions.append(new_action)

            patched = dict(last_planner)
            patched["actions"] = updated_actions
            step_history[last_planner_idx] = patched
            next_state["step_history"] = step_history
            actions = updated_actions

        for idx, action in enumerate(actions):
            decision = validate_action(action)
            if decision.get("requires_approval") is True:
                pending = dict(action) if isinstance(action, dict) else action
                if isinstance(pending, dict):
                    pre_actions = []
                    for prior in actions[:idx]:
                        if isinstance(prior, dict):
                            pre_actions.append(dict(prior))
                    pending["_pre_actions"] = pre_actions
                    requested_path = decision.get("requested_path")
                    resolved_path = decision.get("resolved_path")
                    if isinstance(requested_path, str) and isinstance(resolved_path, str):
                        args = pending.get("args", {})
                        if not isinstance(args, dict):
                            args = {}
                        args["requested_path"] = requested_path
                        args["resolved_path"] = resolved_path
                        pending["args"] = args
                break

        next_state["pending_action"] = pending
        if pending is not None:
            next_state["final"] = False
            next_state["response"] = ""
        return next_state

    def route_after_validator(state: AgentState) -> str:
        if state.get("pending_arg_prompt") is not None:
            return END
        # If an approval is required, stop the graph.
        if state.get("pending_action") is not None:
            return END
        return "executor"

    def route_after_executor(state: AgentState) -> str:
        if state.get("pending_arg_prompt") is not None:
            return END
        # Fast mode: execute tool(s) once, then stop IF we already have a final response.
        # If the planner returned actions but didn't produce a final response yet,
        # run the planner one more time so the UI gets a user-facing answer.
        if state.get("mode") == "fast":
            step_count = int(state.get("step_count", 0))
            response = state.get("response") or ""
            tool_outputs = state.get("tool_outputs") if isinstance(state.get("tool_outputs"), dict) else {}
            if step_count <= 1 and not bool(response) and len(tool_outputs) > 0:
                return "planner"
            return END
        # Stop if planner marked final or we hit max steps.
        if bool(state.get("final", False)):
            return END
        if state.get("pending_action") is not None:
            return END
        if int(state.get("step_count", 0)) >= MAX_STEPS:
            return END
        return "planner"

    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "validator")
    graph.add_node("validator", validator_node)
    graph.add_conditional_edges(
        "validator",
        route_after_validator,
        {
            "executor": "executor",
            END: END,
        },
    )

    graph.add_conditional_edges(
        "executor",
        route_after_executor,
        {
            "planner": "planner",
            END: END,
        },
    )

    return graph.compile()

