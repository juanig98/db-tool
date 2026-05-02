# Plan: Connection String Guardian

## Context

Los perfiles en `connections.yaml` tienen un campo `environment` (production/stage/dev/local) que se declara manualmente. Si alguien configura `environment: dev` pero apunta la `connection_string` a un host de producción (ej. `mongodb://prod-db.internal/app`), el guard de escritura actual NO lo detecta — solo bloquea si `environment == production`. Este guardian hace un chequeo estático (sin conexión) al arranque para detectar esa incoherencia y avisarle al usuario antes de que opere.

---

## Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `db_tool/config/validator.py` | Agregar dataclass `ConnectionStringWarning` + función `check_connection_string_signals()` |
| `db_tool/config/loader.py` | Cachear warnings en `load_profiles()`, exponer `get_connection_warnings()` |
| `db_tool/tui/app.py` | Mostrar warnings como notificaciones en `on_mount()` |
| `db_tool/cli/commands.py` | Emitir warnings a stderr en `_get_loader()` (primera carga) |
| `db_tool/i18n/translations/en.json` | Agregar key `validator.warning.connection_string_mismatch` |
| `db_tool/i18n/translations/es.json` | Ídem en español |
| `tests/unit/config/test_validator.py` | Agregar tests para la nueva función |

---

## Step 1 — `validator.py`: señales y función de chequeo

Agregar después de las excepciones existentes (línea 13):

```python
from dataclasses import dataclass
from typing import Literal

ENVIRONMENT_SIGNALS: dict[Environment, list[str]] = {
    Environment.PRODUCTION: ["prod", "prd", "live", "master"],
    Environment.STAGE:      ["stage", "staging", "stg", "preprod", "pre-prod"],
    Environment.DEV:        ["dev", "develop", "development"],
    Environment.LOCAL:      ["local", "localhost", "127.0.0.1", "::1"],
}

@dataclass
class ConnectionStringWarning:
    alias: str
    declared_env: Environment
    detected_env: Environment
    matched_keyword: str
    severity: Literal["high", "medium"]

def check_connection_string_signals(
    profiles: list[ConnectionProfile],
) -> list[ConnectionStringWarning]:
    warnings: list[ConnectionStringWarning] = []
    for profile in profiles:
        cs_lower = profile.connection_string.lower()
        for env, keywords in ENVIRONMENT_SIGNALS.items():
            if env == profile.environment:
                continue
            for keyword in keywords:
                if keyword in cs_lower:
                    severity: Literal["high", "medium"] = (
                        "high"
                        if env == Environment.PRODUCTION
                        and profile.environment != Environment.PRODUCTION
                        else "medium"
                    )
                    warnings.append(ConnectionStringWarning(
                        alias=profile.alias,
                        declared_env=profile.environment,
                        detected_env=env,
                        matched_keyword=keyword,
                        severity=severity,
                    ))
                    break  # un warning por familia por perfil
    return warnings
```

El `import Environment` ya existe en el módulo vía `ConnectionProfile`. Agregar el import explícito: `from db_tool.config.models import ConnectionProfile, Environment`.

**Severity logic:** HIGH = el perfil no es producción pero la string señala producción (mayor riesgo: podría escribir a prod). MEDIUM = cualquier otro cruce.

---

## Step 2 — `loader.py`: cachear y exponer warnings

**2a.** Agregar `self._connection_warnings: list = []` en `ConfigLoader.__init__` (después de línea 51).

**2b.** Al final de `load_profiles()`, antes del `return profiles` (después de línea 69):

```python
        try:
            from db_tool.config.validator import check_connection_string_signals
            self._connection_warnings = check_connection_string_signals(profiles)
        except Exception:
            self._connection_warnings = []
        return profiles
```

**2c.** Nuevo método público después de `load_profiles()`:

```python
    def get_connection_warnings(self) -> list:
        return list(self._connection_warnings)
```

---

## Step 3 — `tui/app.py`: notificaciones en `on_mount()`

Agregar entre `load_settings()` y `push_screen()` (después de línea 152):

```python
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
```

---

## Step 4 — `cli/commands.py`: stderr warnings en primera carga

Agregar función auxiliar después de `_get_loader()` y llamarla desde ahí:

```python
def _get_loader() -> ConfigLoader:
    global _loader
    if _loader is None:
        _loader = ConfigLoader()
        _warn_connection_strings(_loader)
    return _loader

def _warn_connection_strings(loader: ConfigLoader) -> None:
    try:
        loader.load_profiles()
        for w in loader.get_connection_warnings():
            from db_tool.i18n import t
            msg = t(
                "validator.warning.connection_string_mismatch",
                alias=w.alias,
                declared=w.declared_env.value,
                detected=w.detected_env.value,
                keyword=w.matched_keyword,
                severity=w.severity.upper(),
            )
            color = typer.colors.RED if w.severity == "high" else typer.colors.YELLOW
            typer.echo(typer.style(f"WARNING: {msg}", fg=color), err=True)
    except Exception:
        pass
```

`_warn_connection_strings` recibe el loader como parámetro para evitar recursión.

---

## Step 5 — i18n: agregar la key en ambos JSONs

**`en.json`** (después de los `validator.error.*` existentes):
```json
"validator.warning.connection_string_mismatch": "[{severity}] Profile '{alias}' declared as '{declared}' but connection string signals '{detected}' environment (matched: '{keyword}')."
```

**`es.json`** (ídem):
```json
"validator.warning.connection_string_mismatch": "[{severity}] El perfil '{alias}' está declarado como '{declared}' pero la cadena de conexión sugiere el entorno '{detected}' (coincidencia: '{keyword}')."
```

---

## Step 6 — Tests en `tests/unit/config/test_validator.py`

Agregar al import del archivo:
```python
from db_tool.config.validator import (
    ...,  # existentes
    ConnectionStringWarning,
    check_connection_string_signals,
)
```

Casos a cubrir:
- Sin warnings cuando env coincide con la string (ej. `production` + `prod-host`)
- Detecta `prod` en perfil `dev` → severity HIGH
- Detecta `prd` en perfil `stage` → severity HIGH
- Detecta `staging` en perfil `dev` → severity MEDIUM
- Detecta `localhost` en perfil `production` → severity MEDIUM
- Case-insensitive: `PROD` → detectado
- Solo 1 warning por familia por perfil (string con `prod` y `prd` → 1 warning)
- Lista vacía → sin warnings
- Múltiples perfiles: cada uno genera su propio warning independiente

---

## Verification

```bash
# Unit tests (no DB necesaria)
pytest tests/unit/config/test_validator.py -v

# Smoke test CLI (con connections.yaml que tenga un mismatch deliberado)
# Agregar temporalmente en connections.yaml:
# - alias: test-mismatch
#   environment: dev
#   type: mongodb
#   connection_string: mongodb://prod-db.internal/app
#   database_name: test
./run.sh config list   # debe mostrar WARNING en stderr
./run.sh tui           # debe mostrar notificación al arrancar
```
