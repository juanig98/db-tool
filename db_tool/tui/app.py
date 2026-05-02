from __future__ import annotations

from textual.app import App

from db_tool.config.loader import ConfigLoader
from db_tool.tui.screens.main_menu import MainMenuScreen
from db_tool.tui.screens.logs import LogsScreen
from db_tool.tui.theme import BrandTheme

# Cargamos el tema una sola vez al importar el módulo para poder
# interpolar los colores custom (env-*) directamente en el CSS.
_brand = BrandTheme.load()


def _build_css(th: BrandTheme) -> str:
    return f"""
    Screen {{
        align: center top;
        padding: 1 2;
    }}

    ConnectionManagementScreen {{
        align: left top;
    }}
    ConnectionManagementScreen > VerticalScroll {{
        width: 100%;
    }}
    ConnectionManagementScreen VerticalScroll > * {{
        height: auto;
        margin-bottom: 0;
    }}
    ConnectionManagementScreen Label {{
        width: 100%;
        height: auto;
        padding: 0;
    }}
    ConnectionManagementScreen Button {{
        width: auto;
        min-height: 1;
        margin: 0 1 0 0;
    }}
    ConnectionManagementScreen Horizontal {{
        height: auto;
        layout: horizontal;
    }}

    /* ── Títulos ─────────────────────────────────────────────────── */
    #title {{
        text-align: center;
        margin: 1 0 0 0;
        color: $primary;
        text-style: bold;
    }}
    #subtitle {{
        text-align: center;
        color: {th.text_muted};
        margin: 0 0 1 0;
    }}
    .section-header {{
        color: $secondary;
        text-style: bold;
        margin: 1 0 0 0;
        width: 100%;
    }}

    .warning-banner {{
        color: $error;
        text-style: bold;
        margin: 1 0;
    }}

/* ── Botones ─────────────────────────────────────────────────── */
    Button {{
        width: 100%;
        margin: 0 0 1 0;
    }}
    Button.btn-sm {{
        width: auto;
        margin: 0 1 0 0;
    }}

    /* ── Selects e Inputs ────────────────────────────────────────── */
    Select {{
        width: 100%;
        margin: 0 0 1 0;
    }}
    Input {{
        width: 100%;
 margin: 0 0 1 0;
    }}
    TextArea {{
        width: 100%;
        margin: 0 0 1 0;
    }}

    /* ── Labels generales ──────────────────────────────────────────── */
    Label {{
        margin: 0 0 0 0;
    }}
    .label-muted {{
        color: {th.text_muted};
    }}

    /* ── Panel de config activa (OperationConfigScreen) ──────────── */
    #config_info {{
        border: tall $panel;
        background: $surface;
        padding: 0 1;
        margin: 1 0;
        width: 100%;
        color: {th.text_muted};
    }}

    /* ── Progreso ────────────────────────────────────────────────── */
    ProgressScreen {{
        align: left top;
        padding: 1 2;
    }}
    ProgressScreen #title,
    ProgressScreen #collection_label,
    ProgressScreen #status_label,
    ProgressScreen Rule,
    ProgressScreen Log,
    ProgressScreen ProgressBar {{
        width: 100%;
        max-width: 100%;
    }}
    #collection_label {{
        height: 1;
        margin: 0 0 0 0;
    }}
    #status_label {{
        color: $success;
        height: 1;
        margin: 0 0 1 0;
    }}
    Log {{
        border: tall $panel;
        background: $surface;
        margin: 0 0 1 0;
        width: 100%;
        height: 1fr;
        min-height: 8;
    }}
    ProgressBar {{
        width: 100%;
        margin: 0 0 1 0;
    }}

    /* ── Connection cards ────────────────────────────────────────── */
    ConnectionCard {{
        border: tall $panel;
        background: $surface;
        padding: 0 1;
        margin: 0 0 1 0;
        width: 100%;
    }}
    ConnectionCard.production {{ border: tall {th.env_production}; }}
    ConnectionCard.stage      {{ border: tall {th.env_stage};      }}
    ConnectionCard.dev        {{ border: tall {th.env_dev};        }}
    ConnectionCard.local      {{ border: tall {th.env_local};      }}

    /* ── Separadores ─────────────────────────────────────────────── */
    Rule {{
        width: 100%;
        margin: 1 0;
        color: $panel;
    }}

    /* ── Scroll containers ───────────────────────────────────────── */
    VerticalScroll {{
        width: 100%;
        height: auto;
    }}

    /* ── MainMenuScreen ─────────────────────────────────────────────── */
    MainMenuScreen {{
        align: center top;
    }}
    MainMenuScreen Button {{
        max-width: 60;
    }}
    MainMenuScreen Input {{
        max-width: 60;
    }}
    MainMenuScreen Select {{
        max-width: 60;
    }}
    MainMenuScreen .section-header {{
        max-width: 60;
    }}

    LogsScreen {{
        align: left top;
        padding: 1 2;
    }}
    LogsScreen #log_view {{
        width: 100%;
        max-width: 100%;
        height: 1fr;
        border: tall $panel;
        background: $surface;
    }}
    LogsScreen #level_filter {{
        width: 20;
        max-width: 20;
    }}
    LogsScreen #module_filter {{
        width: 1fr;
    }}
    """


class DBToolApp(App[None]):
    """db-tool TUI application."""

    from db_tool.i18n import t as _t
    TITLE = _t("tui.app.title")
    SUB_TITLE = _t("tui.app.subtitle")

    CSS = _build_css(_brand)
    SCREENS = {"logs": LogsScreen}
    BINDINGS = [("ctrl+l", "push_screen('logs')", "Logs")]

    def __init__(self, debug: bool = False, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._loader = ConfigLoader()
        self._debug = debug
        self._tui_log_handler = None
        import logging
        self._log = logging.getLogger("db_tool.tui.app")

    def on_exception(self, error: Exception) -> None:
        self._log.error(f"on_exception: {error!r}", exc_info=True)

    def _handle_exception(self, error: Exception) -> None:
        self._log.error(f"_handle_exception: {error!r}", exc_info=True)
        super()._handle_exception(error)

    def on_mount(self) -> None:
        from db_tool.logging_config import setup_logging
        from db_tool.tui.log_handler import TextualLogHandler, LogEntryReceived

        self._tui_log_handler = TextualLogHandler(self)
        setup_logging(debug=self._debug, tui_handler=self._tui_log_handler)

        self.register_theme(_brand.to_textual_theme())  # type: ignore[arg-type]
        self.theme = "db-tool"

        try:
            settings = self._loader.load_settings()
        except Exception as exc:
            from db_tool.i18n import t
            self.notify(t("tui.app.error.settings_failed", exc=exc), severity="error", timeout=10)
            settings = __import__("db_tool.config.models", fromlist=["Settings"]).Settings()

        try:
            self._loader.load_profiles()
            for w in self._loader.get_connection_warnings():
                from db_tool.i18n import t
                msg = t(
                    "validator.warning.connection_string_mismatch",
                    alias=w.alias,
                    declared=w.declared_env.value,
                    detected=w.detected_env.value,
                    keyword=w.matched_keyword,
                    severity=w.severity.upper(),
                )
                self.notify(msg, severity="error" if w.severity == "high" else "warning", timeout=15)
        except Exception:
            pass

        self.push_screen(MainMenuScreen(self._loader, settings))

    def on_log_entry_received(self, message: LogEntryReceived) -> None:
        from db_tool.tui.screens.logs import LogsScreen
        if self.screen_stack and isinstance(self.screen_stack[-1], LogsScreen):
            self.screen_stack[-1].add_entry(message.level, message.logger_name, message.formatted)
