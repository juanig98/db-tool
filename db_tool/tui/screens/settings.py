from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Rule

from db_tool.config.loader import ConfigLoader
from db_tool.config.models import Settings
from db_tool.i18n import t


class SettingsScreen(Screen[None]):
    """Edit all settings.env values."""

    BINDINGS = [("escape", "cancel", t("tui.settings.binding.cancel"))]

    def __init__(self, loader: ConfigLoader, settings: Settings, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._loader = loader
        self._settings = settings

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(t("tui.settings.title"), id="title")

        s = self._settings
        with VerticalScroll():
            # ── Performance ───────────────────────────────────────────
            yield Label(t("tui.settings.group.performance"), classes="section-header")
            yield Label(t("tui.settings.label.batch_size"), classes="label-muted")
            yield Input(value=str(s.batch_size), id="batch_size")
            yield Label(t("tui.settings.label.throttle_rps"), classes="label-muted")
            yield Input(value=str(s.throttle_rps), id="throttle_rps")

            # ── Paths ─────────────────────────────────────────────────
            yield Rule()
            yield Label(t("tui.settings.group.paths"), classes="section-header")
            yield Label(t("tui.settings.label.state_dir"), classes="label-muted")
            yield Input(value=str(s.state_dir), id="state_dir")
            yield Label(t("tui.settings.label.mappings_dir"), classes="label-muted")
            yield Input(value=str(s.mappings_dir), id="mappings_dir")
            yield Label(t("tui.settings.label.obfuscation_rules_path"), classes="label-muted")
            yield Input(value=str(s.obfuscation_rules_path), id="obfuscation_rules_path")
            yield Label(t("tui.settings.label.replacements_path"), classes="label-muted")
            yield Input(value=str(s.replacements_path), id="replacements_path")
            yield Label(t("tui.settings.label.exclusion_rules_path"), classes="label-muted")
            yield Input(value=str(s.exclusion_rules_path), id="exclusion_rules_path")

            # ── MongoDB ───────────────────────────────────────────────
            yield Rule()
            yield Label(t("tui.settings.group.mongodb"), classes="section-header")
            yield Label(t("tui.settings.label.mongo_max_retries"), classes="label-muted")
            yield Input(value=str(s.mongo_max_retries), id="mongo_max_retries")
            yield Label(t("tui.settings.label.mongo_retry_backoff_base"), classes="label-muted")
            yield Input(value=str(s.mongo_retry_backoff_base), id="mongo_retry_backoff_base")

            # ── UI ────────────────────────────────────────────────────
            yield Rule()
            yield Label(t("tui.settings.group.ui"), classes="section-header")
            yield Label(t("tui.settings.label.language"), classes="label-muted")
            yield Input(value=str(s.language), id="language")

            yield Rule()
            yield Button(t("tui.settings.button.save"), variant="primary", id="save")
            yield Button(t("tui.settings.button.cancel"), variant="default", id="cancel")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss()
            return
        try:
            from pathlib import Path
            new_settings = Settings(
                batch_size=int(self.query_one("#batch_size", Input).value),
                throttle_rps=float(self.query_one("#throttle_rps", Input).value),
                state_dir=Path(self.query_one("#state_dir", Input).value).expanduser(),
                mappings_dir=Path(self.query_one("#mappings_dir", Input).value).expanduser(),
                obfuscation_rules_path=Path(self.query_one("#obfuscation_rules_path", Input).value),
                replacements_path=Path(self.query_one("#replacements_path", Input).value),
                exclusion_rules_path=Path(self.query_one("#exclusion_rules_path", Input).value),
                mongo_max_retries=int(self.query_one("#mongo_max_retries", Input).value),
                mongo_retry_backoff_base=float(self.query_one("#mongo_retry_backoff_base", Input).value),
                language=self.query_one("#language", Input).value,
            )
            self._loader.save_settings(new_settings)
            self.notify(t("tui.settings.success.saved"), severity="information")
            self.dismiss()
        except Exception as exc:
            self.notify(t("tui.settings.error.save_failed", exc=exc), severity="error")

    def action_cancel(self) -> None:
        self.dismiss()
