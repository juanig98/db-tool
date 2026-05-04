from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, Rule

from db_tool.config.models import ConnectionProfile, Settings
from db_tool.i18n import t

_log = logging.getLogger("db_tool.tui.operation_config")


@dataclass
class OperationConfig:
    source_alias: str | None
    target_alias: str | None
    pattern: str
    obfuscate: bool
    replace: bool
    data_only: bool
    dry_run: bool
    resume: bool
    max_docs: int


class OperationConfigScreen(Screen[OperationConfig | None]):
    """Shows all configurable options before executing an operation."""

    BINDINGS = [("escape", "cancel", t("tui.operation_config.binding.cancel"))]

    def __init__(
        self,
        operation: str,
        source_alias: str | None = None,
        target_alias: str | None = None,
        source_profile: ConnectionProfile | None = None,
        target_profile: ConnectionProfile | None = None,
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._operation = operation
        self._source = source_alias
        self._target = target_alias
        self._source_profile = source_profile
        self._target_profile = target_profile
        self._settings = settings

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(t("tui.operation_config.title", operation=self._operation.upper()), id="title")

        with VerticalScroll():
            # ── Connections ───────────────────────────────────────────
            if self._source or self._target:
                yield Label(t("tui.operation_config.group.connections"), classes="section-header")
                if self._source:
                    yield Label(t("tui.operation_config.label.source", alias=self._source))
                if self._target:
                    yield Label(t("tui.operation_config.label.target", alias=self._target))

            # ── Active config info ────────────────────────────────────
            config_text = self._build_config_info()
            if config_text:
                yield Label(t("tui.operation_config.label.active_config"), classes="section-header")
                yield Label(config_text, id="config_info")

            # ── Scope ─────────────────────────────────────────────────
            yield Rule()
            yield Label(t("tui.operation_config.group.scope"), classes="section-header")
            yield Label(t("tui.operation_config.label.pattern"), classes="label-muted")
            yield Input(value=".*", id="pattern", placeholder=".*")

            # ── Options ───────────────────────────────────────────────
            yield Rule()
            yield Label(t("tui.operation_config.group.options"), classes="section-header")
            with Horizontal():
                if self._operation in ("copy", "sync", "export"):
                    yield Checkbox(t("tui.operation_config.checkbox.obfuscate"), id="obfuscate")
                if self._operation == "copy":
                    yield Checkbox(t("tui.operation_config.checkbox.replace"), id="replace")
                    yield Checkbox(t("tui.operation_config.checkbox.data_only"), id="data_only")
                    yield Checkbox(t("tui.operation_config.checkbox.resume"), id="resume")
                yield Checkbox(t("tui.operation_config.checkbox.dry_run"), id="dry_run")
            if self._operation == "copy":
                yield Label(t("tui.operation_config.label.max_docs"), classes="label-muted")
                yield Input(value="0", id="max_docs", placeholder="0")

            yield Rule()
            yield Button(t("tui.operation_config.button.start"), variant="primary", id="start")
            yield Button(t("tui.operation_config.button.cancel"), variant="default", id="cancel")

        yield Footer()

    def _build_config_info(self) -> str:
        from rich.markup import escape
        lines: list[str] = []
        if self._settings:
            lines.append(t("tui.operation_config.config.batch_size", value=self._settings.batch_size))
            throttle = self._settings.throttle_rps
            if throttle == 0:
                lines.append(t("tui.operation_config.config.throttle_disabled"))
            else:
                lines.append(t("tui.operation_config.config.throttle", value=throttle))
        if self._source_profile and self._source_profile.blacklist:
            bl = escape(", ".join(self._source_profile.blacklist))
            lines.append(t("tui.operation_config.config.source_blacklist", bl=bl))
        if self._target_profile and self._target_profile.blacklist:
            bl = escape(", ".join(self._target_profile.blacklist))
            lines.append(t("tui.operation_config.config.target_blacklist", bl=bl))
        if self._source_profile:
            lines.append(t("tui.operation_config.config.source_db",
                           name=escape(self._source_profile.database_name),
                           type=self._source_profile.type.value))
        if self._target_profile:
            lines.append(t("tui.operation_config.config.target_db",
                           name=escape(self._target_profile.database_name),
                           type=self._target_profile.type.value))
        return "\n".join(lines)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return

        pattern = self.query_one("#pattern", Input).value or ".*"
        obfuscate = (
            self.query_one("#obfuscate", Checkbox).value
            if self._operation in ("copy", "sync", "export")
            else False
        )
        dry_run = self.query_one("#dry_run", Checkbox).value

        data_only = False
        replace = False
        resume = False
        max_docs = 0
        if self._operation == "copy":
            replace = self.query_one("#replace", Checkbox).value
            data_only = self.query_one("#data_only", Checkbox).value
            resume = self.query_one("#resume", Checkbox).value
            try:
                max_docs = int(self.query_one("#max_docs", Input).value or "0")
            except ValueError:
                max_docs = 0

        _log.info(f"Operation '{self._operation}' configured: pattern={pattern!r}, obfuscate={obfuscate}, replace={replace}, dry_run={dry_run}")
        self.dismiss(OperationConfig(
            source_alias=self._source,
            target_alias=self._target,
            pattern=pattern,
            obfuscate=obfuscate,
            replace=replace,
            data_only=data_only,
            dry_run=dry_run,
            resume=resume,
            max_docs=max_docs,
        ))

    def action_cancel(self) -> None:
        self.dismiss(None)
