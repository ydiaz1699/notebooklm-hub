"""Foto del estado REAL de un cuaderno. Solo lecturas: nunca modifica nada.

Separa las fuentes originales de las que creó el método (notas 1/2/3 y MAPA) para que las reglas
razonen sobre el material del usuario y sepan qué está hecho.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from .conventions import is_map, parse_note_title


def _fingerprint(ids: list[str]) -> str:
    """Huella de un conjunto de fuentes: si cambia, las notas de esa categoría quedaron viejas."""
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()[:16]


async def take(client: Any, notebook_id: str) -> dict[str, Any]:
    nb = await client.get_notebook(notebook_id) or {}
    labels = await client.list_labels(notebook_id)
    chat = await client.get_chat_settings(notebook_id)

    sources = []
    notes_by_category: dict[str, dict[int, str]] = {}
    map_id = None
    for s in nb.get("sources", []):
        note = parse_note_title(s["title"])
        kind = "note" if note else ("map" if is_map(s["title"]) else "original")
        if note:
            notes_by_category.setdefault(note[1].casefold(), {})[note[0]] = s["id"]
        if kind == "map":
            map_id = s["id"]
        sources.append({"id": s["id"], "title": s["title"], "kind": kind})
    originals = {s["id"] for s in sources if s["kind"] == "original"}

    labeled: set[str] = set()
    out_labels = []
    for lb in labels:
        labeled.update(lb["source_ids"])
        orig = [sid for sid in lb["source_ids"] if sid in originals]
        notes = notes_by_category.get(lb["name"].strip().casefold(), {})
        out_labels.append({
            "id": lb["id"], "name": lb["name"],
            "original_source_ids": orig,
            "fingerprint": _fingerprint(orig),
            "notes": {n: notes.get(n) for n in (1, 2, 3)},
            "complete": all(notes.get(n) for n in (1, 2, 3)),
        })

    return {
        "notebook_id": notebook_id,
        "title": nb.get("title"),
        "taken_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "original_count": len(originals),
        "unlabeled_original_ids": sorted(originals - labeled),
        "labels": out_labels,
        "map_source_id": map_id,
        "chat": {"goal": (chat or {}).get("goal"),
                 "customized": bool(chat and chat.get("goal") == "custom"
                                    and chat.get("custom_prompt"))},
    }
