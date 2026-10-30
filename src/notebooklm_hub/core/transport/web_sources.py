"""Protocolo de fuentes (escritura) — funciones PURAS, sin red.

Fuente de texto (ADD_SOURCE izAoDd). "El mejor de los 7":
  · 11 campos [None, [título, texto], None, 2, None×6, 1] — coinciden teng-lin y jacob-bd.
  · Bloque de opciones ANIDADO [2, None, None, [1, ..., [1]]] — teng-lin #1546 (verificado en
    vivo: los servidores migrados rechazan la forma plana `[2], [1, ...]` que aún usa jacob-bd).
  · Respuesta en 3 formas posibles — teng-lin SourceRow.from_unknown_shape.
  · Escritura dudosa → buscar la fuente por título antes de fallar — jacob-bd _reconcile_source.
"""
from __future__ import annotations

from typing import Any

from .web_labels import opts as template_block


def build_add_text_params(notebook_id: str, title: str, content: str) -> list[Any]:
    spec = [None, [title, content], None, 2, None, None, None, None, None, None, 1]
    return [[spec], notebook_id, template_block()]


def _source_entry(payload: Any) -> list[Any] | None:
    """Localiza la fila [[id], título, ...] en cualquiera de las 3 formas de respuesta."""
    if not isinstance(payload, list) or not payload:
        return None
    node = payload
    for _ in range(3):                      # profunda [[[[id],t]]] · media [[[id],t]] · plana
        first = node[0] if isinstance(node, list) and node else None
        if isinstance(first, list) and first and isinstance(first[0], list):
            node = first
            continue
        break
    if isinstance(node, list) and node and isinstance(node[0], (list, str)):
        return node
    return None


def parse_added_source(payload: Any, fallback_title: str) -> dict[str, Any] | None:
    """Respuesta de ADD_SOURCE → {id, title}, o None si no se reconoce."""
    entry = _source_entry(payload)
    if entry is None:
        return None
    raw_id = entry[0]
    sid = raw_id[0] if isinstance(raw_id, list) and raw_id else raw_id
    if not isinstance(sid, str) or not sid:
        return None
    title = entry[1] if len(entry) > 1 and isinstance(entry[1], str) and entry[1] else fallback_title
    return {"id": sid, "title": title}
