from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_configured = False


def setup_logging(
    log_path: Path | None = None,
    debug: bool = False,
    tui_handler: logging.Handler | None = None,
) -> None:
    global _configured

    path = log_path or Path(os.environ.get("DBTOOL_LOG", "/tmp/db-tool.log"))
    root = logging.getLogger("db_tool")

    if not _configured:
        _configured = True
        root.setLevel(logging.DEBUG if debug else logging.INFO)

        fh = logging.FileHandler(path, mode="a", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s — %(message)s"))
        root.addHandler(fh)

        if debug:
            sh = logging.StreamHandler(sys.stderr)
            sh.setLevel(logging.DEBUG)
            sh.setFormatter(logging.Formatter("%(levelname)-8s %(name)s — %(message)s"))
            root.addHandler(sh)

        logging.getLogger("textual").setLevel(logging.WARNING)
        logging.getLogger("pymongo").setLevel(logging.WARNING)

    if tui_handler:
        tui_handler.setLevel(logging.INFO if not debug else logging.DEBUG)
        root.addHandler(tui_handler)


def get_log_path() -> Path:
    return Path(os.environ.get("DBTOOL_LOG", "/tmp/db-tool.log"))