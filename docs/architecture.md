# Arquitectura de db-tool

## Visión general

db-tool es una herramienta de línea de comandos con TUI para copiar, sincronizar y ofuscar datos entre bases de datos heterogéneas. El flujo principal es: **leer de un origen → ofuscar en memoria → escribir en un destino no productivo**.

## Capas

```
┌─────────────────────────────────────────────┐
│              CLI (Typer)   TUI (Textual)     │  Interfaz de usuario
├─────────────────────────────────────────────┤
│   copy · sync · delete · obfuscate · export │  Operaciones
├──────────────────┬──────────────────────────┤
│  ObfuscationEngine│     StateManager         │  Servicios
├──────────────────┴──────────────────────────┤
│  MongoDBConnector · BigQueryConnector · MySQL│  Conectores
├─────────────────────────────────────────────┤
│         ConfigLoader + Validator             │  Configuración
└─────────────────────────────────────────────┘
```

## Flujo de datos: copy con ofuscación

```
Source DB
  │
  ├─ iter_documents(batch_size)
  │       │
  │   [batch de docs]
  │       │
  │   ObfuscationEngine.transform(doc)   ← en memoria, nunca toca el origen
  │       │
  │   [batch ofuscado]
  │       │
  └─ Target DB ← upsert_batch()
              │
          StateManager.mark_batch_done()
```

## Módulos clave

### `config/`
- **`models.py`**: `ConnectionProfile` y `Settings` como modelos Pydantic. `ConnectionProfile` tiene `is_production`, `is_stage`, `is_writable` como propiedades derivadas.
- **`loader.py`**: `ConfigLoader` lee `connections.yaml` y `settings.env`. También expone `save_settings()` para que la TUI persista cambios.
- **`validator.py`**: Guards de protección. `guard_write()` lanza `ProductionWriteError`. `filter_blacklist()` aplica los regex de blacklist de un perfil.

### `connectors/`
- **`base.py`**: `AbstractConnector` ABC. Define la interfaz común: `connect`, `disconnect`, `list_collections`, `iter_documents`, `upsert_batch`, `delete_collection`, `copy_indexes`, `get_document`. `assert_write_allowed()` delega a `validator.guard_write()`.
- **`mongodb.py`**: Maneja CosmosDB y MongoDB. Retry automático en error 16500 (RU exhaustion). Throttling configurable por `settings.throttle_rps`.
- **`bigquery.py`** y **`mysql.py`**: Misma interfaz. Documentos anidados serializados como JSON string (Option A).

### `operations/`
Cada módulo expone una función `run_<op>(source, target, pattern, settings, ...)` que:
1. Verifica protecciones (`assert_write_allowed`)
2. Lista y filtra colecciones por regex + blacklist
3. Itera en batches, emite `ProgressEvent` por callback
4. Delega ofuscación al `ObfuscationEngine` si está presente

### `obfuscation/`
- **`fixed_rules.py`**: 20 reglas precompiladas para email, nombre, teléfono, dirección, documentos de identidad.
- **`dynamic_rules.py`**: Parser de `obfuscation_rules.txt`. Formato: `field_regex::value_regex::faker_type`.
- **`mappings.py`**: `MappingStore` — garantiza consistencia referencial. Persiste en `~/.db-tool/mappings/<sha256>.json` por (valor_real, faker_type).
- **`engine.py`**: `ObfuscationEngine` aplica ambas capas de forma recursiva. Carga dinámicos del archivo configurado. No muta el documento original.

### `state/`
- **`manager.py`**: `StateManager` persiste progreso por batch en `~/.db-tool/state/<sha256>.json`. La clave es `sha256(source_alias + target_alias + collection)`. Permite retomar (`--resume`) operaciones interrumpidas.

### `cli/`
- **`commands.py`**: Subcomandos Typer. Cada comando aplica las protecciones antes de invocar la operación.
- **`formatters.py`**: Helpers Rich para tablas, confirmaciones interactivas, y `print_progress()` como `progress_callback`.

### `tui/`
- **`app.py`**: `DBToolApp(App)` — carga config al iniciar, empuja `MainMenuScreen`. Incluye sistema de logging centralizado con panel de logs accesible via `Ctrl+L`.
- Screens: `main_menu` → `connection_select` → `operation_config` → `progress`. Settings, cleanup y connection management son accesibles desde el menú.
- El `progress_callback` de las operaciones llama a `ProgressScreen.on_progress_event()`.
- **Screens TUI adicionales**:
  - `settings.py`: Edita settings.env (batch_size, throttle, paths, MongoDB config, language)
  - `cleanup.py`: Limpia state y mappings
  - `connection_management.py`: Lista, agrega, edita y elimina perfiles de conexión
  - `connection_form.py`: Formulario reutilizable para Add/Edit de conexiones
  - `logs.py`: Panel de logs con filtros por nivel y módulo (Ctrl+L)

