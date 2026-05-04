# SDD-007: Flag `--replace` independiente en la operación copy

## Contexto

La operación `copy` actualmente expone `--obfuscate` para aplicar el motor de ofuscación completo (reglas PII fijas + dinámicas + reemplazos directos). Se identificó la necesidad de poder ejecutar **solo los reemplazos directos** (`replacement_rules.txt`) sin activar el scrubbing PII — útil para renombrar strings conocidos (nombres de empresa, dominios, identificadores de tenant) sin alterar campos de datos sensibles con Faker.

### Semántica confirmada

| Flag(s) activos | Comportamiento |
|---|---|
| ninguno | copia sin transformaciones |
| `--replace` | solo aplica `replacement_rules.txt` (sustituciones literales) |
| `--obfuscate` | aplica PII rules (fixed + dynamic) **y** replacements |
| `--replace --obfuscate` | equivalente a solo `--obfuscate` (replace ya está incluido) |

Los reemplazos directos son deterministas, por lo que no requieren `MappingStore`. La consistencia referencial está garantizada por definición.

---

## Archivos a modificar

### 1. `db_tool/obfuscation/engine.py`

Agregar parámetro `replace_only: bool = False` al constructor. Si es `True`, omite la carga de `FIXED_RULES` y dynamic rules — solo carga `replacement_rules`:

```python
def __init__(self, settings, locale="es_ES", seed=None, replace_only=False):
    self._faker = Faker(locale)
    if seed is not None:
        Faker.seed(seed)
    self._mapping_store = MappingStore(settings)
    self._dynamic_rules = []
    self._replacement_rules = []
    if not replace_only:
        if settings.obfuscation_rules_path.exists():
            self._dynamic_rules = load_dynamic_rules(settings.obfuscation_rules_path)
    if settings.replacements_path.exists():
        self._replacement_rules = load_replacement_rules(settings.replacements_path)
```

`_transform_value` y `_find_rule` no requieren cambios: con `_dynamic_rules = []` y sin `FIXED_RULES` cargados, el engine simplemente no encuentra reglas PII y aplica solo replacements.

> **Nota**: `FIXED_RULES` se importa en el módulo; para el modo `replace_only` hay que evitar que `_find_rule` las itere. Solución: almacenar las fixed rules en una instancia en `__init__` en lugar de accederlas desde el módulo directamente.

Cambio en `__init__`:
```python
self._fixed_rules: list[FieldRule] = [] if replace_only else list(FIXED_RULES)
```

Cambio en `_find_rule`:
```python
for rule in self._fixed_rules + self._dynamic_rules:
```

### 2. `db_tool/cli/commands.py`

En el comando `copy`, agregar flag `--replace`:

```python
replace: bool = typer.Option(False, "--replace", help=t("cli.copy.option.replace")),
```

Agregar helper:
```python
def _build_replace_engine(settings):
    from db_tool.obfuscation.engine import ObfuscationEngine
    return ObfuscationEngine(settings, replace_only=True)
```

Lógica de construcción del engine:
```python
engine = None
if obfuscate:
    engine = _build_engine(settings)          # completo
elif replace:
    engine = _build_replace_engine(settings)  # solo replacements
```

Aplicar el mismo patrón en `sync` y `export` si corresponde (scope de este SDD: solo `copy`).

### 3. `db_tool/tui/screens/operation_config.py`

Agregar campo al dataclass `OperationConfig`:
```python
replace: bool
```

Agregar checkbox para la operación `copy` (dentro del bloque condicional `if self._operation == "copy"`):
```python
yield Checkbox(t("tui.operation_config.checkbox.replace"), id="replace")
```

Leer el valor al hacer submit:
```python
replace = False
if self._operation == "copy":
    replace = self.query_one("#replace", Checkbox).value
    ...
```

Pasar al dataclass:
```python
self.dismiss(OperationConfig(
    ...
    replace=replace,
    ...
))
```

### 4. `db_tool/tui/screens/progress.py`

En el worker `_execute`, al construir el engine para `copy`:

```python
engine = None
if config.obfuscate:
    engine = ObfuscationEngine(self._settings)
elif config.replace:
    engine = ObfuscationEngine(self._settings, replace_only=True)
```

### 5. `db_tool/i18n/translations/es.json` y `en.json`

Agregar keys:
```json
"tui.operation_config.checkbox.replace": "Aplicar reemplazos directos",
"cli.copy.option.replace": "Aplicar reemplazos directos sin ofuscación PII"
```

---

## Archivos a actualizar (documentación)

| Archivo | Qué agregar |
|---|---|
| `docs/obfuscation.md` | Sección sobre uso de `--replace` como flag independiente |
| `docs/operations.md` | Flag `--replace` en la tabla de flags de `copy` |

---

## Tests a agregar

- `tests/unit/obfuscation/test_engine.py` — casos con `replace_only=True`: verificar que FIXED_RULES no se aplican, que replacements sí se aplican.
- `tests/unit/operations/test_copy.py` — caso con engine replace-only pasado como `obfuscation_engine`.

---

## Verificación

```bash
# replace sin obfuscate
./run.sh copy --source local-dev --target local-stage --replace --dry-run

# obfuscate solo (comportamiento previo sin cambios)
./run.sh copy --source local-dev --target local-stage --obfuscate --dry-run

# ambos flags (equivalente a --obfuscate)
./run.sh copy --source local-dev --target local-stage --replace --obfuscate --dry-run

# suite de tests
pytest tests/unit/
```
