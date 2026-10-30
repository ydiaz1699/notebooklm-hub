"""Dónde guarda el motor su estado. Portable: no depende de ningún framework externo.

Prioridad: NOTEBOOKLM_HUB_STATE_DIR > carpeta estándar del sistema operativo.
Nunca dentro del repo ni junto a las cookies.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP = "notebooklm-hub"


def state_dir() -> Path:
    override = os.environ.get("NOTEBOOKLM_HUB_STATE_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP
    xdg = os.environ.get("XDG_STATE_HOME", "").strip()
    return (Path(xdg) if xdg else Path.home() / ".local" / "state") / APP


def db_path() -> Path:
    return state_dir() / "state.db"


def profile() -> str:
    """Perfil/cuenta: separa el estado si se usan varias cuentas de Google (multi-cuenta)."""
    return os.environ.get("NOTEBOOKLM_HUB_PROFILE", "").strip() or "default"
