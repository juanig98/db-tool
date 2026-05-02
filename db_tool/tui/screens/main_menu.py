from __future__ import annotations

import logging

from rich.markup import escape as markup_escape
from textual.app import ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Rule

from db_tool.config.loader import ConfigLoader
from db_tool.config.models import Settings
from db_tool.i18n import t

_log = logging.getLogger("db_tool.tui.main_menu")


def _e(msg: str) -> str:
    return markup_escape(str(msg))


_OP_ICONS: dict[str, str] = {
    "copy":      "+",
    "sync":      "~",
    "delete":    "x",
    "obfuscate": "o",
    "export":    "^",
    "settings":  "*",
    "cleanup":   "#",
    "connections": "=",
    "quit":      "!",
}


class _LaunchOperation(Message):
    """Posted to self to push ProgressScreen from a real message handler."""
    def __init__(self, operation: str, config: object) -> None:
        super().__init__()
        self.operation = operation
        self.config = config


class MainMenuScreen(Screen[None]):
    """Main TUI screen with operation selection."""

    CSS = """
    MainMenuScreen {
        align: center top;
    }
    #menu-container {
        align: center top;
        width: 100%;
        max-width: 60;
    }
    #menu-container > Button {
        width: 100%;
    }
    #menu-container > Label {
        width: 100%;
    }
    """

    BINDINGS = [
        ("q", "quit", t("tui.main_menu.binding.quit")),
        ("up", "focus_up", "Focus up"),
        ("down", "focus_down", "Focus down"),
        ("k", "focus_up", "Focus up"),
        ("j", "focus_down", "Focus down"),
    ]

    def __init__(self, loader: ConfigLoader, settings: Settings, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._loader = loader
        self._settings = settings

    def action_quit(self) -> None:
        self.app.exit()

    def action_focus_up(self) -> None:
        buttons = list(self.query(Button))
        if not buttons:
            return
        focused = self.focused
        if focused is None:
            buttons[0].focus()
            return
        idx = buttons.index(focused)
        buttons[(idx - 1) % len(buttons)].focus()

    def action_focus_down(self) -> None:
        buttons = list(self.query(Button))
        if not buttons:
            return
        focused = self.focused
        if focused is None:
            buttons[0].focus()
            return
        idx = buttons.index(focused)
        buttons[(idx + 1) % len(buttons)].focus()

    def _btn(self, key: str, label_key: str, variant: str) -> Button:
        icon = _OP_ICONS.get(key, "›")
        return Button(f"{icon}  {t(label_key)}", variant=variant, id=key)

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="menu-container"):
            yield Label(t("tui.main_menu.title"), id="title")
            yield Label(t("tui.main_menu.subtitle"), id="subtitle")

            # Data operations
            yield Label(t("tui.main_menu.group.data"), classes="section-header")
            yield self._btn("copy",      "tui.main_menu.button.copy",      "primary")
            yield self._btn("sync",      "tui.main_menu.button.sync",      "primary")
            yield self._btn("delete",    "tui.main_menu.button.delete",    "warning")
            yield self._btn("obfuscate", "tui.main_menu.button.obfuscate", "warning")
            yield self._btn("export",    "tui.main_menu.button.export",    "default")

            yield Rule()

            # Utility
            yield Label(t("tui.main_menu.group.tools"), classes="section-header")
            yield self._btn("settings", "tui.main_menu.button.settings", "default")
            yield self._btn("connections", "tui.main_menu.button.connections", "default")
            yield self._btn("cleanup",  "tui.main_menu.button.cleanup",  "default")

            yield Rule()

            yield self._btn("quit", "tui.main_menu.button.quit", "error")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn = event.button.id
        _log.debug(f"button pressed: {btn!r}")
        if btn == "quit":
            self.app.exit()
            return
        if btn == "settings":
            from db_tool.tui.screens.settings import SettingsScreen
            self.app.push_screen(SettingsScreen(self._loader, self._settings))
            return
        if btn == "connections":
            from db_tool.tui.screens.connection_management import ConnectionManagementScreen
            self.app.push_screen(ConnectionManagementScreen(self._loader, self._settings))
            return
        if btn == "cleanup":
            from db_tool.tui.screens.cleanup import CleanupScreen
            self.app.push_screen(CleanupScreen(self._settings))
            return

        needs_source = btn in ("copy", "sync", "export")
        needs_target = btn in ("copy", "sync", "delete", "obfuscate")

        try:
            profiles = self._loader.load_profiles()
        except Exception as exc:
            self.notify(_e(exc), severity="error")
            return

        if not profiles:
            self.notify(t("tui.main_menu.error.no_connections"), severity="error")
            return

        _log.debug(f"pushing ConnectionSelectScreen for op={btn!r}")
        from db_tool.tui.screens.connection_select import ConnectionSelectScreen

        def _on_connections(result: tuple[str, str] | None) -> None:
            _log.debug(f"_on_connections called with result={result!r}")
            if result is None:
                return
            source_alias, target_alias = result

            source_profile = None
            target_profile = None
            try:
                if needs_source and source_alias:
                    source_profile = self._loader.get_profile(source_alias)
                if needs_target and target_alias:
                    target_profile = self._loader.get_profile(target_alias)
            except Exception as exc:
                self.notify(str(exc), severity="error")
                return

            _log.debug(f"pushing OperationConfigScreen for op={btn!r}, src={source_alias!r}, tgt={target_alias!r}")
            from db_tool.tui.screens.operation_config import OperationConfigScreen

            def _on_config(config: object) -> None:
                _log.debug(f"_on_config called with config={config!r}")
                if config is None:
                    return
                _log.debug("_on_config: posting _LaunchOperation message")
                self.post_message(_LaunchOperation(btn, config))

            self.app.push_screen(
                OperationConfigScreen(
                    operation=btn,
                    source_alias=source_alias if needs_source else None,
                    target_alias=target_alias if needs_target else None,
                    source_profile=source_profile,
                    target_profile=target_profile,
                    settings=self._settings,
                ),
                _on_config,
            )

        self.app.push_screen(
            ConnectionSelectScreen(profiles, needs_source=needs_source, needs_target=needs_target),
            _on_connections,
        )

    def on__launch_operation(self, message: _LaunchOperation) -> None:
        _log.debug(f"on__launch_operation: op={message.operation!r}")
        self._run_operation(message.operation, message.config)

    def _run_operation(self, operation: str, config: object) -> None:
        from db_tool.tui.screens.operation_config import OperationConfig
        from db_tool.tui.screens.progress import ProgressScreen

        _log.debug(f"_run_operation: op={operation!r}, config={config!r}")
        if not isinstance(config, OperationConfig):
            _log.debug("_run_operation: config is not OperationConfig, aborting")
            return

        _log.debug("pushing ProgressScreen")
        try:
            screen = ProgressScreen(operation, config, self._loader, self._settings)
            _log.debug(f"BEFORE push: screen id={id(screen)}, _running={screen._running}, _task={screen._task}, in_registry={screen in self.app._registry}")
            _log.debug(f"BEFORE push: app._running={self.app._running}, stack={[type(s).__name__ for s in self.app.screen_stack]}")
            self.app.push_screen(screen)
            _log.debug(f"AFTER push: stack={[type(s).__name__ for s in self.app.screen_stack]}")
            _log.debug(f"AFTER push: screen._running={screen._running}, _task={screen._task}, in_registry={screen in self.app._registry}")
        except Exception as exc:
            _log.error(f"push_screen raised: {exc!r}", exc_info=True)
