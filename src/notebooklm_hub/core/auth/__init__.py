"""Auth — obtención de credenciales para hablar con NotebookLM.

Fase 1: lo mínimo para funcionar = cargar cookies de una cuenta ya logueada y producir el header
`Cookie` que consume el transporte web. Fases siguientes: master-token (headless auto-curativo),
login por navegador, multi-cuenta/rotación (ver docs/ROADMAP.md).

Formas de aportar cookies en Fase 1 (sin navegador, aptas para servidor/NAS):
  1. Variable de entorno NOTEBOOKLM_HUB_COOKIES = "NAME1=VAL1; NAME2=VAL2; ..."
  2. Archivo JSON (ruta en NOTEBOOKLM_HUB_COOKIE_FILE) con [{"name":..., "value":...}, ...]
     — el mismo formato que exporta Playwright / una extensión de cookies.

⚠️ VERIFICAR EN ENTORNO REAL: no probado contra una cuenta de Google desde el sandbox.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


class AuthError(Exception):
    pass


def load_cookie_header() -> str:
    """Devuelve el header `Cookie` ("k=v; k=v") a partir de env var o archivo JSON.

    Lanza AuthError si no hay credenciales configuradas.
    """
    raw = os.environ.get("NOTEBOOKLM_HUB_COOKIES", "").strip()
    if raw:
        return raw

    path = os.environ.get("NOTEBOOKLM_HUB_COOKIE_FILE", "").strip()
    if path:
        p = Path(path).expanduser()
        if not p.is_file():
            raise AuthError(f"NOTEBOOKLM_HUB_COOKIE_FILE no existe: {p}")
        try:
            data = json.loads(p.read_text())
        except json.JSONDecodeError as exc:
            raise AuthError(f"cookie file no es JSON válido: {exc}") from exc
        if not isinstance(data, list):
            raise AuthError("cookie file debe ser una lista [{name, value}, ...]")
        parts = [f"{c['name']}={c['value']}" for c in data if "name" in c and "value" in c]
        if not parts:
            raise AuthError("cookie file no contiene cookies con name/value")
        return "; ".join(parts)

    raise AuthError(
        "Sin credenciales. Define NOTEBOOKLM_HUB_COOKIES o NOTEBOOKLM_HUB_COOKIE_FILE "
        "(ver docs y core/auth). Usa una cuenta DEDICADA."
    )
