#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$ROOT_DIR/.venv"
MARKER="$VENV_DIR/.installed"

# ── colores ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[db-tool]${NC} $*"; }
success() { echo -e "${GREEN}[db-tool]${NC} $*"; }
warn()    { echo -e "${YELLOW}[db-tool]${NC} $*"; }
error()   { echo -e "${RED}[db-tool] ERROR:${NC} $*" >&2; }

# ── checks previos ────────────────────────────────────────────────────────────

info "Verificando dependencias del sistema..."

# Python 3.12+
if ! command -v python3 &>/dev/null; then
    error "Python 3 no encontrado. Instalar Python 3.12 o superior."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [[ "$PYTHON_MAJOR" -lt 3 ]] || [[ "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 12 ]]; then
    error "Python $PYTHON_VERSION detectado. Se requiere Python 3.12 o superior."
    exit 1
fi
success "Python $PYTHON_VERSION ✓"

# uv (gestor de paquetes)
UV_BIN=""
if command -v uv &>/dev/null; then
    UV_BIN="uv"
elif [[ -x "$HOME/.local/bin/uv" ]]; then
    UV_BIN="$HOME/.local/bin/uv"
fi

if [[ -z "$UV_BIN" ]]; then
    warn "uv no encontrado. Instalando uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    UV_BIN="$HOME/.local/bin/uv"
    success "uv instalado ✓"
else
    success "uv $(${UV_BIN} --version 2>/dev/null | head -1) ✓"
fi

# ── entorno virtual ───────────────────────────────────────────────────────────

cd "$ROOT_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
    info "Creando entorno virtual en .venv ..."
    "$UV_BIN" venv "$VENV_DIR"
fi
success "Entorno virtual ✓"

# ── instalar dependencias ─────────────────────────────────────────────────────

info "Instalando dependencias desde pyproject.toml ..."
"$UV_BIN" pip install -e ".[dev]"
success "Dependencias instaladas ✓"

# ── archivos de configuración ─────────────────────────────────────────────────

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

# ── directorios de estado ─────────────────────────────────────────────────────

mkdir -p "$HOME/.db-tool/state"
mkdir -p "$HOME/.db-tool/mappings"

# ── marker de instalación ─────────────────────────────────────────────────────

date -u +"%Y-%m-%dT%H:%M:%SZ" > "$MARKER"

echo ""
success "Instalación completada."
echo -e "  Activar entorno : ${CYAN}source .venv/bin/activate${NC}"
echo -e "  Lanzar TUI      : ${CYAN}./run.sh${NC}"
echo -e "  Ver ayuda       : ${CYAN}.venv/bin/db-tool --help${NC}"
echo ""
warn "Recordá editar config/connections.yaml con tus conexiones antes de usar la herramienta."
