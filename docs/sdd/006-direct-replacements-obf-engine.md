# SDD-006: Reemplazos directos en el motor de ofuscación

## Contexto
El motor de ofuscación actual trabaja con reglas PII (fijas y dinámicas) que detectan campos por nombre/valor y los reemplazan con datos fake via Faker. Se necesita una tercera capa: **reemplazos directos definidos por el usuario**, donde se mapea un string literal a otro (ej: `coca-cola` → `koke-soda`). Esto aplica a valores de documentos (por substring) y a nombres de collections/tablas. Los reemplazos tienen prioridad sobre las reglas PII: si un valor hace match con un reemplazo, no se aplican reglas PII sobre él.

### Decisiones de diseño confirmadas
- **Matching**: substring (aplica `str.replace` sobre el valor completo)
- **Configuración**: nuevo archivo `replacement_rules.txt` con formato `original::reemplazo`
- **In-place rename**: obfuscar contenido + renombrar collection (escribir a nueva, borrar vieja); error si ya existe
- **Prioridad**: reemplazos tienen prioridad, skip de reglas PII si hubo match

---

## Archivos a crear

### `db_tool/obfuscation/replacement_rules.py`
```python
@dataclass(frozen=True)
class ReplacementRule:
    source: str
    target: str

def load_replacement_rules(path: Path) -> list[ReplacementRule]:
    # formato: original::reemplazo (líneas vacías y # ignoradas)
```

### `replacement_rules.txt.example`
```
# Reemplazos directos: original::reemplazo
# coca-cola::koke-soda
# acme-corp::widget-inc
```

### `tests/unit/obfuscation/test_replacement_rules.py`
Tests unitarios para: carga del archivo, formato inválido, integración con engine (substring, prioridad sobre PII, collection name).

---

## Archivos a modificar

### 1. `db_tool/config/models.py`
Agregar a `Settings`:
```python
replacements_path: Path = Path("./replacement_rules.txt")
```

### 2. `db_tool/obfuscation/engine.py`
**`__init__`**: cargar `ReplacementRule` list si `settings.replacements_path.exists()`. `ObfuscationEngine` ya recibe `settings: Settings` en su constructor (mismo patrón que `obfuscation_rules_path`), por lo que no requiere cambios en la firma.

**Nuevo método** `transform_collection_name(name: str) -> str`:
```python
def transform_collection_name(self, name: str) -> str:
    result = name
    for rule in self._replacement_rules:
        result = result.replace(rule.source, rule.target)
    return result
```

**`_transform_value`**: antes de buscar reglas PII, aplicar replacements sobre strings. Si hubo match (resultado != original), retornar directamente sin pasar por PII rules. Los replacements aplican **solo a valores escalares string**, no a keys del dict (los field names son esquema fijo, no datos de tenant). Strings vacíos no se tocan (el substring replace sobre `""` es siempre no-op, consistente con la guarda `value != ""` de las reglas PII):
```python
if isinstance(value, str) and value and self._replacement_rules:
    replaced = self._apply_replacements(value)
    if replaced != value:
        return replaced
# ... lógica PII existente
```

**Nuevo método privado** `_apply_replacements(value: str) -> str`:
```python
def _apply_replacements(self, value: str) -> str:
    result = value
    for rule in self._replacement_rules:
        result = result.replace(rule.source, rule.target)
    return result
```

### 3. `db_tool/connectors/base.py`
Extender firma de `copy_indexes` para soportar target collection name diferente:
```python
@abstractmethod
def copy_indexes(self, source: "AbstractConnector", collection: str, target_collection: str | None = None) -> int:
    ...
```
(Si `target_collection` es None, usa `collection` como antes — backward compatible.)

Actualizar las 3 implementaciones (`mongodb.py`, `bigquery.py`, `mysql.py`) para aceptar el nuevo parámetro.

`collection_exists(collection: str) -> bool` ya es `@abstractmethod` en `base.py:51` e implementado en los 3 conectores — se usa directamente sin cambios.

