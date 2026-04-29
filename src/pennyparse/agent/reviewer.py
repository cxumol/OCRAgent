from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Literal

from .._client import ChatClient, ChatSession
from ..config import load_pp_config
from ..logger import get_logger
from ..utils import extract_md_codeblock

ReviewStatus = Literal["pass", "minor_revision", "major_revision"]
_AGENT_IMPL_MODE = "tool_calls"


@dataclass(slots=True)
class ReviewOutcome:
    status: ReviewStatus
    text: str
    message: str

    @property
    def ok(self) -> bool:
        return self.status in {"pass", "minor_revision"}

    def as_dict(self) -> dict[str, str]:
        return {
            "status": self.status,
            "text": self.text,
            "message": self.message,
        }


def review_text(
    text: str,
    *,
    source_path: Path | None = None,
    cwd: Path | None = None,
    home: Path | None = None,
    logger=None,
) -> ReviewOutcome:
    logger = logger or get_logger("agent.reviewer")
    pp_cfg = load_pp_config(cwd=cwd, home=home)
    max_length = _review_max_length(pp_cfg)
    candidate = text[:max_length]

    if not candidate.strip():
        return ReviewOutcome(
            status="major_revision",
            text=text,
            message="The reviewer found current given result need a major revision.",
        )

    chat_settings = _chat_settings(pp_cfg)
    if not chat_settings.get("model"):
        return ReviewOutcome(
            status="pass",
            text=text,
            message="The reviewer found current given result is good.",
        )

    try:
        return _review_with_llm(
            candidate,
            original=text,
            source_path=source_path,
            chat_settings=chat_settings,
        )
    except Exception as exc:
        logger.info("LLM review skipped: %s", exc)
        return ReviewOutcome(
            status="pass",
            text=text,
            message="The reviewer found current given result is good.",
        )


def _review_max_length(pp_cfg: Mapping[str, Any]) -> int:
    output = _as_mapping(pp_cfg.get("output"))
    reviewer = _as_mapping(pp_cfg.get("reviewer"))
    value = output.get("max_length", reviewer.get("max_length"))
    if value is None:
        raise RuntimeError("output.max_length must be configured")
    return max(1, int(value))


def _chat_settings(pp_cfg: Mapping[str, Any]) -> dict[str, Any]:
    chat = _as_mapping(_as_mapping(_as_mapping(pp_cfg.get("aigc")).get("api")).get("chatcomp"))
    return {
        "base_url": str(chat.get("base") or "").strip(),
        "api_key": str(chat.get("authkey") or "").strip() or None,
        "model": str(chat.get("model") or "").strip() or None,
    }


def _review_with_llm(
    candidate: str,
    *,
    original: str,
    source_path: Path | None,
    chat_settings: Mapping[str, Any],
) -> ReviewOutcome:
    session = ChatSession()
    session.system(
        "Review one parsed document fragment. Return JSON only with keys "
        "status, message, and text. status MUST be one of pass, minor_revision, "
        "major_revision. Use minor_revision only when the supplied text can be "
        "fixed directly in the text field. Use major_revision for empty, broken, "
        "or obviously incomplete extraction."
    )
    session.user(
        json.dumps(
            {
                "source_path": str(source_path) if source_path else "",
                "text": candidate,
            },
            ensure_ascii=False,
        )
    )

    with ChatClient(**dict(chat_settings), timeout=30.0) as client:
        assistant = client.complete(session, temperature=0)

    content = assistant.get("content")
    payload = extract_md_codeblock(content) if isinstance(content, str) else ""
    if not payload and isinstance(content, str):
        payload = content
    data = json.loads(payload)
    status = data.get("status")
    if status not in {"pass", "minor_revision", "major_revision"}:
        raise RuntimeError(f"invalid reviewer status: {status!r}")
    revised = str(data.get("text") or "")
    message = str(data.get("message") or "").strip()

    if status == "minor_revision" and revised.strip():
        return ReviewOutcome(status="minor_revision", text=revised, message=message)
    if status == "major_revision":
        return ReviewOutcome(
            status="major_revision",
            text=original,
            message=message or "The reviewer found current given result need a major revision.",
        )
    return ReviewOutcome(
        status="pass",
        text=original,
        message=message or "The reviewer found current given result is good.",
    )


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
