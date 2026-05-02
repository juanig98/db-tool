# Conectores de Base de Datos

Todos los conectores implementan `AbstractConnector` (`db_tool/connectors/base.py`) y pueden actuar como origen o destino en cualquier operación.

---

## Interfaz: AbstractConnector

```python
class AbstractConnector(ABC):
    def connect(self) -> None
    def disconnect(self) -> None
    def list_collections(self) -> list[str]
    def estimated_count(self, collection: str) -> int
    def iter_documents(self, collection: str, batch_size: int) -> Iterator[list[dict]]
    def upsert_batch(self, collection: str, docs: list[dict]) -> tuple[int, int]  # (upserted, modified)
    def delete_collection(self, collection: str) -> None
    def copy_indexes(self, source: AbstractConnector, collection: str) -> int
    def collection_exists(self, collection: str) -> bool
    def get_document(self, collection: str, doc_id: Any) -> dict | None
    def assert_write_allowed(self) -> None  # lanza ProductionWriteError si es producción
```

Los conectores son context managers (`with get_connector(...) as conn:`).

---

## MongoDB / CosmosDB

**Tipo en config**: `mongodb`  
**URI format**: `mongodb://user:pass@host:port/database` o URI de CosmosDB completa

```yaml
- alias: prod-conversational
  environment: production
  type: mongodb
  connection_string: "mongodb://user:pass@host.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb"
```

### Características específicas
- **Retry automático en CosmosDB**: detecta error code `16500` (RU exhaustion) y reintenta con backoff exponencial. Configurable con `MONGO_MAX_RETRIES` y `MONGO_RETRY_BACKOFF_BASE`.
- **Throttling**: si `THROTTLE_RPS > 0`, introduce un `sleep(1/throttle_rps)` entre batches de lectura para respetar el límite de RU/s.
- **Indexes**: `copy_indexes()` replica todos los índices no-`_id` del origen al destino, preservando opciones (unique, sparse, TTL, etc.).
- **Base de datos**: se extrae del path de la URI (`/database`). Si no hay path, usa `"db"` como default.

### Ajustar comportamiento CosmosDB
En `settings.env`:
```
MONGO_MAX_RETRIES=5          # intentos ante error 16500
MONGO_RETRY_BACKOFF_BASE=2.0 # backoff = base^intento (segundos)
THROTTLE_RPS=10              # máx 10 requests/seg en lecturas
```

---

## BigQuery

**Tipo en config**: `bigquery`  
**URI format**: `bigquery://project-id/dataset`

```yaml
- alias: prod-analytics
  environment: production
  type: bigquery
  connection_string: "bigquery://my-gcp-project/analytics_dataset"
```

### Autenticación
Usa Application Default Credentials (ADC). Antes de usar el conector:
```bash
gcloud auth application-default login
```
O configurar la variable de entorno `GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json`.

### Características específicas
- **Lectura**: usa `SELECT *` con paginación por `page_size=batch_size`.
- **Escritura**: usa `insert_rows_json` (streaming inserts). Para grandes volúmenes considerar cambiar a load jobs en `bigquery.py`.
- **Indexes**: `copy_indexes()` no hace nada — BigQuery no tiene índices tradicionales.
- **`_id`**: si la tabla no tiene columna `_id`, se asigna uno basado en `id` o hash del documento.

### Manejo cross-type (BigQuery ↔ MongoDB/MySQL)
Los campos que en BigQuery son structs/arrays se reciben como dicts/lists de Python. Al escribir a MySQL o exportar, se serializan como JSON string (Option A). Al leer de MySQL campos JSON, se deserializan automáticamente.

---

## MySQL

**Tipo en config**: `mysql`  
**URI format**: `mysql://user:pass@host:port/database`

```yaml
- alias: local-mysql
  environment: local
  type: mysql
  connection_string: "mysql://root:password@localhost:3306/dev_db"
```

### Características específicas
- **Creación automática de tablas**: en el primer `upsert_batch()`, si la tabla no existe, se crea con las columnas del primer documento. `_id` es `VARCHAR(255) PRIMARY KEY`, el resto son `LONGTEXT`.
- **Upsert**: usa `INSERT ... ON DUPLICATE KEY UPDATE`. Rowcount 1 = insert, 2 = update.
- **Serialización**: dicts y listas se guardan como JSON string. En lectura, se intenta parsear strings que empiezan con `{` o `[`.
- **Indexes**: `copy_indexes()` no aplica — el esquema es inferido en el primer upsert.

---

## Agregar un nuevo conector

1. Crear `db_tool/connectors/<nombre>.py`:
```python
from db_tool.connectors.base import AbstractConnector

class NuevoConnector(AbstractConnector):
    def connect(self): ...
    def disconnect(self): ...
    # implementar todos los métodos abstractos
```

2. Agregar el tipo en `db_tool/config/models.py`:
```python
class ConnectorType(str, Enum):
    NUEVO = "nuevo"
```

3. Registrar en `db_tool/connectors/__init__.py`:
```python
if profile.type == ConnectorType.NUEVO:
    from db_tool.connectors.nuevo import NuevoConnector
    return NuevoConnector(profile, settings)
```

4. Crear `tests/unit/connectors/test_nuevo.py` con tests usando mocks del cliente nativo.

---

## Compatibilidad cross-type

| Origen → Destino | Documentos anidados | Índices |
|-----------------|--------------------|---------| 
| MongoDB → MongoDB | Nativo | Copiados |
| MongoDB → MySQL | JSON serializado | No aplica |
| MongoDB → BigQuery | JSON serializado | No aplica |
| BigQuery → MongoDB | Deserializado | No aplica |
| BigQuery → MySQL | JSON serializado | No aplica |
| MySQL → MongoDB | Deserializado | No aplica |
