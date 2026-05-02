from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from db_tool.tui.log_handler import LogEntryReceived, TextualLogHandler


class TestTextualLogHandler:
    def test_emit_posts_message(self) -> None:
        """emit debe enviar LogEntryReceived al app."""
        mock_app = MagicMock()
        handler = TextualLogHandler(mock_app)

        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )

        handler.emit(record)

        mock_app.post_message.assert_called_once()
        call_args = mock_app.post_message.call_args[0][0]
        assert isinstance(call_args, LogEntryReceived)
        assert call_args.logger_name == "test.logger"
        assert call_args.level == logging.INFO

    def test_emit_formats_message(self) -> None:
        """emit debe formatear el mensaje correctamente."""
        mock_app = MagicMock()
        handler = TextualLogHandler(mock_app)

        record = logging.LogRecord(
            name="db_tool.test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="warning: %s",
            args=("something",),
            exc_info=None,
        )

        handler.emit(record)

        call_args = mock_app.post_message.call_args[0][0]
        assert "WARNING" in call_args.formatted
        assert "db_tool.test" in call_args.formatted

    def test_handler_has_formatter(self) -> None:
        """Handler debe tener un formatter configurado."""
        mock_app = MagicMock()
        handler = TextualLogHandler(mock_app)

        assert handler.formatter is not None

    def test_emit_handles_exception(self) -> None:
        """emit debe manejar excepciones sin romper."""
        mock_app = MagicMock()
        mock_app.post_message.side_effect = Exception("test error")

        handler = TextualLogHandler(mock_app)

        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test",
            args=(),
            exc_info=None,
        )

        handler.emit(record)
        mock_app.post_message.assert_called_once()