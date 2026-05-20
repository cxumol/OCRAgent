from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from ._client import ChatSession
from .config import ocra_config
from .logger import get_logger
from .utils import extract_md_codeblock

logger = get_logger("utils_aigc")

ToolHandler = Callable[[dict[str, Any]], Any]


def _extract_json_candidate(text: str) -> str:
    code = extract_md_codeblock(text)
    if code:
        return code

    obj_start = text.find("{")
    obj_end = text.rfind("}")
    if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
        return text[obj_start : obj_end + 1]

    arr_start = text.find("[")
    arr_end = text.rfind("]")
    if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
        return text[arr_start : arr_end + 1]

    return text


def ai_chat_to_json_obj(client: Any, session: ChatSession) -> Any:
    retry_limit = int(ocra_config["aigc"]["agent"]["max_retry"])
    last_text = ""
    for attempt in range(1, retry_limit + 1):
        message = complete_with_retry(client, session, max_retry=retry_limit)
        last_text = str(message.get("content") or "").strip()
        if not last_text:
            continue

        candidate = _extract_json_candidate(last_text)
        try:
            return json.loads(candidate)
        except Exception as exc:
            logger.warning("ai_chat_to_json_obj attempt %s/%s failed: %s", attempt, retry_limit, exc)
            continue

    raise RuntimeError(f"failed to parse JSON from AI response after {retry_limit} attempts: {last_text!r}")


def complete_with_retry(
    client: Any,
    session: ChatSession,
    *,
    max_retry: int | None = None,
    retry_backoff: float = 0.25,
    **kwargs: Any,
) -> dict[str, Any]:
    retry_limit = max(1, int(max_retry or ocra_config["aigc"]["agent"]["max_retry"]))
    last_exc: Exception | None = None
    for attempt in range(1, retry_limit + 1):
        try:
            return client.complete(session, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt >= retry_limit:
                break
            logger.warning("chat completion attempt %s/%s failed: %s", attempt, retry_limit, exc)
            if retry_backoff > 0:
                time.sleep(retry_backoff * (2 ** (attempt - 1)))
    assert last_exc is not None
    raise last_exc


def run_tool_calls_loop(
    client: Any,
    session: ChatSession,
    *,
    tools: Sequence[Mapping[str, Any]],
    tool_handlers: Mapping[str, ToolHandler],
    max_iter: int | None = None,
    max_retry: int | None = None,
    **completion_options: Any,
) -> dict[str, Any]:
    iter_limit = max(1, int(max_iter or ocra_config["aigc"]["agent"]["max_iter"]))
    retry_limit = max(1, int(max_retry or ocra_config["aigc"]["agent"]["max_retry"]))

    for _ in range(iter_limit):
        assistant = complete_with_retry(
            client,
            session,
            max_retry=retry_limit,
            tools=tools,
            **completion_options,
        )
        _ensure_assistant_recorded(session, assistant)
        tool_calls = assistant.get("tool_calls") or []
        if not tool_calls:
            return assistant

        for index, call in enumerate(tool_calls):
            name, arguments = _parse_tool_call(call)
            call_id = str(call.get("id") or f"call_{index}")
            session.tool(
                _tool_result_json(_execute_tool(name, arguments, tool_handlers)),
                tool_call_id=call_id,
                name=name or None,
            )

    raise RuntimeError(f"agent loop reached max_iter={iter_limit}")


def _ensure_assistant_recorded(session: ChatSession, assistant: Mapping[str, Any]) -> None:
    if not session.messages or session.messages[-1] != assistant:
        session.messages.append(dict(assistant))


def _parse_tool_call(call: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    function = call.get("function")
    if not isinstance(function, Mapping):
        return "", {}

    name = str(function.get("name") or "").strip()
    raw_arguments = function.get("arguments") or "{}"
    if isinstance(raw_arguments, Mapping):
        return name, dict(raw_arguments)
    try:
        arguments = json.loads(str(raw_arguments))
    except Exception as exc:
        return name, {"__tool_call_error__": f"invalid JSON arguments: {exc}"}
    if not isinstance(arguments, dict):
        return name, {"__tool_call_error__": "tool arguments must be a JSON object"}
    return name, arguments


def _execute_tool(
    name: str,
    arguments: dict[str, Any],
    tool_handlers: Mapping[str, ToolHandler],
) -> dict[str, Any]:
    if arguments.get("__tool_call_error__"):
        return {"ok": False, "error": str(arguments["__tool_call_error__"])}
    handler = tool_handlers.get(name)
    if handler is None:
        return {"ok": False, "error": f"unknown tool: {name}"}
    try:
        return {"ok": True, "result": handler(arguments)}
    except Exception as exc:
        return {
            "ok": False,
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
            },
        }


def _tool_result_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)
