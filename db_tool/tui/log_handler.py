from __future__ import annotations

import logging
from textual.message import Message


class LogEntryReceived(Message):
    def __init__(self, level: int, logger_name: str, formatted: str) -> None:
        super().__init__()
        self.level = level
        self.logger_name = logger_name
        self.formatted = formatted


class TextualLogHandler(logging.Handler):
    def __init__(self, app) -> None:
        super().__init__()
        self._app = app
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s — %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            from db_tool.tui.log_buffer import add_log
            add_log(record.levelno, record.name, msg)
            self._app.post_message(LogEntryReceived(record.levelno, record.name, msg))
        except Exception:
            self.handleError(record)