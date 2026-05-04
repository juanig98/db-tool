from __future__ import annotations

import logging
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Rule, Select

from db_tool.config.models import ConnectionProfile
from db_tool.config.validator import check_connection_string_signals
from db_tool.i18n import t

_log = logging.getLogger("db_tool.tui.connection_select")


class ConnectionSelectScreen(Screen[tuple[str, str] | None]):
    """Screen for selecting source and/or target connections depending on the operation."""

    CSS = """
    ConnectionSelectScreen {
        align: center top;
    }
    ConnectionSelectScreen > Label, ConnectionSelectScreen > Select, ConnectionSelectScreen > Button, ConnectionSelectScreen > Rule {
        width: 100%;
        max-width: 120;
    }
    """

    BINDINGS = [("escape", "cancel", t("tui.connection_select.binding.cancel"))]

    def __init__(
        self,
        profiles: list[ConnectionProfile],
        needs_source: bool = True,
        needs_target: bool = True,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._profiles = profiles
        self._needs_source = needs_source
        self._needs_target = needs_target
        self._profile_map: dict[str, ConnectionProfile] = {p.alias: p for p in profiles}

    def _title_key(self) -> str:
        if self._needs_source and self._needs_target:
            return "tui.connection_select.title"
        if self._needs_source:
            return "tui.connection_select.title.source_only"
        return "tui.connection_select.title.target_only"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(t(self._title_key()), id="title")

        options = [(f"{p.alias}  [{p.environment.value}]", p.alias) for p in self._profiles]

        if self._needs_source:
            yield Label(t("tui.connection_select.label.source"), classes="section-header")
            yield Select(options, id="source_select", prompt=t("tui.connection_select.prompt.source"))

        if self._needs_target:
            yield Label(t("tui.connection_select.label.target"), classes="section-header")
            yield Select(options, id="target_select", prompt=t("tui.connection_select.prompt.target"))

        yield Rule()
        yield Button(t("tui.connection_select.button.confirm"), variant="primary", id="confirm")
        yield Button(t("tui.connection_select.button.cancel"), variant="default", id="cancel")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return

        source_val = ""
        target_val = ""

        if self._needs_source:
            source_select: Select = self.query_one("#source_select", Select)
            if source_select.value is Select.BLANK:
                self.notify(t("tui.connection_select.warning.select_source"), severity="warning")
                return
            source_val = str(source_select.value)

        if self._needs_target:
            target_select: Select = self.query_one("#target_select", Select)
            if target_select.value is Select.BLANK:
                self.notify(t("tui.connection_select.warning.select_target"), severity="warning")
                return
            target_val = str(target_select.value)

        if self._needs_target and target_val:
            target_profile = self._profile_map[target_val]
            if not target_profile.allow_prod_writes:
                high = [
                    w for w in check_connection_string_signals([target_profile])
                    if w.severity == "high"
                ]
                if high:
                    self.notify(
                        t("tui.connection_select.error.prod_heuristic_block",
                          alias=target_val, keyword=high[0].matched_keyword),
                        severity="error",
                    )
                    return

        _log.info(f"Connections selected: source={source_val!r}, target={target_val!r}")
        self.dismiss((source_val, target_val))

    def action_cancel(self) -> None:
        _log.debug("Connection selection cancelled")
        self.dismiss(None)
