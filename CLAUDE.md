# db-tool — Guía para Claude

## Flujo de trabajo con el usuario

Todo cambio al proyecto sigue este flujo. No saltear pasos ni implementar antes de tener validación explícita.

1. **Entender el requerimiento** — el usuario describe el problema o la feature. Hacer preguntas si algo es ambiguo antes de avanzar.
2. **Revisar el código relevante** — leer los archivos afectados para tener contexto real antes de opinar.
3. **Proponer y discutir** — presentar el enfoque en 2-3 oraciones con la recomendación y el tradeoff principal. Iterar hasta que el usuario valide.
4. **Crear el plan** — escribir un SDD detallado en `docs/sdd/XXX-{nombre-relevante}.md` (número correlativo). El plan debe incluir: contexto, decisiones de diseño, archivos a modificar con los cambios concretos, y sección de verificación.
5. **Esperar validación del plan** — no implementar hasta que el usuario confirme explícitamente.
6. **Implementar** — crear la rama a partir de `main` (salvo que el plan indique otra base), aplicar los cambios, correr `pytest tests/unit/` y verificar que todo pasa.
7. **Commit** — un solo commit por feature/fix con mensaje descriptivo que explique el *por qué*, no el *qué*. Siempre incluir `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`.
8. **El usuario valida y prueba** — esperar feedback antes de dar la tarea por cerrada.

### Convenciones de ramas

| Tipo | Prefijo | Ejemplo |
|------|---------|---------|
| Feature nueva | `feature/` | `feature/replace-flag-copy-operation` |
| Bug fix | `fix/` | `fix/remove-obfuscate-from-delete-screen` |
| Refactor / reorganización | `refactor/` | `refactor/config-files-relocation` |

### Convenciones de SDDs

- Numeración correlativa: ver el último archivo en `docs/sdd/` para saber el próximo número.
- Nombre en kebab-case describiendo la feature, no la implementación: `008-config-files-relocation`, no `008-mover-archivos`.
- Estructura mínima: **Contexto** → **Decisiones de diseño** → **Archivos a modificar** (con código concreto) → **Verificación**.

---

## Stack
Python 3.12 · Typer (CLI) · Textual (TUI) · Faker (ofuscación) · Pydantic v2 · pymongo · google-cloud-bigquery · mysql-connector-python · pytest

## Estructura
```
db_tool/
├── config/         modelos, loader YAML/env, reglas de protección
├── connectors/     AbstractConnector + mongodb, bigquery, mysql
├── operations/     copy, sync, delete, obfuscate, export
├── obfuscation/    engine, fixed_rules, dynamic_rules, mappings
├── state/          StateManager (~/.db-tool/state/)
├── cli/            comandos Typer
└── tui/            app Textual + 6 pantallas + widgets
tests/
├── unit/           137 tests, sin DB real, usan FakeConnector
└── integration/    marcados @pytest.mark.integration, skipped por default
docs/               documentación técnica detallada
```

## Archivos de configuración (gitignoreados)
| Archivo | Propósito | Ejemplo |
|---------|-----------|---------|
| `connections.yaml` | Perfiles de conexión | `connections.yaml.example` |
| `settings.env` | Parámetros operativos | `settings.env.example` |
| `obfuscation_rules.txt` | Reglas dinámicas de ofuscación | `obfuscation_rules.txt.example` |
| `replacement_rules.txt` | Reemplazos directos de strings | `replacement_rules.txt.example` |

## Cómo modificar cada característica

### Agregar un nuevo conector de base de datos
→ Ver guía completa en [`docs/connectors.md`](docs/connectors.md)
1. Crear `db_tool/connectors/<nombre>.py` implementando `AbstractConnector` (`connectors/base.py`)
2. Agregar el nuevo tipo en `config/models.py` → `ConnectorType`
3. Registrar en el factory `connectors/__init__.py` → `get_connector()`
4. Agregar tests en `tests/unit/connectors/test_<nombre>.py`
5. Actualizar `docs/connectors.md` con la nueva sección del conector

### Agregar una nueva operación
→ Ver referencia de operaciones en [`docs/operations.md`](docs/operations.md)
1. Crear `db_tool/operations/<nombre>.py` con función `run_<nombre>(source, target, pattern, settings, ...)`
2. Usar `ProgressEvent` para reportar progreso (canal CLI↔TUI)
3. Agregar subcomando en `cli/commands.py`
4. Agregar botón en `tui/screens/main_menu.py` y flujo en `_run_operation()`
5. Agregar tests en `tests/unit/operations/test_<nombre>.py`
6. Actualizar `docs/operations.md` con la nueva operación y sus flags

### Modificar reglas de ofuscación fijas
→ Ver [`docs/obfuscation.md`](docs/obfuscation.md) — sección "Capa 1: Reglas fijas"
- Editar `db_tool/obfuscation/fixed_rules.py` → lista `_FIXED_RULES`
- Formato: `(field_regex, value_regex_or_None, faker_type)`
- Actualizar la tabla de campos detectados en `docs/obfuscation.md`

### Agregar reglas de ofuscación dinámicas
→ Ver [`docs/obfuscation.md`](docs/obfuscation.md) — sección "Capa 2: Reglas dinámicas"
- Editar `obfuscation_rules.txt` (una regla por línea)
- Formato: `field_regex::value_regex::faker_type`
- Desde la TUI: Settings → editar ruta, luego editar el archivo

