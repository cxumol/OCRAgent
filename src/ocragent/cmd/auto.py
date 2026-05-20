from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..config import (
    OCRAGENT_CHAT_ENV_REMINDER,
    get_user_toolbox_path,
    load_ocra_config,
)
from ..logger import configure_logging, get_logger
from .init_docs import run_init_docs
from .init_tools import run_init_tools
from .run import run
from .tool import load_user_specs, load_user_toolbox_module


@dataclass(slots=True)
class AutoOptions:
    paths: list[Path]
    out_dir: Path
    force: bool
    yes: bool
    dry_run: bool


@dataclass(slots=True)
class _Stage:
    name: str
    action: str
    reason: str = ""

    def line(self) -> str:
        if self.reason:
            return f"{self.name}: {self.action}, {self.reason}"
        return f"{self.name}: {self.action}"


def run_auto(
    *,
    paths: list[Path] | None = None,
    out_dir: Path | None = None,
    force: bool = False,
    yes: bool = False,
    dry_run: bool = False,
    cwd: Path | None = None,
    home: Path | None = None,
    logger=None,
) -> dict[str, Any]:
    cwd = cwd or Path.cwd()
    home = home or Path.home()
    logger = logger or get_logger("cmd.auto")
    out_dir = out_dir or Path("ocragent_results")

    toolbox_path = get_user_toolbox_path(home=home)
    memory_path = cwd / ".ocragent_memory.txt"
    toolbox_txt = home / "ocragent.toolbox_user.txt"
    has_chat = _has_chat_config(cwd=cwd, home=home)

    stages = _plan(
        toolbox_path=toolbox_path,
        memory_path=memory_path,
        toolbox_txt=toolbox_txt,
        has_chat=has_chat,
        force=force,
        out_dir=out_dir,
    )
    for stage in stages:
        logger.info(stage.line())

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "plan": [stage.line() for stage in stages],
            "stages_run": [],
            "out_dir": str(_resolve_path(out_dir, cwd)),
            "parsed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "failures": [],
            "skipped": [],
            "log_file": str(cwd / "ocragent.log"),
            "memory_file": str(memory_path),
            "toolbox_file": str(toolbox_path),
        }

    stages_run: list[str] = []
    generated_toolbox = False

    should_init_tools = force and toolbox_txt.exists()
    if should_init_tools or not toolbox_path.exists():
        if toolbox_txt.exists():
            if not has_chat:
                raise RuntimeError(f"{OCRAGENT_CHAT_ENV_REMINDER} Next: configure chat settings, then run `ocragent`.")
            logger.info("stage: init tools")
            run_init_tools(overwrite=force or not toolbox_path.exists(), source_path=toolbox_txt, cwd=cwd, home=home, logger=logger)
            stages_run.append("init tools")
            generated_toolbox = True
        else:
            logger.warning("No toolbox TXT found; using builtin-only mode.")
            _write_builtin_only_runtime(toolbox_path)
            stages_run.append("init tools")

    if generated_toolbox and _generated_toolbox_requires_review(toolbox_path):
        _require_generated_toolbox_review(toolbox_path, yes=yes)

    if force or not memory_path.exists():
        if not has_chat:
            raise RuntimeError(f"{OCRAGENT_CHAT_ENV_REMINDER} Next: configure chat settings, then run `ocragent init docs`.")
        logger.info("stage: init docs")
        run_init_docs(overwrite=force or not memory_path.exists(), cwd=cwd, home=home, logger=logger)
        stages_run.append("init docs")

    logger.info("stage: run")
    run_summary = run(paths=paths, out_dir=out_dir, cwd=cwd, home=home, logger=logger)
    stages_run.append("run")

    return _summary(
        run_summary,
        stages_run=stages_run,
        cwd=cwd,
        memory_path=memory_path,
        toolbox_path=toolbox_path,
    )


def parse_auto_args(argv: Sequence[str]) -> AutoOptions:
    parser = argparse.ArgumentParser(
        prog="ocragent",
        description="Run OCRAgent Autonomous Mode.",
    )
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("ocragent_results"))
    parser.add_argument("--force", "-f", action="store_true")
    parser.add_argument("--yes", "-y", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(list(argv))
    return AutoOptions(
        paths=list(args.paths),
        out_dir=args.out_dir,
        force=bool(args.force),
        yes=bool(args.yes),
        dry_run=bool(args.dry_run),
    )


def main(argv: Sequence[str] | None = None) -> int:
    options = parse_auto_args(sys.argv[1:] if argv is None else argv)
    configure_logging()
    logger = get_logger("cmd.auto")
    try:
        summary = run_auto(
            paths=options.paths or None,
            out_dir=options.out_dir,
            force=options.force,
            yes=options.yes,
            dry_run=options.dry_run,
            logger=logger,
        )
    except Exception as exc:
        logger.error(str(exc))
        return 1

    if options.dry_run:
        for line in summary.get("plan") or []:
            sys.stdout.write(f"{line}\n")
    else:
        sys.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))
        sys.stdout.write("\n")
    sys.stdout.flush()
    return 0 if summary.get("ok") else 1


