# db-tool

Toolkit de línea de comandos para copiar, sincronizar y ofuscar datos entre bases de datos. Pensado para que desarrolladores tengan datos de prueba realistas en entornos no productivos, sin exponer información sensible de producción.

## Qué hace

- **Copia** colecciones/tablas entre bases de datos (MongoDB, CosmosDB, BigQuery, MySQL)
- **Ofusca** datos sensibles en memoria antes de escribir en el destino — emails, nombres, teléfonos, documentos de identidad, y cualquier campo que configures
- **Sincroniza** incrementalmente (solo lo nuevo o modificado desde la última vez)
- **Exporta** a JSONL para inspección o carga en otras herramientas
- **Protege** conexiones productivas: bloquea escrituras y pide confirmación antes de cualquier operación sensible

Tiene interfaz de línea de comandos (`db-tool <comando>`) y TUI interactiva (`db-tool tui`).

## Instalación

Requiere Python 3.12+. El script de instalación gestiona el resto automáticamente.

```bash
git clone <repo>
cd db-tool
bash scripts/install.sh
```

`install.sh` se encarga de:
- Verificar Python 3.12+
- Instalar [uv](https://docs.astral.sh/uv/) si no está presente
- Crear el entorno virtual `.venv`
- Instalar todas las dependencias del proyecto
- Crear `config/connections.yaml`, `config/settings.env`, `config/obfuscation_rules.txt` y `config/replacement_rules.txt` desde sus ejemplos si no existen
- Crear los directorios `~/.db-tool/state/` y `~/.db-tool/mappings/`

## Configuración inicial

Editar `config/connections.yaml` con tus bases de datos (se crea automáticamente al instalar):

```yaml
- alias: prod-conversational
  environment: production          # production | stage | dev | local
  type: mongodb                    # mongodb | bigquery | mysql
  connection_string: "mongodb://user:pass@prod.cosmos.azure.com:10255/?ssl=true"
  blacklist:
    - "^tmp_.*"                    # regex de colecciones a ignorar

- alias: local-conversational
  environment: local
  type: mongodb
  connection_string: "mongodb://localhost:27017/conversational"
  blacklist: []
```

> `config/connections.yaml` está en `.gitignore` — nunca se sube al repositorio.

Los parámetros operativos opcionales se configuran en `config/settings.env`:

```env
BATCH_SIZE=1000          # documentos por batch
THROTTLE_RPS=0           # 0 = sin límite; útil para CosmosDB con RU limitados
MONGO_MAX_RETRIES=5      # reintentos ante error de RU exhaustion
MONGO_RETRY_BACKOFF_BASE=2.0
```

Las reglas de ofuscación adicionales van en `config/obfuscation_rules.txt`. Formato: `field_regex::value_regex::faker_type` — ver [docs/obfuscation.md](docs/obfuscation.md).

## Uso

### TUI (recomendado)

```bash
./run.sh          # lanza la TUI directamente
```

`run.sh` detecta si la instalación fue completada y ejecuta `scripts/install.sh` automáticamente si es necesario. También acepta cualquier comando CLI:

```bash
./run.sh --help
./run.sh copy --source prod-conversational --target local-conversational --obfuscate
```

O con el entorno activado:

```bash
source .venv/bin/activate
db-tool tui
```

Navegar con el mouse o teclado. El flujo es: seleccionar operación → seleccionar conexiones → configurar opciones → ejecutar.

**Panel de Logs:** Presiona `Ctrl+L` en cualquier momento para ver los logs de la operación en curso. Los logs se almacenan en `/tmp/db-tool.log`.

### CLI

**Copiar producción a local con ofuscación:**
```bash
db-tool copy --source prod-conversational --target local-conversational \
  --pattern "mydblocal-.*" --obfuscate
```

**Sincronizar solo lo nuevo:**
```bash
db-tool sync --source prod-conversational --target local-conversational \
  --pattern "mydblocal-.*" --obfuscate
```

**Preview de qué se borraría:**
```bash
db-tool delete --target local-conversational --pattern "foo-.*" --dry-run
```

**Modo debug:** Agrega `--debug` para ver logs detallados en stderr:
```bash
db-tool tui --debug
db-tool copy --source prod-conversational --target local-conversational --debug
```

**Borrar y recargar desde cero:**
```bash
db-tool delete --target local-conversational --pattern "foo-.*"
db-tool copy --source prod-conversational --target local-conversational \
  --pattern "foo-.*" --obfuscate
```

**Exportar a JSONL:**
```bash
db-tool export --source local-conversational --pattern "mydblocal-users" \
  --output ./exports
```

**Ver conexiones configuradas:**
```bash
db-tool config list
```

**Limpiar cache de ofuscación:**
```bash
db-tool cleanup mappings
db-tool cleanup state
```

## Tests

```bash
# Unit tests (sin DB real, rápidos)
pytest

# Integration tests (requieren MongoDB local)
MONGO_URI_TEST=mongodb://localhost:27017/test pytest -m integration
```

## Documentación

| Documento | Contenido |
|-----------|-----------|
| [docs/architecture.md](docs/architecture.md) | Arquitectura, capas, flujo de datos |
| [docs/operations.md](docs/operations.md) | Referencia detallada de cada operación |
| [docs/obfuscation.md](docs/obfuscation.md) | Sistema de ofuscación, reglas, consistencia referencial |
| [docs/connectors.md](docs/connectors.md) | Conectores, configuración, cómo agregar uno nuevo |
| [docs/scripts.md](docs/scripts.md) | Scripts de instalación y ejecución |
| [CLAUDE.md](CLAUDE.md) | Guía para modificar y extender el proyecto |
