from __future__ import annotations

import json
import os
from pathlib import Path

_TRANSLATIONS: dict[str, str] = {}
_LANG: str = "en"
_TRANSLATIONS_DIR = Path(__file__).parent / "translations"


def _load(lang: str) -> None:
    global _TRANSLATIONS, _LANG
    path = _TRANSLATIONS_DIR / f"{lang}.json"
    if not path.exists():
        path = _TRANSLATIONS_DIR / "en.json"
    with open(path, encoding="utf-8") as f:
        _TRANSLATIONS = json.load(f)
    _LANG = lang


def setup(lang: str) -> None:
    """Reload translations for the given language code (e.g. 'en', 'es')."""
    _load(lang)


def t(key: str, **kwargs: object) -> str:
    """Return the translation for key, interpolating any kwargs."""
    text = _TRANSLATIONS.get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text


# Auto-load at import time from LANGUAGE env var so Typer help strings are translated.
_load(os.environ.get("LANGUAGE", "en"))
