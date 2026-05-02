#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
MARKER="$VENV_DIR/.installed"
DB_TOOL="$VENV_DIR/bin/db-tool"

# ── verificar instalación ─────────────────────────────────────────────────────

if [[ ! -f "$MARKER" ]] || [[ ! -x "$DB_TOOL" ]]; then
    echo "[db-tool] Instalación no encontrada. Ejecutando scripts/install.sh ..."
    bash "$ROOT_DIR/scripts/install.sh"
fi

# ── ejecutar ──────────────────────────────────────────────────────────────────

# Sin argumentos → lanza la TUI
# Con argumentos → pasa directamente al CLI (ej: ./run.sh copy --source x --target y)
exec "$DB_TOOL" "${@:-tui}"
