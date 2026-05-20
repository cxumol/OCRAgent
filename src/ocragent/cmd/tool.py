from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterable, Mapping, cast

from ..config import get_user_toolbox_path
from ..logger import get_logger

USER_TOOLBOX_RUNTIME_CONTRACT = """
Generate a single Python file at ${HOME}/.ocragent/user_toolbox.py.

The file exposes three runtime objects:

- TOOL_SPECS describes each generated tool in the cmd/tool shape:
  name, scope, cost, desc, secrets, flags.
- TOOL_HANDLERS maps tool names to callables. Each callable receives argv: list[str].
- UNAVAILABLE_TOOLS maps intentionally disabled tool names to concrete reasons.

Handler return contract:

- str for text results
- bytes for binary results
- dict/list/scalar JSON values for json results
- or a tuple: (kind, value), where kind is text, json, or binary

Constraints:

- never print business output to stdout
- log only to stderr when needed
- never hardcode secrets
- read secrets from environment variables named in the tool metadata
- prefer httpx for HTTP
- prefer subprocess for local CLI calls
- parse CLI args inside each handler with argparse
""".strip()

SAMPLE_GENERATED_USER_TOOLBOX = """import argparse
import os

import httpx

TOOL_SPECS = [
    {
        "name": "example_tool",
        "scope": "parser",
        "cost": "medium",
        "desc": "OCR a local image through the example HTTP API.",
        "secrets": ["EXAMPLE_API_KEY"],
        "flags": {
            "path": "/path/to/image.png",
            "prompt-text": "OCR this image.",
        },
    },
]
UNAVAILABLE_TOOLS = {}


def tool_example_tool(argv: list[str]) -> str:
    parser = argparse.ArgumentParser(prog="ocragent tool example_tool", add_help=False)
    parser.add_argument("--path", required=True)
    parser.add_argument("--prompt-text", default="OCR this image.")
    args = parser.parse_args(argv)

    api_key = os.environ["EXAMPLE_API_KEY"]
    payload = {"path": args.path, "prompt": args.prompt_text}
    headers = {"authorization": f"Bearer {api_key}"}

    with httpx.Client(timeout=30.0) as client:
        response = client.post("https://example.invalid/ocr", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    return data["text"]


TOOL_HANDLERS = {
    "example_tool": tool_example_tool,
}
"""

SAMPLE_DYNAMIC_IMPORT = """import importlib

def resolve_entrypoint(entrypoint: str):
    module_name, separator, attr_name = entrypoint.partition(":")
    if not separator or not module_name or not attr_name:
        raise ValueError(f"invalid entrypoint: {entrypoint!r}")
    module = importlib.import_module(module_name)
    return getattr(module, attr_name)
"""

_RESULT_KINDS = {"text", "json", "binary"}
_TOOL_COST_LEVELS = ("very low", "low", "medium", "high", "very high")
_TOOL_SCOPES = ("previewer", "parser", "reviewer")
_BUILTIN_TOOL_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "img_metadata_px",
        "scope": "previewer",
        "cost": "very low",
        "desc": "Read image pixel dimensions.",
        "flags": {"path": "/path/to/file.png"},
    },
    {
        "name": "img_thumb",
        "scope": "previewer",
        "cost": "very low",
        "desc": "Render a small PNG thumbnail for an image.",
        "flags": {"path": "/path/to/file.png"},
    },
    {
        "name": "pdf_metadata",
        "scope": "previewer",
        "cost": "low",
        "desc": "Read basic PDF page and text-layer metadata.",
        "flags": {"path": "/path/to/file.pdf"},
    },
    {
        "name": "pdf2txt",
        "scope": "parser",
        "cost": "low",
        "desc": "Extract PDF text with PyMuPDF.",
        "flags": {"path": "/path/to/file.pdf"},
    },
    {
        "name": "pdf_pages_to_images",
        "scope": "parser",
        "cost": "medium",
        "desc": "Render each PDF page to a PNG image with PyMuPDF.",
        "flags": {"path": "/path/to/file.pdf", "out-dir": "/path/to/page-images"},
    },
    {
        "name": "pandoc2txt",
        "scope": "parser",
        "cost": "low",
        "desc": "Convert office documents to plain text with Pandoc.",
        "flags": {"path": "/path/to/file"},
    },
)
_BUILTIN_DEPENDENCIES = {
    "pdf_metadata": "pymupdf",
    "pdf2txt": "pymupdf",
    "pdf_pages_to_images": "pymupdf",
    "pandoc2txt": "pypandoc",
}


