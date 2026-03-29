from __future__ import annotations

from langgraph.graph import END, StateGraph

from core.executor import Executor
from core.planner import Planner
from core.state import AgentState
from core.validator import validate_action
from llm.client import LLMClient


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
        last_planner = None
        for item in reversed(step_history):
            if isinstance(item, dict) and item.get("type") == "planner":
                last_planner = item
                break
        actions = []
        if isinstance(last_planner, dict) and isinstance(last_planner.get("actions"), list):
            actions = last_planner.get("actions", [])

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
        # If an approval is required, stop the graph.
        if state.get("pending_action") is not None:
            return END
        return "executor"

    def route_after_executor(state: AgentState) -> str:
        # Fast mode: execute once, then stop.
        if state.get("mode") == "fast":
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