def _plan(
    *,
    toolbox_path: Path,
    memory_path: Path,
    toolbox_txt: Path,
    has_chat: bool,
    force: bool,
    out_dir: Path,
) -> list[_Stage]:
    stages = [_Stage("prepare", "ok")]
    if force:
        if toolbox_txt.exists() and has_chat:
            stages.append(_Stage("init tools", "run", "--force requested"))
        elif not toolbox_path.exists():
            stages.append(_Stage("init tools", "run", "builtin-only runtime"))
        else:
            stages.append(_Stage("init tools", "skip", "no toolbox TXT for regeneration"))
        stages.append(_Stage("init docs", "run", "--force requested"))
    else:
        if toolbox_path.exists():
            stages.append(_Stage("init tools", "skip", "user_toolbox.py exists"))
        elif toolbox_txt.exists():
            action = "run" if has_chat else "blocked"
            stages.append(_Stage("init tools", action, "toolbox TXT exists"))
        else:
            stages.append(_Stage("init tools", "run", "builtin-only runtime"))

        if memory_path.exists():
            stages.append(_Stage("init docs", "skip", ".ocragent_memory.txt exists"))
        else:
            action = "run" if has_chat else "blocked"
            stages.append(_Stage("init docs", action, ".ocragent_memory.txt missing"))
    stages.append(_Stage("run", "run", f"out-dir {out_dir}"))
    return stages


def _has_chat_config(*, cwd: Path, home: Path) -> bool:
    try:
        cfg = load_ocra_config(cwd=cwd, home=home)
    except Exception:
        return False
    aigc = cfg.get("aigc")
    api = aigc.get("api") if isinstance(aigc, Mapping) else {}
    chat = api.get("chatcomp") if isinstance(api, Mapping) else {}
    if not isinstance(chat, Mapping):
        return False
    return bool(str(chat.get("base") or "").strip() and str(chat.get("model") or "").strip())


def _write_builtin_only_runtime(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "TOOL_SPECS = []",
                "UNAVAILABLE_TOOLS = {}",
                "TOOL_HANDLERS = {}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _generated_toolbox_requires_review(path: Path) -> bool:
    module, module_error = load_user_toolbox_module(module_path=path)
    if module_error or module is None:
        return True
    specs, specs_error = load_user_specs(module=module)
    if specs_error:
        return True
    return bool(specs)


def _require_generated_toolbox_review(path: Path, *, yes: bool) -> None:
    if yes:
        return
    if not sys.stdin.isatty():
        raise RuntimeError(f"Review {path} before continuing, then rerun `ocragent --yes`.")
    sys.stderr.write(f"Review {path} before running generated tools. Continue? [y/N] ")
    sys.stderr.flush()
    answer = sys.stdin.readline().strip().lower()
    if answer not in {"y", "yes"}:
        raise RuntimeError(f"Stopped before using generated toolbox: {path}")


def _summary(
    run_summary: dict[str, Any],
    *,
    stages_run: list[str],
    cwd: Path,
    memory_path: Path,
    toolbox_path: Path,
) -> dict[str, Any]:
    return {
        "ok": bool(run_summary.get("ok")),
        "stages_run": stages_run,
        "out_dir": str(run_summary.get("out_dir") or ""),
        "parsed_count": int(run_summary.get("parsed_count") or 0),
        "failed_count": int(run_summary.get("failed_count") or 0),
        "skipped_count": int(run_summary.get("skipped_count") or 0),
        "results": list(run_summary.get("results") or []),
        "failures": list(run_summary.get("failures") or []),
        "skipped": list(run_summary.get("skipped") or []),
        "log_file": str(cwd / "ocragent.log"),
        "memory_file": str(memory_path),
        "toolbox_file": str(toolbox_path),
    }


def _resolve_path(path: Path, cwd: Path) -> Path:
    return path if path.is_absolute() else cwd / path
