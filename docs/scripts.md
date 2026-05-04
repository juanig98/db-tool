# Scripts de instalación y ejecución

## scripts/install.sh

Instalador completo del proyecto. Verifica el entorno, instala dependencias y prepara los archivos de configuración.

```bash
bash scripts/install.sh
```

### Qué hace, en orden

1. **Verifica Python 3.12+** — aborta si la versión es menor.
2. **Instala uv** — si `uv` no está en el PATH ni en `~/.local/bin/`, lo descarga e instala automáticamente desde `astral.sh`.
3. **Crea el entorno virtual** en `.venv/` — solo si no existe.
4. **Instala dependencias** — ejecuta `uv pip install -e ".[dev]"` contra `pyproject.toml`. Incluye dependencias de producción y de desarrollo (pytest, etc.).
5. **Crea el directorio `config/`** si no existe y copia los archivos de configuración desde sus ejemplos si no existen:
   - `config/connections.yaml` ← `config/connections.yaml.example`
   - `config/settings.env` ← `config/settings.env.example`
   - `config/obfuscation_rules.txt` ← `config/obfuscation_rules.txt.example`
   - `config/replacement_rules.txt` ← `config/replacement_rules.txt.example`
6. **Crea directorios de estado** — `~/.db-tool/state/` y `~/.db-tool/mappings/`.
7. **Escribe un marker** en `.venv/.installed` con la fecha de instalación. `run.sh` usa este marker para saber si la instalación fue completada.

### Re-ejecutar el instalador

Es seguro ejecutarlo varias veces:
- No reinstala dependencias si ya están instaladas (uv es idempotente).
- No sobreescribe `config/connections.yaml`, `config/settings.env`, `config/obfuscation_rules.txt` ni `config/replacement_rules.txt` si ya existen.
- Sí actualiza el marker de instalación.

Para forzar una reinstalación limpia:

```bash
rm -rf .venv
bash scripts/install.sh
```

### Requisitos del sistema

| Requisito | Versión mínima | Notas |
|-----------|---------------|-------|
| Python | 3.12 | Verificado al inicio del script |
| curl | cualquiera | Solo necesario si uv no está instalado |
| bash | 4.0+ | El script usa `set -euo pipefail` |

---

## run.sh

Punto de entrada principal del proyecto. Lanza la TUI o ejecuta cualquier comando CLI.

```bash
./run.sh              # lanza la TUI
./run.sh --help       # muestra la ayuda del CLI
./run.sh <comando>    # ejecuta un comando directamente
```

### Comportamiento

1. **Verifica la instalación** — comprueba que existan `.venv/.installed` y `.venv/bin/db-tool`. Si alguno falta, ejecuta `scripts/install.sh` automáticamente antes de continuar.
2. **Sin argumentos** — lanza `db-tool tui`.
3. **Con argumentos** — pasa los argumentos directamente al CLI. Equivale a llamar `.venv/bin/db-tool <args>`.

### Ejemplos

```bash
# Lanzar la TUI
./run.sh

# Copiar colecciones con ofuscación
./run.sh copy --source prod-conversational --target local-conversational \
  --pattern "mydblocal-.*" --obfuscate

# Sincronizar delta
./run.sh sync --source prod-conversational --target local-conversational

# Preview de borrado
./run.sh delete --target local-conversational --pattern "foo-.*" --dry-run

# Ver conexiones configuradas
./run.sh config list

# Limpiar mappings de ofuscación
./run.sh cleanup mappings
```

### Diferencia con llamar db-tool directamente

`run.sh` agrega la capa de autoinstalación. Si el entorno ya está instalado, el overhead es mínimo (solo una verificación de archivos). Para uso cotidiano con el entorno activado, llamar `db-tool` directamente es equivalente:

```bash
source .venv/bin/activate
db-tool tui
```