### 4. `db_tool/operations/copy.py`
En `run_copy`, al iterar collections, calcular el nombre de destino:
```python
target_collection = (
    obfuscation_engine.transform_collection_name(collection)
    if obfuscation_engine else collection
)
```
Pasar `target_collection` a `_copy_collection`. Dentro de `_copy_collection`:
- `target.upsert_batch(target_collection, batch)` en vez de `collection`
- `target.copy_indexes(source, collection, target_collection)` al final

**No se verifica si `target_collection` ya existe**: `copy` es idempotente por diseño (usa upsert), por lo que si la collection destino ya existe los documentos se actualizan. Esto es diferente al in-place rename donde la collection destino nueva no debería existir.

El `ProgressEvent` y `StateManager` siguen usando el nombre original (`collection`) para tracking.

### 5. `db_tool/operations/obfuscate.py`
En `run_obfuscate`, calcular target collection name:
```python
target_collection = obfuscation_engine.transform_collection_name(collection)
```

Si hay rename (`target_collection != collection`):
- Verificar que `target_collection` no exista: `target.collection_exists(target_collection)` → error si existe
- En `_obfuscate_collection`: escribir a `target_collection`
- Después de completar la collection, si no `dry_run`: `target.delete_collection(collection)`

**TUI**: `ProgressEvent.collection` reporta el nombre original de la collection durante el procesamiento (no rompe la pantalla de progreso). El listado de collections en la TUI se refresca desde la DB al terminar la operación, mostrando el nuevo nombre. No se requieren cambios en pantallas o widgets de la TUI.

### 6. `docs/obfuscation.md`
Agregar nueva sección **"Capa 3: Reemplazos directos"** documentando:
- Propósito (tenant names, client identifiers)
- Formato del archivo
- Comportamiento de prioridad sobre reglas PII
- Aplicación a collection names
- Comportamiento en copy vs obfuscate in-place

### 8. `CLAUDE.md`
Agregar entrada en la tabla de modificaciones:
```
### Agregar reemplazos directos
→ Editar `replacement_rules.txt` (una regla por línea)
→ Formato: `original::reemplazo`
```

---

## Incongruencias / puntos de mejora detectados

1. **Los reemplazos no usan `MappingStore`**: No es necesario — son deterministas (misma entrada siempre produce misma salida), a diferencia de Faker. Consistencia referencial garantizada por definición.

2. **`copy_indexes` no soporta target name diferente**: La firma actual es `copy_indexes(source, collection)`, asumiendo que source y target tienen el mismo nombre. Con renombrado esto falla silenciosamente. Se extiende la firma.

3. **Rename en in-place no es atómico**: Se usa write-then-delete (en vez de `renameCollection` nativo de MongoDB). Durante la operación existe una ventana donde ambas collections coexisten. Aceptable dado que solo aplica a entornos no-producción.

4. **El `obfuscation_rules.txt.example` no menciona el nuevo archivo**: Agregar referencia en el ejemplo para que los usuarios descubran la feature.

5. **Los replacements no aplican a keys de documentos**: Solo se transforman valores escalares string. Los field names son esquema fijo y no deben ser alterados.

---

## Verificación

```bash
# 1. Tests unitarios
pytest tests/unit/obfuscation/test_replacement_rules.py
pytest tests/unit/obfuscation/test_engine.py  # tests de integración con replacements

# 2. Smoke test manual (dry-run, sin DB real)
echo "coca-cola::koke-soda" > replacement_rules.txt
./run.sh copy --source local-dev --target local-stage --obfuscate --dry-run

# 3. Verificar collection rename en copy
./run.sh copy --source local-dev --target local-stage --obfuscate --pattern "coca-cola.*"
# → Debe crear "koke-soda-*" en target, no "coca-cola-*"

# 4. Verificar in-place rename
./run.sh obfuscate --target local-stage --pattern "coca-cola.*"
# → "coca-cola-orders" debe desaparecer y aparecer "koke-soda-orders"
# → Error si "koke-soda-orders" ya existe

# 5. Suite completa de unit tests
pytest tests/unit/
```
