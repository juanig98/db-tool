# SDD 009 — Bloqueo heurístico de escrituras en entornos productivos

## Contexto

Actualmente `check_connection_string_signals()` detecta señales de producción en la connection string y muestra un aviso al iniciar la TUI. Ese aviso es ignorable: el usuario puede seleccionar igual esa conexión como target y ejecutar operaciones destructivas.

El objetivo es convertir ese aviso en un bloqueo real en la pantalla `ConnectionSelectScreen`, e introducir un flag `allow_prod_writes` en el perfil de conexión que permita bypassear el bloqueo de forma intencional y explícita.

---

## Decisiones de diseño

### 1. Dónde bloquear
El bloqueo ocurre en `ConnectionSelectScreen.on_button_pressed()`, al confirmar la selección. Si el target seleccionado tiene señales de producción y no tiene `allow_prod_writes: true`, se muestra un error y no se avanza.

No se bloquea en `main_menu.py` ni en `operation_config.py` porque la lógica de selección ya vive en `ConnectionSelectScreen`.

### 2. Qué conexiones se bloquean
Se bloquea cuando `check_connection_string_signals()` retorna al menos un warning de severidad `high` para el target seleccionado. Severidad `high` = señales de producción en una conexión no declarada como `production`.

Las conexiones declaradas como `environment: production` ya están bloqueadas por `guard_write()` en el nivel de operación — este SDD no cambia eso.

### 3. El flag `allow_prod_writes`
- Campo opcional en `ConnectionProfile`, default `False`.
- Si es `True`, bypasea el bloqueo heurístico en `ConnectionSelectScreen`.
- **No se expone en la TUI de gestión de conexiones** (`connection_form.py`). El usuario debe editarlo manualmente en `connections.yaml`.
- La idea es que sea un "hack consciente": el usuario sabe lo que hace.

### 4. Lookup eficiente en ConnectionSelectScreen
`ConnectionSelectScreen` recibe la lista de perfiles (`list[ConnectionProfile]`). Se construye un dict `alias → profile` al inicializar para hacer el lookup en O(1) al confirmar.

Los warnings heurísticos se calculan on-demand al confirmar (no al inicializar la pantalla), llamando a `check_connection_string_signals([target_profile])`.

---

## Archivos a modificar

### `db_tool/config/models.py`
Agregar `allow_prod_writes` a `ConnectionProfile`:

```python
class ConnectionProfile(BaseModel):
    alias: str
    environment: Environment
    type: ConnectorType
    connection_string: str
    database_name: str
    blacklist: list[str] = []
    allow_prod_writes: bool = False  # bypass heuristic production block
```

### `db_tool/tui/screens/connection_select.py`
1. Importar `check_connection_string_signals` y la i18n key nueva.
2. Construir `_profile_map` en `__init__`.
3. En `on_button_pressed`, tras resolver `target_val`, obtener el perfil y verificar señales:

```python
from db_tool.config.validator import check_connection_string_signals

# en __init__:
self._profile_map: dict[str, ConnectionProfile] = {p.alias: p for p in profiles}

# en on_button_pressed, antes del dismiss:
if self._needs_target and target_val:
    target_profile = self._profile_map[target_val]
    if not target_profile.allow_prod_writes:
        warnings = check_connection_string_signals([target_profile])
        high = [w for w in warnings if w.severity == "high"]
        if high:
            self.notify(
                t("tui.connection_select.error.prod_heuristic_block",
                  alias=target_val, keyword=high[0].matched_keyword),
                severity="error",
            )
            return
```

### `db_tool/i18n/translations/en.json`
```json
"tui.connection_select.error.prod_heuristic_block": "Cannot use '{alias}' as target: connection string contains '{keyword}', which suggests a production environment. If this is intentional, set allow_prod_writes: true in connections.yaml."
```

### `db_tool/i18n/translations/es.json`
```json
"tui.connection_select.error.prod_heuristic_block": "No se puede usar '{alias}' como target: la cadena de conexión contiene '{keyword}', lo que sugiere un entorno productivo. Si es intencional, configurar allow_prod_writes: true en connections.yaml."
```

### `config/connections.yaml.example`
Agregar `allow_prod_writes` comentado en un perfil no-productivo de ejemplo. El flag no tiene sentido en perfiles `production` (ya bloqueados por `guard_write`); su caso de uso es un perfil dev/stage cuya connection string contiene una keyword de producción por razones legítimas (ej. un clone nombrado `prod-clone-local`).

```yaml
- alias: dev-db1
  environment: dev
  type: mongodb
  connection_string: "mongodb://localhost:27017"
  database_name: mydb
  blacklist: []
  # allow_prod_writes: true  # set to true only if this non-production connection has a prod-like hostname that triggers the heuristic block
```

---

## Tests a agregar

### `tests/unit/tui/test_connection_select_prod_block.py` (nuevo)
Usar `App` de Textual en modo headless para verificar:
1. Que al confirmar con un target que tiene señales `high` y `allow_prod_writes=False` **no** se hace dismiss (se queda en la pantalla).
2. Que con `allow_prod_writes=True` **sí** avanza.
3. Que si el target no tiene señales de producción avanza normalmente.

### `tests/unit/config/test_models.py` (existente)
Verificar que `allow_prod_writes` tiene default `False` y acepta `True`.

---

## Verificación

```bash
pytest tests/unit/
```

Smoke test manual en TUI:
1. Configurar una conexión con `environment: dev` y `connection_string` que contenga `prod`.
2. Intentar usarla como target en Copy → debe bloquear con mensaje de error.
3. Agregar `allow_prod_writes: true` al perfil → debe dejar avanzar.
