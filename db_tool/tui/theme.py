"""
Visual theme for db-tool TUI.

To customize, edit or create ~/.db-tool/theme.json with any subset of the
fields defined in BrandTheme. Unset fields fall back to the defaults below.

Example theme.json:
{
  "primary": "#00d4aa",
  "accent": "#ff6b35",
  "background": "#0d0f14"
}
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class BrandTheme:
    # ── Core brand ─────────────────────────────────────────────────────────
    primary: str = "#4f8ef7"      # botones principales, títulos
    secondary: str = "#a78bfa"    # highlights secundarios, section headers
    accent: str = "#fb923c"       # énfasis, badges
    success: str = "#34d399"      # éxito, operaciones OK
    warning: str = "#fbbf24"      # advertencias
    error: str = "#f87171"        # errores, acciones destructivas

    # ── Superficies ────────────────────────────────────────────────────────
    background: str = "#0f1117"
    surface: str = "#161b27"
    panel: str = "#1e2436"

    # ── Colores de entorno (bordes de connection cards) ────────────────────
    env_production: str = "#f87171"   # rojo  — producción
    env_stage: str = "#fbbf24"        # amarillo — stage
    env_dev: str = "#34d399"          # verde — dev
    env_local: str = "#60a5fa"        # azul — local

    # ── Texto ──────────────────────────────────────────────────────────────
    text_muted: str = "#4b5675"

    @classmethod
    def load(cls, path: Path | None = None) -> "BrandTheme":
        """Load theme from JSON, falling back to defaults for missing keys."""
        target = path or (Path.home() / ".db-tool" / "theme.json")
        try:
            if target.exists():
                data = json.loads(target.read_text())
                valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
                return cls(**valid)
        except Exception:
            pass
        return cls()

    def save(self, path: Path | None = None) -> None:
        """Persist current theme to JSON (creates parent dirs as needed)."""
        target = path or (Path.home() / ".db-tool" / "theme.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(self), indent=2))

    def to_textual_theme(self) -> object:
        """Convert to a Textual Theme object for use with App.register_theme()."""
        from textual.theme import Theme as TxtTheme
        return TxtTheme(
            name="db-tool",
            primary=self.primary,
            secondary=self.secondary,
            accent=self.accent,
            success=self.success,
            warning=self.warning,
            error=self.error,
            background=self.background,
            surface=self.surface,
            panel=self.panel,
            dark=True,
            variables={
                "env-production": self.env_production,
                "env-stage":      self.env_stage,
                "env-dev":        self.env_dev,
                "env-local":      self.env_local,
                "text-muted":     self.text_muted,
            },
        )
