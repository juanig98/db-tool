from __future__ import annotations

import logging
from typing import Any

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select, TextArea

from db_tool.config.loader import ConfigLoader
from db_tool.config.models import ConnectionProfile, ConnectorType, Environment
from db_tool.i18n import t

_log = logging.getLogger("db_tool.tui.connection_form")

_ENV_OPTIONS = [
    (t("tui.connections.form.env.production"), Environment.PRODUCTION.value),
    (t("tui.connections.form.env.stage"), Environment.STAGE.value),
    (t("tui.connections.form.env.dev"), Environment.DEV.value),
    (t("tui.connections.form.env.local"), Environment.LOCAL.value),
]

_TYPE_OPTIONS = [
    (t("tui.connections.form.type.mongodb").upper(), ConnectorType.MONGODB.value),
    (t("tui.connections.form.type.bigquery").upper(), ConnectorType.BIGQUERY.value),
    (t("tui.connections.form.type.mysql").upper(), ConnectorType.MYSQL.value),
]


class ConnectionFormScreen(Screen[bool | None]):
    """Form screen for adding or editing a connection profile."""

    BINDINGS = [("escape", "cancel", t("tui.connections.form.binding.cancel"))]

    def __init__(
        self,
        loader: ConfigLoader,
        profile: ConnectionProfile | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._loader = loader
        self._profile = profile
        self._is_edit = profile is not None

    @property
    def _title_key(self) -> str:
        return "tui.connections.form.title_edit" if self._is_edit else "tui.connections.form.title_add"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(t(self._title_key), id="title")

        if self._is_edit and self._profile and self._profile.environment == Environment.PRODUCTION:
            yield Label(t("tui.connections.error.production_protected"), classes="warning-banner")

        with VerticalScroll():
            yield Label(t("tui.connections.label.alias"), classes="label-muted")
            yield Input(
                value=self._profile.alias if self._profile else "",
                id="alias",
                disabled=self._is_edit,
            )

            yield Label(t("tui.connections.label.environment"), classes="label-muted")
            env_value = self._profile.environment.value if self._profile else Environment.LOCAL.value
            yield Select(_ENV_OPTIONS, value=env_value, id="environment")

            yield Label(t("tui.connections.label.type"), classes="label-muted")
            type_value = self._profile.type.value if self._profile else ConnectorType.MONGODB.value
            yield Select(_TYPE_OPTIONS, value=type_value, id="type")

            yield Label(t("tui.connections.label.connection_string"), classes="label-muted")
            yield Input(
                value=self._profile.connection_string if self._profile else "",
                id="connection_string",
                password=True,
            )

            yield Label(t("tui.connections.label.database_name"), classes="label-muted")
            yield Input(
                value=self._profile.database_name if self._profile else "",
                id="database_name",
            )

            yield Label(t("tui.connections.label.blacklist"), classes="label-muted")
            blacklist_str = "\n".join(self._profile.blacklist) if self._profile and self._profile.blacklist else ""
            yield TextArea(blacklist_str, id="blacklist")

        is_production = self._is_edit and self._profile and self._profile.environment == Environment.PRODUCTION
        yield Button(
            t("tui.connections.button.save"),
            variant="primary",
            id="save",
            disabled=is_production,
        )
        yield Button(t("tui.connections.button.cancel"), variant="default", id="cancel")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return

        if event.button.id == "save":
            self._save()

    def _save(self) -> None:
        alias = self.query_one("#alias", Input).value.strip()
        if not alias:
            self.notify(t("tui.connections.error.alias_required"), severity="error")
            return

        env_select: Select = self.query_one("#environment", Select)
        env = Environment(env_select.value)

        type_select: Select = self.query_one("#type", Select)
        ctype = ConnectorType(type_select.value)

        connection_string = self.query_one("#connection_string", Input).value
        database_name = self.query_one("#database_name", Input).value

        blacklist_ta: TextArea = self.query_one("#blacklist", TextArea)
        blacklist = [line.strip() for line in blacklist_ta.text.split("\n") if line.strip()]

        profile = ConnectionProfile(
            alias=alias,
            environment=env,
            type=ctype,
            connection_string=connection_string,
            database_name=database_name,
            blacklist=blacklist,
        )

        try:
            if self._is_edit:
                if self._profile:
                    from db_tool.config.validator import guard_connection_mutation

                    guard_connection_mutation(self._profile)
                self._loader.update_profile(alias, profile)
                self.notify(t("tui.connections.success.updated"))
            else:
                if env == Environment.PRODUCTION:
                    self.notify(t("tui.connections.warning.production_create"), severity="warning")
                self._loader.add_profile(profile)
                self.notify(t("tui.connections.success.added"))

            self.dismiss(True)
        except Exception as exc:
            _log.error(f"Failed to save profile: {exc!r}")
            self.notify(str(exc), severity="error")

    def action_cancel(self) -> None:
        self.dismiss(None)