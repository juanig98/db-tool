# Plan: Backup & Restore

## Context

Agregar operaciones de backup/restore que permitan:
1. **Backup**: Crear tarball con todas las colecciones + metadatos (índice, fecha, origen)
2. **Restore**: Restaurar desde un backup a cualquier conexión destino

---

## Archivos a crear

| Archivo | Descripción |
|---------|-------------|
| `db_tool/operations/backup.py` | Función `run_backup(source, output_path, settings, pattern, include_indexes, compression)` |
| `db_tool/operations/restore.py` | Función `run_restore(input_path, target, settings, skip_existing, overwrite)` |
| `db_tool/tui/screens/backup_config.py` | Screen de configuración de backup |
| `db_tool/tui/screens/restore_config.py` | Screen de configuración de restore |

## Archivos a modificar

- `db_tool/cli/commands.py` → agregar subcomandos `backup` y `restore`
- `db_tool/tui/screens/main_menu.py` → botones "Backup" y "Restore"
- `db_tool/i18n/translations/en.json` y `es.json` → traducciones

## CLI

```bash
db-tool backup --source alias --output ./backup.tar.gz --pattern ".*" --compress
db-tool restore --input ./backup.tar.gz --target alias --skip-existing
```

Flags:
- `--output, -o`: Path de salida (default: `./backup_<alias>_<timestamp>.tar.gz`)
- `--compress`: Comprimir a tar.gz (default: True)
- `--include-indexes`: Incluir índices en el backup (default: False)
- `--pattern`: Regex para filtrar colecciones (default: `.*`)
- `--input, -i`: Path del archivo de backup
- `--skip-existing`: No restaurar colecciones que ya existen (default: False)
- `--overwrite`: Eliminar y recrear colecciones existentes (default: False)

## Flujo de navegación TUI

```
MainMenuScreen
  └─[Backup]─► ConnectionSelectScreen (solo source)
                  └─[Confirm]─► BackupConfigScreen
                          └─[Start]─► run_backup() → ProgressScreen

MainMenuScreen
  └─[Restore]─► ConnectionSelectScreen (solo target)
                  └─[Confirm]─► RestoreConfigScreen (seleccionar archivo)
                          └─[Start]─► run_restore() → ProgressScreen
```

## Formato del backup

```
backup_<alias>_<timestamp>/
├── backup_manifest.json    # Metadata
├── collection1.jsonl       # Datos
├── collection2.jsonl
└── indexes/               # Solo si --include-indexes
```

**backup_manifest.json**:
```json
{
  "version": "1.0",
  "created_at": "2024-01-15T10:30:00Z",
  "source_alias": "prod-db",
  "source_type": "mongodb",
  "source_db": "proddb",
  "collections": ["users", "orders", "products"],
  "total_documents": 15000
}
```

## Consideraciones de seguridad

- **Producción bloqueada**: Restore a producción debe requerir `--force` o confirmación explícita
- **Validar backup**: Verificar que el backup es válido antes de restaurar (version, checksums)
- **Logging**: Registrar cada restore para auditoría

## Tests a crear

### `tests/unit/operations/test_backup.py`
- Test que backup crea el tarball con manifest
- Test que exclude por blacklist funciona
- Test que include_indexes copia correctamente
- Test que empty pattern exporta todo

### `tests/unit/operations/test_restore.py`
- Test que restore desde tarball funciona
- Test que skip_existing salta correctamente
- Test que overwrite borra y recrea
- Test que restore a production sin --force falla

## Verification

```bash
# CLI
db-tool backup --source local-db --output /tmp/test-backup.tar.gz --compress
ls -la /tmp/test-backup.tar.gz

db-tool restore --input /tmp/test-backup.tar.gz --target local-db-2

# TUI
./run.sh tui
# Backup → seleccionar source → configurar → ejecutar
# Restore → seleccionar target → elegir archivo → configurar → ejecutar
```