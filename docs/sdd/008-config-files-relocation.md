# SDD-008: Relocación de archivos de configuración a `config/`

## Contexto

Los archivos de configuración del operador (`connections.yaml`, `settings.env`, `obfuscation_rules.txt`, `replacement_rules.txt` y sus `.example`) viven actualmente en la raíz del repositorio mezclados con `pyproject.toml`, `run.sh`, `README.md`, etc. Moverlos a un subdirectorio `config/` los agrupa semánticamente y limpia la raíz.

---

## Estructura objetivo

```
config/
├── connections.yaml           ← gitignoreado (datos reales)
├── connections.yaml.example   ← trackeado
├── settings.env               ← gitignoreado
├── settings.env.example       ← trackeado
├── obfuscation_rules.txt      ← gitignoreado
├── obfuscation_rules.txt.example ← trackeado
├── replacement_rules.txt      ← gitignoreado
└── replacement_rules.txt.example ← trackeado
```

---

## Archivos a modificar

### 1. `db_tool/config/loader.py` — `_resolve_config_path()`

Extender el walk-up para buscar primero `<dir>/config/<filename>` y luego `<dir>/<filename>` (compatibilidad retroactiva durante la transición):

```python
for directory in [current, *current.parents]:
    candidate = directory / "config" / filename
    if candidate.exists():
        return candidate
    candidate = directory / filename
    if candidate.exists():
        return candidate
```

El fallback final cambia a `current / "config" / filename` para que el error de archivo no encontrado muestre la ruta correcta.

### 2. `db_tool/config/models.py` — defaults de `Settings`

```python
obfuscation_rules_path: Path = Path("./config/obfuscation_rules.txt")
replacements_path: Path = Path("./config/replacement_rules.txt")
```

### 3. `scripts/install.sh` — bloque de archivos de configuración

Crear el directorio `config/` si no existe y ajustar todas las rutas:

```bash
mkdir -p "$ROOT_DIR/config"

if [[ ! -f "$ROOT_DIR/config/connections.yaml" ]]; then
    cp "$ROOT_DIR/config/connections.yaml.example" "$ROOT_DIR/config/connections.yaml"
    warn "Se creó config/connections.yaml desde el ejemplo. Editarlo con tus conexiones antes de usar la herramienta."
fi

if [[ ! -f "$ROOT_DIR/config/settings.env" ]]; then
    cp "$ROOT_DIR/config/settings.env.example" "$ROOT_DIR/config/settings.env"
    info "Se creó config/settings.env con valores por defecto."
fi

if [[ ! -f "$ROOT_DIR/config/obfuscation_rules.txt" ]]; then
    cp "$ROOT_DIR/config/obfuscation_rules.txt.example" "$ROOT_DIR/config/obfuscation_rules.txt"
    info "Se creó config/obfuscation_rules.txt desde el ejemplo."
fi

if [[ ! -f "$ROOT_DIR/config/replacement_rules.txt" ]]; then
    cp "$ROOT_DIR/config/replacement_rules.txt.example" "$ROOT_DIR/config/replacement_rules.txt"
    info "Se creó config/replacement_rules.txt desde el ejemplo."
fi
```

> Nota: `replacement_rules.txt` no se copiaba en el installer anterior — se agrega ahora.

### 4. `settings.env.example` — actualizar path por defecto

```
OBFUSCATION_RULES_PATH=./config/obfuscation_rules.txt
```

> `REPLACEMENTS_PATH` no estaba en el `.example`; no hace falta agregar (el default del modelo ya apunta al lugar correcto).

### 5. `.gitignore` — actualizar entradas

Reemplazar:
```
connections.yaml
settings.env
obfuscation_rules.txt
replacement_rules.txt
```

Por:
```
config/connections.yaml
config/settings.env
config/obfuscation_rules.txt
config/replacement_rules.txt
```

### 6. Mover archivos físicos

```bash
mkdir -p config/
git mv connections.yaml.example       config/connections.yaml.example
git mv settings.env.example           config/settings.env.example
git mv obfuscation_rules.txt.example  config/obfuscation_rules.txt.example
git mv replacement_rules.txt.example  config/replacement_rules.txt.example
# Los archivos reales (gitignoreados) se mueven manualmente:
mv connections.yaml      config/
mv settings.env          config/
mv obfuscation_rules.txt config/
mv replacement_rules.txt config/
```

---

## Compatibilidad retroactiva

El walk-up modificado en `loader.py` sigue encontrando archivos en la raíz (paso 2 del loop). Esto significa que instalaciones existentes con archivos en la raíz siguen funcionando sin migración forzada. El installer sí apunta a `config/` desde esta versión, por lo que las instalaciones nuevas usan la estructura nueva.

---

## Documentación a actualizar

| Archivo | Qué cambiar |
|---|---|
| `README.md` | Rutas en "Configuración rápida", tabla de archivos de config |
| `CLAUDE.md` | Tabla de archivos de configuración, sección "Cambiar parámetros", "Agregar/modificar conexiones" |
| `docs/scripts.md` | Rutas en la descripción del installer |
| `docs/architecture.md` | Referencias a rutas de config files |

---

## Tests

Los tests usan `tmp_path / "connections.yaml"` y `tmp_path / "settings.env"` pasados explícitamente como parámetros a `ConfigLoader`, por lo que **no requieren cambios** — no dependen del walk-up.

---

## Verificación

```bash
# 1. Mover archivos y reinstalar
bash scripts/install.sh

# 2. Verificar que el loader encuentra los archivos en config/
./run.sh config list

# 3. Verificar compatibilidad retroactiva (archivo en raíz)
cp config/connections.yaml ./connections.yaml
./run.sh config list   # debe seguir funcionando

# 4. Suite de unit tests
pytest tests/unit/
```
