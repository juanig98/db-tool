import logging


class TestLogBuffer:
    def test_log_buffer_add(self) -> None:
        """log_buffer debe guardar logs."""
        from db_tool.tui.log_buffer import add_log, get_all_logs, clear_logs

        clear_logs()
        add_log(logging.INFO, "test.logger", "test message")

        logs = get_all_logs()
        assert len(logs) == 1
        assert logs[0] == (logging.INFO, "test.logger", "test message")

    def test_log_buffer_clear(self) -> None:
        """log_buffer debe limpiar logs."""
        from db_tool.tui.log_buffer import add_log, get_all_logs, clear_logs

        clear_logs()
        add_log(logging.INFO, "test", "msg")
        clear_logs()

        assert len(get_all_logs()) == 0