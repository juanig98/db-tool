from __future__ import annotations

from collections import deque

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, RichLog, Select

_MAX_ENTRIES = 1000


class LogsScreen(Screen[None]):
    BINDINGS = [("escape", "dismiss", "Volver")]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._buffer: deque[tuple[int, str, str]] = deque(maxlen=_MAX_ENTRIES)

    def on_mount(self) -> None:
        from db_tool.tui.log_buffer import get_all_logs
        for level, logger_name, formatted in get_all_logs():
            self._buffer.append((level, logger_name, formatted))
            if self._passes_filter(level, logger_name):
                self._append_to_view(level, formatted)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Select(
            [("ALL", 0), ("DEBUG", 10), ("INFO", 20), ("WARNING", 30), ("ERROR", 40)],
            id="level_filter",
            value=0,
        )
        yield Input(placeholder="Filtrar por módulo...", id="module_filter")
        yield Button("Limpiar", id="clear")
        yield RichLog(id="log_view", highlight=True, markup=True)
        yield Footer()

    def add_entry(self, level: int, logger_name: str, formatted: str) -> None:
        self._buffer.append((level, logger_name, formatted))
        if self._passes_filter(level, logger_name):
            self._append_to_view(level, formatted)

    def _passes_filter(self, level: int, logger_name: str) -> bool:
        min_level = self.query_one("#level_filter", Select).value or 0
        module_filter = self.query_one("#module_filter", Input).value
        return level >= min_level and (not module_filter or module_filter in logger_name)

    def _append_to_view(self, level: int, formatted: str) -> None:
        colors = {10: "dim", 20: "white", 30: "yellow", 40: "red bold", 50: "red bold reverse"}
        color = colors.get(level, "white")
        self.query_one("#log_view", RichLog).write(f"[{color}]{formatted}[/{color}]")

    def _redraw(self) -> None:
        log_view = self.query_one("#log_view", RichLog)
        log_view.clear()
        for level, name, formatted in self._buffer:
            if self._passes_filter(level, name):
                self._append_to_view(level, formatted)

    def on_select_changed(self, _) -> None:
        self._redraw()

    def on_input_changed(self, _) -> None:
        self._redraw()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "clear":
            self._buffer.clear()
            self.query_one("#log_view", RichLog).clear()

    def action_dismiss(self) -> None:
        self.app.pop_screen()