class ToolError(RuntimeError):
    pass


class ToolUsageError(ToolError):
    pass


class ToolUnavailableError(ToolError):
    pass


def _normalize_cost(value: str) -> str:
    text = value.strip().lower().replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    aliases = {
        "verylow": "very low",
        "vlow": "very low",
        "veryhigh": "very high",
        "vhigh": "very high",
    }
    text = aliases.get(text, text)
    if text in _TOOL_COST_LEVELS:
        return text
    raise ValueError(f"invalid cost {value!r}; expected one of: {', '.join(_TOOL_COST_LEVELS)}")


def _normalize_scope(value: str) -> str:
    text = value.strip().lower().replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    aliases = {
        "planner": "previewer",
        "planning": "previewer",
        "metadata": "previewer",
        "preview": "previewer",
        "review": "reviewer",
        "parser": "parser",
    }
    text = aliases.get(text, text)
    if text in _TOOL_SCOPES:
        return text
    raise ValueError(f"invalid scope {value!r}; expected one of: {', '.join(_TOOL_SCOPES)}")


@dataclass(slots=True)
class ToolSpec:
    name: str
    scope: str
    cost: str
    desc: str
    secrets: list[str] = field(default_factory=list)
    flags: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ToolSpec":
        name = str(data.get("name", "")).strip()
        if not name:
            raise ValueError("tool name must be a non-empty string")

        raw_scope = str(data.get("scope", "")).strip()
        if not raw_scope:
            raise ValueError(f"tool {name!r} is missing scope")
        scope = _normalize_scope(raw_scope)

        raw_cost = str(data.get("cost", "")).strip()
        if not raw_cost:
            raise ValueError(f"tool {name!r} is missing cost")
        cost = _normalize_cost(raw_cost)

        desc = str(data.get("desc") or "").strip()
        if not desc:
            raise ValueError(f"tool {name!r} is missing desc")

        return cls(
            name=name,
            scope=scope,
            cost=cost,
            desc=desc,
            secrets=_normalize_secrets(data.get("secrets") or []),
            flags=_normalize_flags(data.get("flags") or {}),
        )

    def usage(self) -> str:
        parts = [f"ocragent tool {self.name}"]
        for flag, value in self.flags.items():
            token = f"--{flag}"
            if value:
                token = f"{token} VALUE"
            parts.append(f"[{token}]")
        return " ".join(parts)

    def has_flag(self, name: str) -> bool:
        wanted = _normalize_flag_name(name)
        return any(_normalize_flag_name(flag) == wanted for flag in self.flags)

    def flag_token(self, name: str) -> str:
        wanted = _normalize_flag_name(name)
        for flag in self.flags:
            if _normalize_flag_name(flag) == wanted:
                return f"--{flag}"
        raise KeyError(name)

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "scope": self.scope,
            "cost": self.cost,
            "desc": self.desc,
            "secrets": list(self.secrets),
            "flags": dict(self.flags),
        }


