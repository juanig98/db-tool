# Sistema de Ofuscación

db-tool reemplaza datos sensibles con datos falsos pero plausibles usando la librería [Faker](https://faker.readthedocs.io/). La ofuscación es **recursiva** (aplica a todos los niveles de un documento anidado) y **referencialmente consistente** (el mismo valor real siempre produce el mismo valor fake dentro y entre ejecuciones).

---

## Capas de ofuscación

### Capa 1: Reglas fijas

Definidas en `db_tool/obfuscation/fixed_rules.py`. Se aplican siempre, sin configuración adicional.

| Campos detectados | Ejemplo de match | Faker usado |
|-------------------|-----------------|-------------|
| `email`, `user_email`, `emailAddress` | Valor contiene `@` | `faker.email()` |
| `name`, `nombre`, `fullName`, `full_name` | Cualquier valor | `faker.name()` |
| `firstName`, `first_name` | Cualquier valor | `faker.first_name()` |
| `lastName`, `last_name`, `surname` | Cualquier valor | `faker.last_name()` |
| `phone`, `telefono`, `mobile`, `celular` | Valor con 5+ dígitos | `faker.phone_number()` |
| `address`, `direccion`, `domicilio` | Cualquier valor | `faker.address()` |
| `street`, `street_address` | Cualquier valor | `faker.street_address()` |
| `city`, `ciudad` | Cualquier valor | `faker.city()` |
| `zip`, `zip_code`, `postal_code` | Cualquier valor | `faker.postcode()` |
| `dni`, `nid`, `cedula`, `document_number` | Cualquier valor | `faker.numerify("########")` |
| `tax_id`, `fiscal_id`, `cuit`, `rfc`, `nif` | Cualquier valor | `faker.numerify("########")` |
| `birth_date`, `birthDate`, `fecha_nacimiento` | Cualquier valor | `faker.date_of_birth()` |

La detección de campos es **case-insensitive**. Los patrones de nombre de campo son regex con `fullmatch`.

### Capa 2: Reglas dinámicas

Definidas en `obfuscation_rules.txt`. Cada línea tiene el formato:

```
field_regex::value_regex::faker_type
```

- `field_regex`: regex aplicado sobre el **nombre** del campo (case-insensitive, fullmatch)
- `value_regex`: regex aplicado sobre el **valor** del campo. Usar `.*` para coincidir con cualquier valor
- `faker_type`: nombre de un método de `Faker` (ej: `email`, `name`, `phone_number`, `numerify`, `address`)

Ejemplos:

```
# Campos de RFC mexicano
.*rfc.*::.*::numerify

# Campos de DNI con exactamente 8 dígitos
.*dni.*::\d{8}::numerify

# Cualquier campo que parezca un número de cuenta bancaria
.*cuenta.*::\d{10,20}::numerify

# Campos de razón social
.*razon_social.*::.*::company

# Coordenadas GPS
.*lat.*::-?\d+\.\d+::latitude
.*lon.*::-?\d+\.\d+::longitude
```

Las **reglas fijas tienen precedencia** sobre las dinámicas. Si un campo coincide con ambas, se aplica la regla fija.

---

## Consistencia referencial

El mismo valor real (`juan@example.com`) siempre produce el mismo valor fake, sin importar:
- En qué colección aparece
- En cuántas ejecuciones distintas
- Con qué instancia del engine se procesa

Esto se logra mediante `MappingStore`, que persiste un archivo JSON por cada par `(valor_real, faker_type)` en `~/.db-tool/mappings/`. La clave de lookup es `sha256(faker_type + "::" + valor_real)`.

**Importante**: la limpieza de mappings (`db-tool cleanup mappings`) rompe la consistencia para futuras ejecuciones. Los datos ya copiados con ofuscación previa tendrán valores distintos en la próxima copia.

---

## Recursividad

El engine aplica las reglas a cualquier nivel de anidamiento:

```python
# Documento de entrada
{
  "_id": "123",
  "contact": {
    "email": "real@example.com",   # → ofuscado
    "phones": [
      {"mobile": "1122334455"},    # → ofuscado
      {"work": "9988776655"}       # → ofuscado
    ]
  },
  "status": "active"               # → sin cambios
}
```

Las listas de documentos anidados también son procesadas recursivamente.

---

## Valores que NO se ofuscan

- `null` / `None`
- Strings vacíos (`""`)
- Campos cuyo nombre no coincide con ninguna regla
- Campos cuyos valores no coinciden con el `value_regex` de la regla

---

## Capa 3: Reemplazos directos

Permite mapear un string literal a otro (ej: `coca-cola` → `koke-soda`). Aplica a **valores escalares string** dentro de los documentos y a **nombres de colecciones/tablas**.

### Propósito

Usado para ofuscar identificadores de tenants, nombres de clientes, o cualquier valor queidentifique negocio específico que se quiere reemplazar por un替代.

### Formato del archivo

El archivo `replacement_rules.txt` contiene una regla por línea:

```
original::reemplazo
```

- Líneas vacías y comentarios (`#`) son ignorados
- El matching es por **substring** (aplica `str.replace` sobre el valor completo)

Ejemplos:

```
# Reemplazos de nombres de empresas
coca-cola::koke-soda
acme-corp::widget-inc

# Prefijos de collections
old-prefix-::new-prefix-
```

### Prioridad sobre reglas PII

Los reemplazos directos tienen **prioridad máxima**. Si un valor hace match con un reemplazo, las reglas PII (Capas 1 y 2) no se aplican sobre él. Esto permite que un valor como `coca-cola@email.com` se transforme directamente a `koke-soda@email.com` sin pasar por la regla de email de Faker.

### Aplicación a nombres de colecciones

El engine proporciona `transform_collection_name(name: str) -> str` que aplica los replacements al nombre de la colección:

- **Copy**: la colección destino se crea con el nombre transformado. Si ya existe, se actualiza (upsert).
- **Obfuscate in-place**: si el nombre cambia, se escribe a la nueva colección y luego se elimina la original. Error si la colección destino ya existe.

### Configuración

El archivo se define en `Settings.replacements_path` (default: `./replacement_rules.txt`). Es análogo a `obfuscation_rules_path`.

### Uso independiente con `--replace`

Los reemplazos directos pueden activarse **sin ofuscación PII** usando el flag `--replace` en la operación `copy`:

```bash
db-tool copy --source <alias> --target <alias> --replace
```

En este modo el engine se construye con `replace_only=True`: no carga las reglas fijas ni dinámicas, solo `replacement_rules.txt`. Útil para renombrar tenants o dominios sin alterar campos de datos sensibles con Faker.

| Flags activos | Comportamiento |
|---|---|
| ninguno | copia sin transformaciones |
| `--replace` | solo reemplazos directos |
| `--obfuscate` | PII rules + reemplazos directos |
| `--replace --obfuscate` | equivalente a solo `--obfuscate` |

---

## Modificar el sistema de ofuscación

### Agregar una regla fija permanente
Editar `db_tool/obfuscation/fixed_rules.py`, agregar una tupla a `_FIXED_RULES`:
```python
(r".*numero_cliente.*", None, "numerify"),
```

### Agregar una regla dinámica sin reiniciar
Editar `obfuscation_rules.txt` o usar la pantalla de Settings en la TUI para cambiar la ruta del archivo. El engine recarga las reglas dinámicas en cada instanciación.

### Cambiar el locale de Faker
En `ObfuscationEngine.__init__()`, el parámetro `locale` determina el idioma de los datos generados. Default: `es_ES` (español de España). Cambiar a `es_MX`, `en_US`, etc., según necesidad.

### Agregar un nuevo `faker_type`
Si el tipo que necesitás no existe directamente en Faker, agregar un caso en `engine._get_faker_fn()`:
```python
if faker_type == "mi_tipo_custom":
    return lambda: mi_logica_custom()
```
