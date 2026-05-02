from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Label, Static

from db_tool.config.models import ConnectionProfile, Environment
from db_tool.i18n import t

_ENV_ICONS = {
    Environment.PRODUCTION: "⬤",
    Environment.STAGE:      "◆",
    Environment.DEV:        "◇",
    Environment.LOCAL:      "○",
}


class ConnectionCard(Static):
    """Displays a single connection profile summary."""

    DEFAULT_CSS = """
    ConnectionCard {
        height: auto;
        padding: 0 0 0 0;
    }
    ConnectionCard > Label {
        height: auto;
    }
    """

    def __init__(self, profile: ConnectionProfile, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.profile = profile
        self.add_class(profile.environment.value)

    def compose(self) -> ComposeResult:
        env_label = {
            Environment.PRODUCTION: t("tui.connection_card.env.production"),
            Environment.STAGE:      t("tui.connection_card.env.stage"),
            Environment.DEV:        t("tui.connection_card.env.dev"),
            Environment.LOCAL:      t("tui.connection_card.env.local"),
        }.get(self.profile.environment, self.profile.environment.value)

        icon = _ENV_ICONS.get(self.profile.environment, "·")
        db_type = self.profile.type.value.upper()
        yield Label(
            f"[bold]{self.profile.alias}[/bold]"
            f"  {icon} {env_label}"
            f"  [{db_type}]"
        )
