"""Nombres fijos que usan las recetas (docs/design/recetas.md). Único sitio donde se definen:
el motor los crea con estos nombres y la foto los reconoce por ellos.
"""
from __future__ import annotations

import re

MAP_TITLE = "MAPA"
NOTE_KINDS = {1: "Puntos clave", 2: "Índice de preguntas", 3: "Síntesis"}

# "1. Puntos clave – Turbo" (acepta guion largo, medio o normal y espacios variables).
_NOTE_RE = re.compile(r"^\s*([123])\.\s*(Puntos clave|Índice de preguntas|Síntesis)\s*[–—-]\s*(.+?)\s*$",
                      re.IGNORECASE)


def note_title(number: int, category: str) -> str:
    return f"{number}. {NOTE_KINDS[number]} – {category.strip()}"


def parse_note_title(title: str) -> tuple[int, str] | None:
    """'2. Índice de preguntas – Turbo' → (2, 'Turbo'); otra cosa → None."""
    m = _NOTE_RE.match(title or "")
    if not m:
        return None
    number = int(m.group(1))
    if m.group(2).casefold() != NOTE_KINDS[number].casefold():
        return None                     # número y tipo no casan: no es una nota del método
    return number, m.group(3)


def is_map(title: str) -> bool:
    return (title or "").strip() == MAP_TITLE
