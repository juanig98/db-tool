
# Plan: Logging completo — Opción C híbrida

## Contexto

El proyecto solo tiene logging en 3 archivos TUI (`app.py`, `main_menu.py`, `progress.py`). El resto del codebase (connectors, operations, obfuscation, config, state, otras pantallas TUI) no tiene logging. La configuración actual es un `_setup_file_logger()` hardcodeado en `app.py` que escribe a `/tmp/db-tool.log` y se activa al importar el módulo (problemático para tests).

El objetivo es: logging centralizado en todo el codebase, flag `--debug` que emite a stderr en la terminal que lanzó la app, y un panel de logs accesible en la TUI con filtro por nivel.

---

## Fase 1 — Infraestructura base

### 1.1 Crear `db_tool/logging_config.py`

```python
_configured = False

def setup_logging(
    log_path: Path | None = None,
    debug: bool = False,
    tui_handler: logging.Handler | None = None,
) -> None:
    global _configured
    if _configured:
        return  # idempotente
    _configured = True

    path = log_path or Path(os.environ.get("DBTOOL_LOG", "/tmp/db-tool.log"))
    root = logging.getLogger("db_tool")
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    # Handler a archivo (siempre, nivel DEBUG)
    fh = logging.FileHandler(path, mode="a", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s — %(message)s"))
    root.addHandler(fh)

    # Handler a stderr (solo si --debug)
    if debug:
        sh = logging.StreamHandler(sys.stderr)
        sh.setLevel(logging.DEBUG)
        sh.setFormatter(logging.Formatter("%(levelname)-8s %(name)s — %(message)s"))
        root.addHandler(sh)

    # Handler TUI (inyectado desde DBToolApp)
    if tui_handler:
        tui_handler.setLevel(logging.WARNING if not debug else logging.DEBUG)
        root.addHandler(tui_handler)

    # Silenciar librerías de terceros
    logging.getLogger("textual").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)

def get_log_path() -> Path:
    return Path(os.environ.get("DBTOOL_LOG", "/tmp/db-tool.log"))
```

### 1.2 Modificar `db_tool/tui/app.py`

- **Eliminar** `_setup_file_logger()` y su llamada de nivel de módulo (línea 24)
- **Eliminar** `import logging`, `import os`, `from pathlib import Path`, `_log` a nivel de módulo (solo los del setup antiguo)
- En `DBToolApp.__init__()`, agregar `debug: bool = False` y guardar `self._debug = debug`
- En `DBToolApp.on_mount()`:
  ```python
  from db_tool.logging_config import setup_logging
  from db_tool.tui.log_handler import TextualLogHandler
  self._tui_log_handler = TextualLogHandler(self)
  setup_logging(debug=self._debug, tui_handler=self._tui_log_handler)
  ```
- En `DBToolApp` agregar handler del mensaje:
  ```python
  def on_log_entry_received(self, message: LogEntryReceived) -> None:
      # repostear a LogsScreen si está montada
      if self.is_screen_installed("logs"):
          screen = self.get_screen("logs")
          if isinstance(screen, LogsScreen) and screen.is_running:
              screen.add_entry(message.level, message.logger_name, message.formatted)
  ```
- Registrar `LogsScreen`: `SCREENS = {"logs": LogsScreen}`
- Agregar binding: `BINDINGS = [("l", "push_screen('logs')", "Logs")]`

### 1.3 Modificar `db_tool/cli/commands.py`

Agregar callback global con `--debug`:
```python
@app.callback()
def _global_options(
    debug: bool = typer.Option(False, "--debug", is_eager=False, help="Enable debug logging to stderr"),
) -> None:
    from db_tool.logging_config import setup_logging
    setup_logging(debug=debug)
```

Modificar el subcomando `tui`:
```python
@app.command(help=t("cli.tui.help"))
def tui(debug: bool = typer.Option(False, "--debug", help="Enable debug logging")):
    from db_tool.logging_config import setup_logging
    from db_tool.tui.app import DBToolApp
    setup_logging(debug=debug)
    DBToolApp(debug=debug).run()
```

### 1.4 Crear `db_tool/tui/log_handler.py`

```python
import logging
from textual.message import Message

class LogEntryReceived(Message):
    def __init__(self, level: int, logger_name: str, formatted: str) -> None:
        super().__init__()
        self.level = level
        self.logger_name = logger_name
        self.formatted = formatted

class TextualLogHandler(logging.Handler):
    def __init__(self, app) -> None:
        super().__init__()
        self._app = app

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._app.call_from_thread(
                self._app.post_message,
                LogEntryReceived(record.levelno, record.name, msg)
            )
        except Exception:
            self.handleError(record)
```

---

## Fase 2 — Propagación de logging a todos los módulos

Agregar en cada archivo:
```python
import logging
_log = logging.getLogger(__name__)
```

Eventos a loguear por módulo:

| Módulo | Nivel | Qué |
|--------|-------|-----|
| `connectors/mongodb.py` | INFO | connect/disconnect con alias |
| `connectors/mongodb.py` | DEBUG | cada retry con sleep |
| `connectors/bigquery.py` | INFO | connect/disconnect |
| `connectors/mysql.py` | INFO | connect/disconnect |
| `operations/copy.py` | INFO | inicio (N colecciones), fin por colección |
| `operations/copy.py` | WARNING | error en colección |
| `operations/copy.py` | DEBUG | inicio/fin de cada batch |
| `operations/sync.py` | INFO | mismo patrón que copy |
| `operations/delete.py` | INFO | colecciones eliminadas |
| `operations/export.py` | INFO | archivos exportados |
| `operations/obfuscate.py` | INFO | colecciones procesadas |
| `obfuscation/engine.py` | INFO | N reglas cargadas |
| `obfuscation/engine.py` | WARNING | faker_type desconocido |
| `config/loader.py` | INFO | archivo de config cargado |
| `config/loader.py` | WARNING | settings.env no encontrado, usando defaults |
| `config/validator.py` | WARNING | escritura a producción bloqueada |
| `state/manager.py` | DEBUG | checkpoint guardado/cargado |
| TUI screens restantes | DEBUG | on_mount, eventos de usuario clave |

---

## Fase 3 — Panel de logs TUI

### 3.1 Crear `db_tool/tui/screens/logs.py`

```python
from collections import deque
_MAX_ENTRIES = 1000

class LogsScreen(Screen[None]):
    BINDINGS = [("escape", "dismiss", "Volver")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._buffer: deque[tuple[int, str, str]] = deque(maxlen=_MAX_ENTRIES)

    def compose(self) -> ComposeResult:
        yield Header()
        # Fila de controles: Select nivel + Input filtro + Button limpiar
        yield Select([("ALL",0),("DEBUG",10),("INFO",20),("WARNING",30),("ERROR",40)],
                     id="level_filter", value=0)
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
```

### 3.2 CSS para LogsScreen (en `app.py` → `_build_css()`)

```css
LogsScreen {
    align: left top;
    padding: 1 2;
}
LogsScreen #log_view {
    width: 100%;
    max-width: 100%;
    height: 1fr;
    border: tall $panel;
    background: $surface;
}
LogsScreen #level_filter {
    width: 20;
    max-width: 20;
}
LogsScreen #module_filter {
    width: 1fr;
}
```

---

## Traducciones a agregar

En `en.json` y `es.json`:
- `tui.logs.title`: "Logs" / "Logs"
- `tui.logs.binding.back`: "Back" / "Volver"
- `tui.logs.button.clear`: "Clear" / "Limpiar"
- `tui.logs.filter.placeholder`: "Filter by module..." / "Filtrar por módulo..."
- `cli.tui.option.debug`: "Enable debug logging to stderr" / "Activar logging debug en stderr"

---

## Archivos a crear/modificar

| Archivo | Acción |
|---------|--------|
| `db_tool/logging_config.py` | CREAR |
| `db_tool/tui/log_handler.py` | CREAR |
| `db_tool/tui/screens/logs.py` | CREAR |
| `db_tool/tui/app.py` | MODIFICAR — eliminar setup antiguo, integrar handler TUI, registrar LogsScreen |
| `db_tool/cli/commands.py` | MODIFICAR — callback --debug, flag en tui() |
| `db_tool/connectors/*.py` | MODIFICAR — agregar _log y llamadas |
| `db_tool/operations/*.py` | MODIFICAR — agregar _log y llamadas |
| `db_tool/obfuscation/*.py` | MODIFICAR — agregar _log y llamadas |
| `db_tool/config/loader.py`, `validator.py` | MODIFICAR — agregar _log y llamadas |
| `db_tool/state/manager.py` | MODIFICAR — agregar _log y llamadas |
| `db_tool/tui/screens/*.py` (restantes) | MODIFICAR — agregar _log |
| `db_tool/i18n/translations/en.json` | MODIFICAR — agregar keys de logs |
| `db_tool/i18n/translations/es.json` | MODIFICAR — agregar keys de logs |
| `docs/architecture.md` | MODIFICAR — documentar sistema de logging |

---

## Tests a agregar

- `tests/unit/test_logging_config.py`:
  - `test_setup_logging_idempotent` — segunda llamada no agrega handlers duplicados
  - `test_debug_adds_stderr_handler` — con `debug=True` hay StreamHandler en stderr
  - `test_textual_logger_stays_warning` — logger "textual" siempre en WARNING

- `tests/unit/tui/test_log_handler.py`:
  - `test_emit_calls_post_message` — mock de `app.call_from_thread`, verifica que se llama con `LogEntryReceived`

- `tests/unit/tui/test_logs_screen.py`:
  - `test_logs_screen_renders` — monta y tiene `#log_view`, `#level_filter`
  - `test_filter_by_level` — agrega entries de distintos niveles, verifica filtro
  - `test_clear_empties_buffer` — presiona clear, buffer vacío

---

## Verificación end-to-end

```bash
# 1. Tests unitarios
pytest tests/unit/ -q  # deben pasar los 136 + nuevos

# 2. CLI con --debug (stderr visible en terminal)
source .venv/bin/activate
db-tool --debug copy --source alias1 --target alias2 --dry-run

# 3. TUI con --debug
db-tool tui --debug
# Presionar L → panel de logs aparece
# Hacer una operación → logs aparecen en panel en tiempo real
# Cambiar filtro de nivel → se actualiza la vista
# Los logs también aparecen en stderr de la terminal que lanzó la app
```