def _normalize_secrets(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("secrets must be a list")
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize_flags(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("flags must be a mapping")
    flags: dict[str, str] = {}
    for key, example in value.items():
        name = str(key).strip().lstrip("-")
        if not name:
            raise ValueError("flag name must be non-empty")
        flags[name] = str(example).strip()
    return flags


def _normalize_flag_name(name: str) -> str:
    return name.strip().lstrip("-").replace("_", "-")


@dataclass(slots=True)
class ToolAvailability:
    available: bool
    reason: str = ""
    source: str = "runtime"


@dataclass(slots=True)
class DiscoveredTool:
    spec: ToolSpec
    availability: ToolAvailability
    source: str


@dataclass(slots=True)
class ToolInstance:
    name: str
    enabled: bool
    disable_reason: str
    cost: str
    scope: str
    desc: str
    secrets: list[str]
    flags: dict[str, str]

    @property
    def __name__(self) -> str:
        return self.name


@dataclass(slots=True)
class ToolExecutionResult:
    kind: str
    value: Any


def load_builtin_specs() -> list[ToolSpec]:
    return [ToolSpec.from_mapping(item) for item in _BUILTIN_TOOL_SPECS]


def load_user_specs(
    *,
    module: ModuleType | None = None,
    module_path: Path | None = None,
) -> tuple[list[ToolSpec], str | None]:
    owned_module = module
    if owned_module is None:
        owned_module, module_error = load_user_toolbox_module(module_path=module_path)
        if module_error:
            return [], module_error

    assert owned_module is not None
    raw_specs = getattr(owned_module, "TOOL_SPECS", None)
    if raw_specs is None:
        return [], "user toolbox does not expose TOOL_SPECS"
    if not isinstance(raw_specs, list) or not raw_specs:
        return [], "user toolbox TOOL_SPECS must be a non-empty list"

    specs: list[ToolSpec] = []
    for index, item in enumerate(raw_specs):
        if not isinstance(item, Mapping):
            return [], f"user toolbox TOOL_SPECS[{index}] must be a mapping"
        try:
            specs.append(ToolSpec.from_mapping(cast(Mapping[str, Any], item)))
        except ValueError as exc:
            return [], f"user toolbox TOOL_SPECS[{index}] is invalid: {exc}"
    return specs, None


def load_user_toolbox_module(*, module_path: Path | None = None) -> tuple[ModuleType | None, str | None]:
    path = module_path or get_user_toolbox_path()
    if not path.exists():
        return None, f"{path} not found"

    spec = importlib.util.spec_from_file_location("ocragent_user_toolbox", path)
    if spec is None or spec.loader is None:
        return None, f"failed to load module spec from {path}"

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover - import failures depend on generated user code
        return None, f"failed to import {path}: {exc!r}"
    return module, None


def discover_builtin_tools(*, logger=None) -> list[DiscoveredTool]:
    logger = logger or get_logger("cmd.tool")
    discovered: list[DiscoveredTool] = []
    for spec in load_builtin_specs():
        availability = _check_builtin_availability(spec)
        discovered.append(DiscoveredTool(spec=spec, availability=availability, source="builtin"))
        _log_unavailable(logger, spec, availability)
    return discovered


def discover_user_tools(*, cwd: Path | None = None, logger=None) -> list[DiscoveredTool]:
    return discover_user_tools_for_home(cwd=cwd, logger=logger)


def discover_user_tools_for_home(
    *,
    cwd: Path | None = None,
    home: Path | None = None,
    logger=None,
) -> list[DiscoveredTool]:
    logger = logger or get_logger("cmd.tool")
    module, module_error = load_user_toolbox_module(module_path=get_user_toolbox_path(home=home))
    if module_error:
        logger.debug("Skipping user tool discovery: %s", module_error)
        return []

    assert module is not None
    specs, specs_error = load_user_specs(module=module)
    if specs_error:
        logger.warning("Skipping user tool discovery: %s", specs_error)
        return []

    discovered: list[DiscoveredTool] = []
    for spec in specs:
        availability = _check_user_availability(spec, module=module, module_error=module_error)
        discovered.append(DiscoveredTool(spec=spec, availability=availability, source="user"))
        _log_unavailable(logger, spec, availability)
    return discovered


def list_tools(
    *,
    cwd: Path | None = None,
    home: Path | None = None,
    logger=None,
    scope: str | None = None,
) -> str:
    logger = logger or get_logger("cmd.tool")
    scope_filter = scope
    if scope_filter is not None:
        try:
            scope_filter = _normalize_scope(scope_filter)
        except ValueError:
            return f"Invalid --scope {scope_filter!r}. Expected: {', '.join(_TOOL_SCOPES)}\n"

    discovered = [
        *discover_builtin_tools(logger=logger),
        *discover_user_tools_for_home(cwd=cwd, home=home, logger=logger),
    ]
    tools = [_tool_instance(item) for item in discovered]
    if scope_filter is not None:
        tools = [tool for tool in tools if tool.scope == scope_filter]

    lines: list[str] = []
    for tool in tools:
        if not tool.enabled:
            continue
        header = f"{tool.name}\tscope: {tool.scope} cost: {tool.cost}\t{tool.desc}"
        if tool.flags:
            flag_lines = [
                f"\t--{key} {value}".rstrip()
                for key, value in tool.flags.items()
            ]
            lines.append(header + "\n" + "\n".join(flag_lines))
        else:
            lines.append(header)
    return "\n\n".join(lines)


def describe_tool(name: str, *, cwd: Path | None = None, logger=None) -> str:
    discovered = _find_tool(name, cwd=cwd, logger=logger)
    return _format_tool_help(discovered)


def run_tool(
    name: str,
    argv: list[str],
    *,
    cwd: Path | None = None,
    home: Path | None = None,
    logger=None,
) -> ToolExecutionResult:
    logger = logger or get_logger("cmd.tool")
    discovered = _find_tool(name, cwd=cwd, home=home, logger=logger)
    if _wants_help(argv):
        return ToolExecutionResult(kind="text", value=_format_tool_help(discovered))

    if not discovered.availability.available:
        raise ToolUnavailableError(
            f"{discovered.spec.name} is unavailable: {discovered.availability.reason or 'unknown reason'}"
        )

    if discovered.source == "builtin":
        handler = _builtin_handler(discovered.spec.name)
        raw_result = handler(argv)
    else:
        raw_result = _run_user_tool(discovered.spec, argv, home=home)
    return coerce_tool_result(raw_result, tool_name=name)


def coerce_tool_result(result: Any, *, tool_name: str = "") -> ToolExecutionResult:
    kind: str
    value: Any

    if (
        isinstance(result, tuple)
        and len(result) == 2
        and isinstance(result[0], str)
        and result[0] in _RESULT_KINDS
    ):
        kind = result[0]
        value = result[1]
    elif hasattr(result, "kind") and hasattr(result, "value"):
        kind = getattr(result, "kind")
        value = getattr(result, "value")
    elif isinstance(result, (bytes, bytearray, memoryview)):
        kind = "binary"
        value = bytes(result)
    elif isinstance(result, str):
        kind = "text"
        value = result
    elif isinstance(result, (dict, list, int, float, bool)) or result is None:
        kind = "json"
        value = result
    else:
        raise ToolUsageError(f"{tool_name or 'tool'} returned unsupported result type: {type(result).__name__}")

    return ToolExecutionResult(kind=kind, value=value)


def _find_tool(
    name: str,
    *,
    cwd: Path | None = None,
    home: Path | None = None,
    logger=None,
) -> DiscoveredTool:
    logger = logger or get_logger("cmd.tool")
    for discovered in [
        *discover_builtin_tools(logger=logger),
        *discover_user_tools_for_home(cwd=cwd, home=home, logger=logger),
    ]:
        if discovered.spec.name == name:
            return discovered
    raise ToolUsageError(f"unknown tool: {name}")


def _tool_instance(discovered: DiscoveredTool) -> ToolInstance:
    spec = discovered.spec
    return ToolInstance(
        name=spec.name,
        enabled=discovered.availability.available,
        disable_reason=discovered.availability.reason or "",
        cost=spec.cost,
        scope=spec.scope,
        desc=spec.desc,
        secrets=list(spec.secrets),
        flags=dict(spec.flags),
    )


def _format_tool_help(discovered: DiscoveredTool) -> str:
    spec = discovered.spec
    availability = "yes" if discovered.availability.available else "no"
    lines = [
        f"ToolName: {spec.name}",
        f"Usage: {spec.usage()}",
        f"Scope: {spec.scope or '-'}",
        f"Cost: {spec.cost or '-'}",
        f"Desc: {spec.desc or '-'}",
        f"Available: {availability}",
    ]
    if discovered.availability.reason:
        lines.append(f"UnavailableReason: {discovered.availability.reason}")
    if spec.flags:
        lines.append("Flags:")
        for flag, value in spec.flags.items():
            lines.append(f"  --{flag} {value}".rstrip())
    if spec.secrets:
        lines.append(f"Secrets: {', '.join(spec.secrets)}")
    return "\n".join(lines) + "\n"


def _wants_help(argv: Iterable[str]) -> bool:
    return any(arg in {"-h", "--help"} for arg in argv)


def _log_unavailable(logger, spec: ToolSpec, availability: ToolAvailability) -> None:
    if availability.available or not availability.reason:
        return
    logger.warning(
        "Tool %s is unavailable (%s): %s",
        spec.name,
        availability.source,
        availability.reason,
    )


def _missing_secrets(spec: ToolSpec) -> list[str]:
    return [name for name in spec.secrets if not os.getenv(name)]


def _check_builtin_availability(spec: ToolSpec) -> ToolAvailability:
    missing = _missing_secrets(spec)
    if missing:
        return ToolAvailability(False, f"missing required env vars: {', '.join(missing)}", "program_rule")

    module_name = _BUILTIN_DEPENDENCIES.get(spec.name)
    if module_name:
        if importlib.util.find_spec(module_name) is None:
            return ToolAvailability(
                False,
                f"python module {module_name!r} is not importable",
                "runtime",
            )
    return ToolAvailability(True)


def _check_user_availability(
    spec: ToolSpec,
    *,
    module: ModuleType | None,
    module_error: str | None,
) -> ToolAvailability:
    missing = _missing_secrets(spec)
    if missing:
        return ToolAvailability(False, f"missing required env vars: {', '.join(missing)}", "program_rule")

    if module_error:
        return ToolAvailability(False, module_error, "runtime")

    assert module is not None
    unavailable = getattr(module, "UNAVAILABLE_TOOLS", {})
    if isinstance(unavailable, Mapping):
        reason = unavailable.get(spec.name)
        if isinstance(reason, str) and reason.strip():
            return ToolAvailability(False, reason.strip(), "llm")

    handler = _resolve_user_handler(module, spec.name)
    if handler is None:
        return ToolAvailability(
            False,
            f"user toolbox does not expose a handler for {spec.name}",
            "runtime",
        )
    return ToolAvailability(True)


def _builtin_handler(name: str) -> Callable[[list[str]], Any]:
    handlers: dict[str, Callable[[list[str]], Any]] = {
        "img_metadata_px": img_metadata_px,
        "img_thumb": img_thumb,
        "pdf_metadata": pdf_metadata,
        "pdf2txt": pdf2txt,
        "pdf_pages_to_images": pdf_pages_to_images,
        "pandoc2txt": pandoc2txt,
    }
    try:
        return handlers[name]
    except KeyError as exc:  # pragma: no cover - metadata/handler drift
        raise ToolUsageError(f"builtin tool handler missing for {name}") from exc


def _run_user_tool(spec: ToolSpec, argv: list[str], *, home: Path | None = None) -> Any:
    module, module_error = load_user_toolbox_module(module_path=get_user_toolbox_path(home=home))
    if module_error:
        raise ToolUnavailableError(module_error)
    assert module is not None
    handler = _resolve_user_handler(module, spec.name)
    if handler is None:
        raise ToolUnavailableError(f"user toolbox handler missing for {spec.name}")
    return handler(argv)


def _resolve_user_handler(module: ModuleType, tool_name: str) -> Callable[[list[str]], Any] | None:
    handlers = getattr(module, "TOOL_HANDLERS", None)
    if isinstance(handlers, Mapping):
        handler = handlers.get(tool_name)
        if callable(handler):
            return handler
    return None


def _read_image_size(path: Path) -> tuple[int, int]:
    from PIL import Image

    with Image.open(path) as image:
        return image.width, image.height


def img_metadata_px(argv: list[str]) -> dict[str, int]:
    parser = argparse.ArgumentParser(prog="ocragent tool img_metadata_px", add_help=False)
    parser.add_argument("--path", required=True)
    args = parser.parse_args(argv)
    path = Path(args.path).expanduser().resolve()
    width, height = _read_image_size(path)
    return {"width": width, "height": height}


def img_thumb(argv: list[str]) -> bytes:
    parser = argparse.ArgumentParser(prog="ocragent tool img_thumb", add_help=False)
    parser.add_argument("--path", required=True)
    args = parser.parse_args(argv)
    path = Path(args.path).expanduser().resolve()

    from PIL import Image

    with Image.open(path) as image:
        thumb = image.copy()
        thumb.thumbnail((360, 360))
        buffer = io.BytesIO()
        thumb.save(buffer, format="PNG")
        return buffer.getvalue()


def pdf_metadata(argv: list[str]) -> dict[str, Any]:
    parser = argparse.ArgumentParser(prog="ocragent tool pdf_metadata", add_help=False)
    parser.add_argument("--path", required=True)
    args = parser.parse_args(argv)
    path = Path(args.path).expanduser().resolve()

    import pymupdf

    with pymupdf.open(path) as document:
        return {
            "page_count": document.page_count,
            "word_count": sum(len(page.get_text("words")) for page in document),
            "toc": document.get_toc(),
        }


def pdf2txt(argv: list[str]) -> str:
    parser = argparse.ArgumentParser(prog="ocragent tool pdf2txt", add_help=False)
    parser.add_argument("--path", required=True)
    args = parser.parse_args(argv)
    path = Path(args.path).expanduser().resolve()

    import pymupdf

    with pymupdf.open(path) as document:
        return chr(12).join(page.get_text() for page in document)


def pdf_pages_to_images(argv: list[str]) -> dict[str, Any]:
    parser = argparse.ArgumentParser(prog="ocragent tool pdf_pages_to_images", add_help=False)
    parser.add_argument("--path", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--zoom", type=float, default=2.0)
    args = parser.parse_args(argv)
    path = Path(args.path).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()

    import pymupdf

    out_dir.mkdir(parents=True, exist_ok=True)
    pages: list[dict[str, Any]] = []
    with pymupdf.open(path) as document:
        matrix = pymupdf.Matrix(args.zoom, args.zoom)
        for index, page in enumerate(document, start=1):
            image_path = out_dir / f"page-{index:04d}.png"
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            pixmap.save(image_path)
            pages.append({"page": index, "image_file": str(image_path)})
    return {"source_file": str(path), "pages": pages}


def pandoc2txt(argv: list[str]) -> str:
    parser = argparse.ArgumentParser(prog="ocragent tool pandoc2txt", add_help=False)
    parser.add_argument("--path", required=True)
    args = parser.parse_args(argv)
    path = Path(args.path).expanduser().resolve()

    import pypandoc

    return pypandoc.convert_file(str(path), to="plain")

def prompt_builtin_contract_json() -> str:
    return json.dumps([spec.to_prompt_dict() for spec in load_builtin_specs()], ensure_ascii=False, indent=2)
