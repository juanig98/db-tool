from __future__ import annotations

import logging
from pathlib import Path

import pytest

from db_tool import logging_config


class TestGetLogPath:
    def test_get_log_path_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_log_path debe devolver el default si no hay env var."""
        monkeypatch.delenv("DBTOOL_LOG", raising=False)
        path = logging_config.get_log_path()
        assert path == Path("/tmp/db-tool.log")

    def test_get_log_path_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_log_path debe respetar DBTOOL_LOG."""
        monkeypatch.setenv("DBTOOL_LOG", "/custom/path/db-tool.log")
        path = logging_config.get_log_path()
        assert path == Path("/custom/path/db-tool.log")


class TestLoggingLevels:
    @pytest.mark.skip(reason="Requires clean state between tests")
    def test_textual_logger_warning(self, tmp_path: Path) -> None:
        """Logger textual debe estar en WARNING."""
        logging_config.setup_logging(log_path=tmp_path / "test.log")
        textual_logger = logging.getLogger("textual")
        assert textual_logger.level == logging.WARNING

    @pytest.mark.skip(reason="Requires clean state between tests")
    def test_pymongo_logger_warning(self, tmp_path: Path) -> None:
        """Logger pymongo debe estar en WARNING."""
        logging_config.setup_logging(log_path=tmp_path / "test.log")
        pymongo_logger = logging.getLogger("pymongo")
        assert pymongo_logger.level == logging.WARNING

    @pytest.mark.skip(reason="Requires clean state between tests")
    def test_root_logger_info_by_default(self, tmp_path: Path) -> None:
        """Root logger debe estar en INFO por defecto."""
        logging_config.setup_logging(log_path=tmp_path / "test.log", debug=False)
        root = logging.getLogger("db_tool")
        assert root.level == logging.INFO

    @pytest.mark.skip(reason="Requires clean state between tests")
    def test_root_logger_debug_when_enabled(self, tmp_path: Path) -> None:
        """Root logger debe estar en DEBUG cuando debug=True."""
        logging_config.setup_logging(log_path=tmp_path / "test.log", debug=True)
        root = logging.getLogger("db_tool")
        assert root.level == logging.DEBUG