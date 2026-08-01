from __future__ import annotations

import json

from core.state import AgentState
from llm.client import LLMClient
from llm.prompts import build_planner_prompt
from llm.utils import PlannerOutputError, parse_planner_json, safe_json_parse
from tools.registry import TOOL_REGISTRY


class Planner:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def plan(self, state: AgentState) -> AgentState:
        query = state.get("query", "")
        tools_payload = []
        for tool in TOOL_REGISTRY.values():
            tools_payload.append(
                {
                    "name": getattr(tool, "name", ""),
                    "description": getattr(tool, "description", ""),
                    "args_schema": getattr(tool, "args_schema", {}) or {},
                }
            )
        tools_json = json.dumps(tools_payload, ensure_ascii=False)

        # Provide previous context so planner can reason over past actions.
        prev_history = list(state.get("step_history", []))
        prev_tools = dict(state.get("tool_outputs", {}))
        context_snippet = json.dumps(
            {"tool_outputs": prev_tools, "step_history": prev_history[-5:]},
            ensure_ascii=False,
        )

        enriched_query = f"{query}\n\nPrevious context:\n{context_snippet}"
        prompt = build_planner_prompt(query=enriched_query, tools_json=tools_json)
        text = self._llm.generate(prompt)

        next_state: AgentState = dict(state)
        step_history = list(next_state.get("step_history", []))

        try:
            try:
                payload = parse_planner_json(text)
            except PlannerOutputError:
                payload = safe_json_parse(text)
                if not isinstance(payload, dict):
                    payload = {"final": True, "response": "Failed to parse planner output."}

            next_state["step"] = int(next_state.get("step", 0)) + 1
            mode_raw = payload.get("mode")
            mode = mode_raw if mode_raw in ("fast", "reasoning") else "reasoning"
            next_state["mode"] = mode

            # Backward safety: accept old single-action format.
            actions_raw = payload.get("actions")
            if actions_raw is None and isinstance(payload.get("action"), dict):
                old_action = payload["action"]
                tool = old_action.get("tool")
                args = old_action.get("args", {})
                if isinstance(tool, str) and isinstance(args, dict):
                    actions_raw = [
                        {"tool": tool, "args": args, "output_key": "tool_output"}
                    ]

            # Direct final response (no actions).
            if payload.get("final") is True and not isinstance(actions_raw, list):
                response = payload.get("response")
                if not isinstance(response, str):
                    raise PlannerOutputError("Planner final response must be a string.")

                planner_step = {
                    "type": "planner",
                    "step_description": "Final response",
                    "actions": [],
                    "final": True,
                    # Compatibility fields for existing UI:
                    "planner_json": payload,
                    "planner_raw": text,
                }
                step_history.append(planner_step)

                next_state["final"] = True
                next_state["response"] = response
                next_state["step_history"] = step_history
                return next_state

            # Action plan branch:
            # - reasoning mode usually uses final=false and loops.
            # - fast mode can use final=true with actions, then execute once and stop.
            if payload.get("final") is False or (
                mode == "fast" and payload.get("final") is True and isinstance(actions_raw, list)
            ):
                if not isinstance(actions_raw, list):
                    raise PlannerOutputError('Planner output must include "actions" as a list.')

                step_description = payload.get("step_description")
                if not isinstance(step_description, str) or not step_description.strip():
                    step_description = "Executing planned actions"

                normalized_actions = []
                for a in actions_raw:
                    if not isinstance(a, dict):
                        continue
                    tool = a.get("tool")
                    args = a.get("args", {})
                    output_key = a.get("output_key")
                    if not isinstance(tool, str):
                        continue
                    if tool not in TOOL_REGISTRY:
                        continue
                    if not isinstance(args, dict):
                        args = {}
                    if not isinstance(output_key, str) or not output_key.strip():
                        output_key = "tool_output"

                    normalized_actions.append(
                        {
                            "tool": tool,
                            "args": args,
                            "output_key": output_key,
                        }
                    )

                if not normalized_actions:
                    raise PlannerOutputError("Planner did not provide any valid actions.")

                # Compatibility for existing UI expecting planner_json with `action`.
                first_action = normalized_actions[0]
                compat_planner_json = {
                    "final": False,
                    "action": {"tool": first_action["tool"], "args": first_action["args"]},
                }

                planner_step = {
                    "type": "planner",
                    "step_description": step_description,
                    "actions": normalized_actions,
                    "final": bool(payload.get("final") is True and mode == "fast"),
                    "mode": mode,
                    "planner_json": compat_planner_json,
                    "planner_raw": text,
                }
                step_history.append(planner_step)

                response = payload.get("response")
                next_state["final"] = False
                next_state["response"] = response if isinstance(response, str) else ""
                next_state["step_history"] = step_history
                return next_state

            raise PlannerOutputError('Planner JSON must include "final": true/false.')
        except PlannerOutputError as e:
            # Safety: if model outputs extra text or malformed JSON, treat it as final.
            step_history.append(
                {
                    "type": "planner",
                    "step_description": "Planner error",
                    "actions": [],
                    "final": True,
                    # Compatibility for UI:
                    "planner_error": str(e),
                    "planner_raw": text,
                }
            )
            next_state["step_history"] = step_history
            next_state["step"] = int(next_state.get("step", 0)) + 1
            next_state["final"] = True
            next_state["response"] = text.strip() or f"Planner error: {e}"
            return next_state

