from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Rule

from db_tool.config.models import Settings
from db_tool.i18n import t


class CleanupScreen(Screen[None]):
    """Clear mappings and/or state files."""

    BINDINGS = [("escape", "go_back", t("tui.cleanup.binding.back"))]

    def __init__(self, settings: Settings, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._settings = settings

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(t("tui.cleanup.title"), id="title")

        yield Label(t("tui.cleanup.group.mappings"), classes="section-header")
        yield Label(t("tui.cleanup.label.mappings"), classes="label-muted")
        yield Button(t("tui.cleanup.button.clear_mappings"), variant="warning", id="clear_mappings")

        yield Rule()

        yield Label(t("tui.cleanup.group.state"), classes="section-header")
        yield Label(t("tui.cleanup.label.state"), classes="label-muted")
        yield Button(t("tui.cleanup.button.clear_state"), variant="warning", id="clear_state")

        yield Rule()

        yield Label(t("tui.cleanup.group.all"), classes="section-header")
        yield Label(t("tui.cleanup.label.all"), classes="label-muted")
        yield Button(t("tui.cleanup.button.clear_all"), variant="error", id="clear_all")

        yield Rule()
        yield Button(t("tui.cleanup.button.back"), variant="default", id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id in ("clear_mappings", "clear_all"):
            from db_tool.obfuscation.mappings import MappingStore
            count = MappingStore(self._settings).clear_all()
            self.notify(t("tui.cleanup.success.mappings_deleted", count=count), severity="information")
        if event.button.id in ("clear_state", "clear_all"):
            from db_tool.state.manager import StateManager
            count = StateManager(self._settings).clear_all()
            self.notify(t("tui.cleanup.success.state_deleted", count=count), severity="information")

    def action_go_back(self) -> None:
        self.dismiss()
