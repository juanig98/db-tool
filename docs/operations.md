# Referencia de Operaciones

Todas las operaciones aceptan un `pattern` (regex) para seleccionar colecciones/tablas. Las colecciones en la `blacklist` del perfil de conexión siempre son ignoradas, independientemente del patrón.

---

## copy

Copia colecciones de un origen a un destino en batches. Usa upsert por `_id` — es idempotente y seguro de reintentar.

```bash
db-tool copy --source <alias> --target <alias> [opciones]
```

| Flag | Default | Descripción |
|------|---------|-------------|
| `--pattern` | `.*` | Regex para filtrar colecciones |
| `--obfuscate` | false | Aplica ofuscación en memoria antes de escribir |
| `--data-only` | false | Omite la copia de índices |
| `--dry-run` | false | Muestra qué haría sin ejecutar |
| `--resume` | false | Retoma desde el último checkpoint |
| `--max-docs` | 0 (todos) | Límite de documentos por colección |

**Comportamiento con producción como origen**: si `--obfuscate` no está activo, solicita confirmación explícita antes de copiar datos sensibles.

**Checkpointing**: el progreso se guarda en `~/.db-tool/state/` por batch. Si la operación se interrumpe, `--resume` la retoma desde donde quedó sin re-procesar batches ya completados.

---

## sync

Sincronización delta: solo copia documentos que no existen en el destino o cuyo `updatedAt` en el origen es más reciente que en el destino.

```bash
db-tool sync --source <alias> --target <alias> [--pattern <regex>] [--obfuscate]
```

**Criterio de sincronización por documento**:
- Documento no existe en destino → se copia
- `updatedAt` del origen > `updatedAt` del destino → se copia
- Cualquiera de los dos no tiene `updatedAt` → se copia (safe default)
- `updatedAt` igual o destino más nuevo → se omite

**Diferencia con copy**: sync no resetea el destino. Es incremental. No copia índices.

---

## delete

Elimina colecciones que coincidan con el patrón en el destino.

```bash
db-tool delete --target <alias> --pattern <regex> [--dry-run]
```

`--dry-run` lista las colecciones que serían eliminadas sin borrar nada. Siempre bloqueado en producción; requiere confirmación en stage.

---

## obfuscate

Aplica ofuscación in-place sobre documentos existentes en el destino. Solo funciona en entornos no productivos.

```bash
db-tool obfuscate --target <alias> [--pattern <regex>] [--dry-run]
```

Lee cada documento, lo pasa por el `ObfuscationEngine`, y hace upsert del resultado. La consistencia referencial se mantiene: si el mismo email ya fue ofuscado antes (en cualquier operación previa), se mapea al mismo valor fake.

---

## export

Exporta colecciones a archivos JSONL en un directorio local.

```bash
db-tool export --source <alias> --pattern <regex> --output <directorio> [--obfuscate]
```

Genera un archivo `<directorio>/<colección>.jsonl` por cada colección coincidente. Los tipos complejos (ObjectId, datetime) se serializan a string. Con `--obfuscate`, los datos son ofuscados antes de escribirse al archivo.

---

## config

Gestiona los perfiles de conexión en `connections.yaml`.

```bash
db-tool config list              # lista todos los perfiles
db-tool config add               # agrega un perfil (interactivo)
db-tool config remove <alias>    # elimina un perfil (bloqueado en producción)
```

---

## cleanup

Elimina archivos persistentes de estado y mapeos.

```bash
db-tool cleanup mappings   # borra ~/.db-tool/mappings/ (reset consistencia referencial)
db-tool cleanup state      # borra ~/.db-tool/state/ (reset checkpoints de operaciones)
```

---

## Flujo recomendado: prod → local

```bash
# 1. Limpiar destino local
db-tool delete --target local-db --pattern "mydblocal-.*" --dry-run  # preview
db-tool delete --target local-db --pattern "mydblocal-.*"

# 2. Copiar con ofuscación
db-tool copy --source prod-db --target local-db --pattern "mydblocal-.*" --obfuscate

# 3. Verificar
db-tool export --source local-db --pattern "mydblocal-users" --output /tmp/check --obfuscate
```