### Agregar reemplazos directos
→ Ver [`docs/obfuscation.md`](docs/obfuscation.md) — sección "Capa 3: Reemplazos directos"
- Editar `replacement_rules.txt` (una regla por línea)
- Formato: `original::reemplazo`
- Aplica a valores string y nombres de colecciones

### Cambiar parámetros operativos
- Editar `settings.env` directamente, o usar `db-tool tui` → Settings
- Variables: `BATCH_SIZE`, `THROTTLE_RPS`, `MONGO_MAX_RETRIES`, `MONGO_RETRY_BACKOFF_BASE`, `STATE_DIR`, `MAPPINGS_DIR`, `OBFUSCATION_RULES_PATH`

### Agregar/modificar conexiones
- Editar `connections.yaml` directamente, o usar `db-tool config add|edit|remove`
- Campos por perfil: `alias`, `environment` (production|stage|dev|local), `type`, `connection_string`, `blacklist` (lista de regex)

### Modificar reglas de protección
→ Ver [`docs/architecture.md`](docs/architecture.md) — sección "Reglas de protección"
- `db_tool/config/validator.py` — funciones `guard_write()`, `guard_connection_mutation()`, `requires_stage_confirmation()`
- Actualizar la tabla de reglas en `docs/architecture.md` si cambia el comportamiento

### Modificar la TUI
→ Ver [`docs/architecture.md`](docs/architecture.md) — sección "tui/"
- Pantallas en `db_tool/tui/screens/` — cada una es una `Screen` de Textual
- Widgets en `db_tool/tui/widgets/`
- Estilos CSS inline en `db_tool/tui/app.py`

### Agregar o modificar traducciones
→ Ver [`docs/architecture.md`](docs/architecture.md) — sección "Sistema i18n"
- Archivos en `db_tool/i18n/translations/` — uno por idioma (`en.json`, `es.json`)
- Todas las keys deben existir en ambos archivos
- El idioma se configura con `LANGUAGE` en `settings.env` o como variable de entorno
- Agregar un idioma nuevo: crear el JSON, agregar el código al validator en `config/models.py`

### Modificar los scripts de instalación/ejecución
→ Ver [`docs/scripts.md`](docs/scripts.md)
- Instalador: `scripts/install.sh` — checks, creación de venv, instalación de deps, setup de config
- Runner: `run.sh` — autodetecta instalación, lanza TUI o pasa args al CLI
- Actualizar `docs/scripts.md` si cambia el comportamiento de alguno de los dos

## Comandos frecuentes
```bash
# Instalar (primera vez o reinstalar)
bash scripts/install.sh

# Ejecutar
./run.sh                        # lanza TUI
./run.sh --help                 # ayuda CLI
./run.sh copy --source <alias> --target <alias> --obfuscate

# Con entorno activado
source .venv/bin/activate
db-tool tui
db-tool copy --source <alias> --target <alias> --obfuscate
db-tool sync --source <alias> --target <alias>
db-tool delete --target <alias> --pattern "mydblocal-.*" --dry-run
db-tool config list
db-tool cleanup mappings

# Tests
pytest                          # unit tests (default)
pytest -m integration           # requiere MONGO_URI_TEST=...
pytest tests/unit/obfuscation/  # módulo específico
```

## Invariantes importantes
- `production` → NUNCA se escribe, NUNCA se modifica su config. Bloqueado en `validator.py` y verificado en cada conector con `assert_write_allowed()`.
- La ofuscación nunca muta el doc original — `engine.transform()` siempre devuelve un nuevo dict.
- El `MappingStore` garantiza que el mismo valor real → mismo valor fake entre runs (persistido en `~/.db-tool/mappings/`).
- Los tests de operaciones usan `FakeConnector` (en `tests/conftest.py`), no mocks de pymongo.

## Documentación detallada
- [`docs/architecture.md`](docs/architecture.md) — arquitectura, capas, flujo de datos, ProgressEvent, almacenamiento persistente
- [`docs/operations.md`](docs/operations.md) — referencia de cada operación con todos sus flags y comportamientos
- [`docs/obfuscation.md`](docs/obfuscation.md) — sistema de ofuscación: reglas fijas, dinámicas, consistencia referencial
- [`docs/connectors.md`](docs/connectors.md) — configuración por DB, interfaz AbstractConnector, cómo agregar uno nuevo
- [`docs/scripts.md`](docs/scripts.md) — scripts de instalación (`scripts/install.sh`) y ejecución (`run.sh`)

## Regla de documentación

**Cualquier cambio al código requiere actualizar la documentación correspondiente en `docs/`.**

| Si modificás... | Actualizá... |
|----------------|--------------|
| Un conector existente o nuevo | `docs/connectors.md` |
| Una operación existente o nueva | `docs/operations.md` |
| Reglas de ofuscación (fijas o dinámicas) | `docs/obfuscation.md` |
| Arquitectura, capas, flujo, protecciones | `docs/architecture.md` |
| `scripts/install.sh` o `run.sh` | `docs/scripts.md` |
| Getting started o instalación | `README.md` |
| Cómo modificar el proyecto | `CLAUDE.md` |
| Traducciones (strings UI/CLI) | `db_tool/i18n/translations/` |