### `logging_config.py`
- Sistema centralizado de logging que escribe a `/tmp/db-tool.log`
- Soporta flag `--debug` que también emite a stderr
- Handler TUI que pasa logs al panel en tiempo real
- Buffer global para ver logs históricos al abrir la screen de logs
- Silencia librerías de terceros (textual, pymongo) a nivel WARNING

## Canal CLI ↔ TUI: ProgressEvent

```python
@dataclass
class ProgressEvent:
    collection: str
    batch_index: int
    docs_processed: int
    docs_total: int
    upserted: int
    modified: int
    skipped: int
    phase: Literal["reading", "writing", "indexing", "complete", "error"]
    error: str | None = None
```

Las operaciones solo saben emitir `ProgressEvent`. CLI y TUI deciden cómo renderizarlo.

## Almacenamiento persistente

| Artefacto | Ubicación | Limpieza |
|-----------|-----------|----------|
| Estado de operación | `~/.db-tool/state/<sha256>.json` | `db-tool cleanup state` |
| Mappings de ofuscación | `~/.db-tool/mappings/<shard>/<sha256>.json` | `db-tool cleanup mappings` |

## Reglas de protección

| Entorno | Escritura | Modificar config |
|---------|-----------|-----------------|
| `production` | Bloqueado | Bloqueado |
| `stage` | Confirmación | Confirmación |
| `dev` / `local` | Libre | Libre |

Copia desde `production` sin `--obfuscate` → confirmación obligatoria.

### Connection String Guardian

Sistema de detección de inconsistencias entre el entorno declarado (`environment`) y las señales en la `connection_string`.

- **`validator.py`**: `ENVIRONMENT_SIGNALS` mapea palabras clave a entornos (prod→["prod","prd","live"], stage→["stage","staging"], dev→["dev","develop"], local→["localhost","127.0.0.1"])
- **`check_connection_string_signals()`**: Detecta cuando una connection_string contiene palabras de un entorno diferente al declarado
- **Severity**: HIGH (perfil no es producción pero la string señala producción), MEDIUM (cualquier otro cruce)
- Se muestra como notificación en TUI y como warning en CLI stderr
- No bloquea operaciones, solo avisa


## Sistema i18n

El módulo `db_tool/i18n/` provee internacionalización completa para todos los textos del proyecto.

### Cómo funciona

- `db_tool/i18n/__init__.py` expone la función `t(key, **kwargs) -> str`
- Al importar el módulo, se auto-carga el idioma desde la variable de entorno `LANGUAGE` (por defecto `en`)
- `setup(lang)` recarga las traducciones en runtime (se llama automáticamente desde `load_settings()`)
- Las keys faltantes devuelven la key misma (fail-safe)

### Archivos de traducción

| Archivo | Idioma |
|---------|--------|
| `db_tool/i18n/translations/en.json` | Inglés |
| `db_tool/i18n/translations/es.json` | Español |

### Configuración

La variable `LANGUAGE` se puede definir en `settings.env` o como variable de entorno del sistema. Valores soportados: `en`, `es`.

```bash
# En settings.env
LANGUAGE=es

# O como variable de entorno (tiene precedencia)
LANGUAGE=es ./run.sh --help
```

### Agregar un nuevo idioma

1. Crear `db_tool/i18n/translations/<lang>.json` con todas las keys de `en.json` traducidas
2. Agregar `"<lang>"` a la validación en `db_tool/config/models.py` → `language_valid()`
3. Actualizar la opción en `tui/screens/settings.py` label `tui.settings.label.language` en ambos JSON

## Tests

El proyecto usa **pytest** con tests unitarios que no requieren conexión a bases de datos reales.

### Estructura

```
tests/
├── conftest.py                 # Fixtures (FakeConnector, profiles, settings)
├── unit/
│   ├── config/                 # Tests de config/models.py, loader.py, validator.py
│   ├── connectors/            # Tests de conectores (mongodb, bigquery, mysql)
│   ├── operations/             # Tests de copy, sync, delete, export, obfuscate
│   ├── obfuscation/           # Tests de engine, mappings, fixed/dynamic rules
│   ├── state/                 # Tests de StateManager
│   ├── tui/                   # Tests de screens TUI
│   └── test_logging_config.py # Tests del sistema de logging
└── integration/               # Tests que requieren DB real (skip por defecto)
```

### Fixtures importantes

- **`FakeConnector`**: Conector en memoria para tests unitarios. Soporta seed(), clear() y todas las operaciones de AbstractConnector.
- **`source_connector` / `target_connector`**: Fixtures de conectores con auto-limpieza entre tests.

### Ejecutar tests

```bash
pytest                      # Unit tests (default)
pytest -m integration       # Integración (requiere MONGO_URI_TEST=...)
pytest tests/unit/config/   # Tests específicos de un módulo
```

### Coverage

- ~153 tests unitarios cubriendo conectores, operaciones, obfuscation, config, validator, logging, TUI
- 4 tests skipped (logging con estado global)
- 2 tests deselected (integración)
