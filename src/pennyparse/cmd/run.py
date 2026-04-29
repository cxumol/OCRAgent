from __future__ import annotations

from pathlib import Path
from typing import Any

from ..agent.parser import run_parser
from ..logger import get_logger


def run(
    *,
    paths: list[Path] | None = None,
    out_dir: Path | None = None,
    cwd: Path | None = None,
    home: Path | None = None,
    logger=None,
) -> dict[str, Any]:
    return run_parser(
        paths=paths,
        out_dir=out_dir,
        cwd=cwd,
        home=home,
        logger=logger or get_logger("cmd.run"),
    )
