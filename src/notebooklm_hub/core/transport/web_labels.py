"""Protocolo de etiquetas de fuentes (labels) — funciones PURAS, sin red.

Decisiones "el mejor de los 7" (detalle en docs/provenance/capabilities-matrix.md §4bis):
base teng-lin (`_web/params/labels.py`, `_web/rows/labels.py`, `_web/labels.py`), que documenta
y confirma el envoltorio de opciones y los modos; jacob-bd (`core/labels.py`) coincide en la forma
de cada etiqueta pero usa un envoltorio reducido `[2]` y otros códigos de modo.

  LIST_LABELS   I3xc3c  [opts, nb_id]                         → [[etiqueta, ...]]        (solo lee)
  CREATE_LABEL  agX4Bc  [opts, nb_id, None, None, [False]]    → [None, [etiqueta, ...]]  (IA, incremental)
                        [opts, nb_id, None, None, [True]]     → idem                    (IA, BORRA y rehace)
  UPDATE_LABEL  le8sX   [opts, nb_id, label_id, [[None, [[src]]]]]                      (asignar fuente)
Etiqueta: [nombre, [[source_id], ...] | None, label_id, emoji]
"""
from __future__ import annotations

from typing import Any, Literal

from .base import TransportError


def opts() -> list[Any]:
    """Envoltorio de opciones de la web (igual que el de ADD_SOURCE). Nuevo en cada llamada."""
    return [2, None, None, [1, None, None, None, None, None, None, None, None, None, [1]]]


def build_list_labels_params(notebook_id: str) -> list[Any]:
    return [opts(), notebook_id]


def build_generate_labels_params(notebook_id: str,
                                 scope: Literal["unlabeled", "all"]) -> list[Any]:
    """scope='unlabeled' → solo fuentes sin etiqueta, conserva las existentes (seguro).
    scope='all' → BORRA todas las etiquetas y las rehace con IDs nuevos (destructivo)."""
    if scope not in ("unlabeled", "all"):
        raise ValueError(f"scope debe ser 'unlabeled' o 'all', no {scope!r}")
    return [opts(), notebook_id, None, None, [scope == "all"]]


def build_assign_source_params(notebook_id: str, label_id: str, source_id: str) -> list[Any]:
    """Asigna UNA fuente a una etiqueta (la web solo respeta el primer id por llamada)."""
    return [opts(), notebook_id, label_id, [[None, [[source_id]]]]]


def parse_label(row: Any) -> dict[str, Any]:
    """Una etiqueta del protocolo → dict canónico. Forma rara = drift (no se silencia)."""
    if not (isinstance(row, list) and len(row) >= 3 and isinstance(row[0], str)
            and isinstance(row[2], str)):
        raise TransportError("Etiqueta con formato no reconocido (drift).", retriable=False)
    members = row[1]
    if members is None:
        source_ids: list[str] = []          # etiqueta vacía: legítimo
    elif isinstance(members, list):
        source_ids = []
        for m in members:
            if not (isinstance(m, list) and m and isinstance(m[0], str)):
                raise TransportError("Miembro de etiqueta mal formado (drift).", retriable=False)
            source_ids.append(m[0])
    else:
        raise TransportError("Fuentes de la etiqueta con formato no reconocido (drift).",
                             retriable=False)
    emoji = row[3] if len(row) > 3 and isinstance(row[3], str) and row[3] else None
    return {"id": row[2], "name": row[0], "emoji": emoji, "source_ids": source_ids}


def parse_label_set(payload: Any, *, index: int) -> list[dict[str, Any]]:
    """LIST_LABELS devuelve el conjunto en [0]; CREATE_LABEL lo devuelve en [1]."""
    if not payload:
        return []
    if not isinstance(payload, list):
        raise TransportError("Respuesta de etiquetas no es una lista (drift).", retriable=False)
    rows = payload[index] if len(payload) > index else None
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise TransportError("Conjunto de etiquetas mal formado (drift).", retriable=False)
    return [parse_label(r) for r in rows]
