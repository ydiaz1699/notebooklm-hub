"""Lógica neutral de etiquetas (labels): leer, autoetiquetar con IA y asignar fuentes.

Las etiquetas son la base del "método de las 3 notas" (docs/design/recetas.md, R3).
Reglas: leer NUNCA modifica (LIST_LABELS); autoetiquetar por defecto es incremental (solo
fuentes sin etiqueta); rehacer todas es destructivo y va por una tool aparte con confirmación.
"""
from __future__ import annotations

from typing import Any

from .errors import AmbiguousError, NotFoundError
from .notebooks import resolve_notebook_id


def _enrich(labels: list[dict[str, Any]], notebook: dict[str, Any] | None) -> dict[str, Any]:
    """Añade títulos de fuentes y la lista de fuentes SIN etiqueta (lo que necesita el motor)."""
    titles = {s["id"]: s["title"] for s in (notebook or {}).get("sources", [])}
    labeled: set[str] = set()
    out = []
    for lb in labels:
        labeled.update(lb["source_ids"])
        out.append({**lb, "source_count": len(lb["source_ids"]),
                    "sources": [{"id": sid, "title": titles.get(sid)} for sid in lb["source_ids"]]})
    unlabeled = [{"id": sid, "title": t} for sid, t in titles.items() if sid not in labeled]
    return {"count": len(out), "labels": out, "unlabeled_sources": unlabeled}


async def list_labels(client: Any, notebook: str) -> dict[str, Any]:
    nb_id = await resolve_notebook_id(client, notebook)
    labels = await client.list_labels(nb_id)
    return {"notebook_id": nb_id, **_enrich(labels, await client.get_notebook(nb_id))}


async def auto_label(client: Any, notebook: str, *, scope: str = "unlabeled") -> dict[str, Any]:
    nb_id = await resolve_notebook_id(client, notebook)
    labels = await client.generate_labels(nb_id, scope)
    return {"notebook_id": nb_id, "scope": scope,
            **_enrich(labels, await client.get_notebook(nb_id))}


def match_label(labels: list[dict[str, Any]], label: str) -> dict[str, Any]:
    """Nombre o ID de etiqueta → etiqueta. Exacto > parcial; ambiguo NO se adivina."""
    key = label.strip()
    by_id = [lb for lb in labels if lb["id"] == key]
    if by_id:
        return by_id[0]
    fold = key.casefold()
    exact = [lb for lb in labels if lb["name"].strip().casefold() == fold]
    matches = exact or [lb for lb in labels if fold in lb["name"].casefold()]
    if not matches:
        names = ", ".join(f"'{lb['name']}'" for lb in labels) or "ninguna"
        raise NotFoundError(f"No hay ninguna etiqueta '{label}'. Etiquetas: {names}.")
    if len(matches) > 1:
        options = ", ".join(f"'{lb['name']}' ({lb['id']})" for lb in matches)
        raise AmbiguousError(f"'{label}' coincide con varias etiquetas: {options}. "
                             "Pásame el ID exacto.")
    return matches[0]


async def assign_source(client: Any, notebook: str, label: str, source_id: str) -> dict[str, Any]:
    if not source_id or not source_id.strip():
        raise ValueError("source_id es obligatorio")
    nb_id = await resolve_notebook_id(client, notebook)
    target = match_label(await client.list_labels(nb_id), label)
    nb = await client.get_notebook(nb_id) or {}
    if source_id not in {s["id"] for s in nb.get("sources", [])}:
        raise NotFoundError(f"La fuente '{source_id}' no está en este notebook.")
    if source_id in target["source_ids"]:
        return {"notebook_id": nb_id, "label_id": target["id"], "label": target["name"],
                "source_id": source_id, "changed": False}       # idempotente: ya estaba
    await client.assign_source_to_label(nb_id, target["id"], source_id)
    return {"notebook_id": nb_id, "label_id": target["id"], "label": target["name"],
            "source_id": source_id, "changed": True}
