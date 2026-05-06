# SDD-010: Reglas de exclusión de ofuscación

## Contexto

El engine de ofuscación detecta campos por nombre (regex) y los transforma con Faker. Campos genéricos como `name` matchean la regla fija `^(name|nombre)$` y se ofuscan en todos los documentos, sin distinción de colección. Esto es incorrecto para campos estructurales/operativos como `{tenant}-environments.name` o `{tenant}-channels.name`, cuyo valor no es PII y debe preservarse.

La solución existente —cargar esos valores en `replacement_rules.txt` con source == target— no escala y es frágil ante nuevos valores.

## Decisiones de diseño

- **Nuevo archivo de configuración**: `config/exclusion_rules.txt`, mismo patrón que los archivos existentes (gitignoreado, plantilla en `.example`).
- **Formato**: `collection_regex::field_regex` (scoped a colecciones que matcheen) o `field_regex` (global). Regex case-insensitive, fullmatch sobre el nombre del campo.
- **Precedencia**: Las exclusiones se evalúan **después** de los reemplazos directos y **antes** de las reglas fijas/dinámicas. Los reemplazos directos siguen aplicando en campos excluidos (útil para renombrar prefijos de tenant sin ofuscar PII).
- **Contexto de colección**: `transform(doc, collection=None)` recibe el nombre de colección opcional. El argumento ya estaba disponible en los 4 call sites de operaciones.
- **Backward compatible**: `collection=None` hace que solo apliquen exclusiones globales; el comportamiento previo se preserva.

## Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `db_tool/obfuscation/exclusion_rules.py` | NUEVO: `ExclusionRule` dataclass + `load_exclusion_rules()` |
| `db_tool/config/models.py` | Agregar `exclusion_rules_path` a `Settings` |
| `db_tool/obfuscation/engine.py` | Cargar exclusiones, `transform(collection=)`, `_is_excluded()` |
| `db_tool/operations/copy.py` | Pasar `collection=collection` a `transform()` |
| `db_tool/operations/sync.py` | Ídem |
| `db_tool/operations/obfuscate.py` | Ídem |
| `db_tool/operations/export.py` | Ídem |
| `config/exclusion_rules.txt.example` | NUEVO: plantilla con comentarios |
| `.gitignore` | Agregar `config/exclusion_rules.txt` |
| `docs/obfuscation.md` | Sección "Capa 0" + entrada en "Modificar el sistema" |
| `CLAUDE.md` | Tabla de config + sección "Excluir campos" |
| `tests/unit/obfuscation/test_exclusion_rules.py` | NUEVO: 7 tests para `load_exclusion_rules` |
| `tests/unit/obfuscation/test_engine.py` | 4 tests nuevos: exclusión global, scoped, sin collection, prioridad replacements |

## Verificación

```bash
# Unit tests
pytest tests/unit/obfuscation/ -v   # 71 passed

# Uso manual
echo ".*-environments.*::name" > config/exclusion_rules.txt
./run.sh copy --source <alias> --target <alias> --obfuscate
# Verificar: docs en colecciones *-environments* conservan el campo 'name' intacto
# Verificar: docs en otras colecciones con campo 'name' sí son ofuscados
```
