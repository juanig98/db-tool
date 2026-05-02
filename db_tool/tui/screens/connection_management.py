from __future__ import annotations

import logging
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label

from db_tool.config.loader import ConfigLoader
from db_tool.config.models import ConnectionProfile, Settings
from db_tool.i18n import t
from db_tool.tui.widgets.connection_card import ConnectionCard

_log = logging.getLogger("db_tool.tui.connection_management")


class ConnectionManagementScreen(Screen[None]):
    """Screen for managing connection profiles."""

    BINDINGS = [("escape", "cancel", t("tui.connections.binding.cancel"))]

    def __init__(self, loader: ConfigLoader, settings: Settings, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._loader = loader
        self._settings = settings
        self._profiles: list[ConnectionProfile] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(t("tui.connections.title"), id="title")

        with VerticalScroll(id="profiles_container"):
            yield Label(t("tui.connections.no_profiles"), id="empty_msg")

        yield Button(t("tui.connections.button.add"), variant="primary", id="add")
        yield Footer()

    def on_mount(self) -> None:
        self._load_profiles()

    def _load_profiles(self) -> None:
        try:
            self._profiles = self._loader.load_profiles()
        except Exception as exc:
            _log.error(f"Failed to load profiles: {exc!r}")
            self.notify(str(exc), severity="error")
            return
        self._render_profiles()

    def _render_profiles(self) -> None:
        container = self.query_one("#profiles_container", VerticalScroll)
        container.remove_children()

        if not self._profiles:
            container.mount(Label(t("tui.connections.no_profiles"), id="empty_msg"))
            return

        from textual.containers import Horizontal
        for profile in self._profiles:
            safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in profile.alias)
            card = ConnectionCard(profile)
            container.mount(card)
            with card.prevent(Button.Pressed):
                card.mount(
                    Horizontal(
                        Button(t("tui.connections.button.edit"), variant="default", id=f"edit_{safe_id}", classes="btn-sm"),
                        Button(t("tui.connections.button.delete"), variant="error", id=f"delete_{safe_id}", classes="btn-sm"),
                    )
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id

        if btn_id == "add":
            self._go_form(None)
            return

        if btn_id and btn_id.startswith("edit_"):
            safe_id = btn_id[5:]
            profile = next((p for p in self._profiles if "".join(c if c.isalnum() or c in "-_" else "_" for c in p.alias) == safe_id), None)
            if profile:
                self._go_form(profile)
            return

        if btn_id and btn_id.startswith("delete_"):
            safe_id = btn_id[7:]
            alias = next((p.alias for p in self._profiles if "".join(c if c.isalnum() or c in "-_" else "_" for c in p.alias) == safe_id), None)
            self._delete_profile(alias)
            return

    def _go_form(self, profile: ConnectionProfile | None) -> None:
        from db_tool.tui.screens.connection_form import ConnectionFormScreen

        def on_save(success: bool | None) -> None:
            if success:
                self._load_profiles()

        self.app.push_screen(ConnectionFormScreen(self._loader, profile), on_save)

    def _delete_profile(self, alias: str) -> None:
        profile = next((p for p in self._profiles if p.alias == alias), None)
        if not profile:
            return

        try:
            from db_tool.config.validator import guard_connection_mutation

            guard_connection_mutation(profile)
        except Exception as exc:
            self.notify(str(exc), severity="error")
            return

        try:
            self._loader.remove_profile(alias)
            _log.info(f"Connection profile deleted: {alias}")
            self.notify(t("tui.connections.success.deleted"))
            self._load_profiles()
        except Exception as exc:
            _log.error(f"Failed to delete profile: {exc!r}")
            self.notify(str(exc), severity="error")

    def action_cancel(self) -> None:
        self.app.pop_screen()