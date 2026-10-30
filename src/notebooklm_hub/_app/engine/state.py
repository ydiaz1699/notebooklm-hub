"""Estado de un cuaderno + recomendaciones (foto → reglas), recordando la visita anterior."""
from __future__ import annotations

from typing import Any

from ..notebooks import resolve_notebook_id
from . import paths, rules, snapshot
from .store import Store


def default_store() -> Store:
    return Store(paths.db_path(), profile=paths.profile())


def _changes(prev: dict[str, Any] | None, snap: dict[str, Any]) -> dict[str, Any] | None:
    if prev is None:
        return None                                   # primera visita
    before = {s["id"] for s in prev.get("sources", [])}
    now = {s["id"] for s in snap["sources"]}
    return {"since": prev.get("taken_at"),
            "added_sources": sorted(now - before), "removed_sources": sorted(before - now)}


async def notebook_state(client: Any, notebook: str, *, store: Store | None = None,
                         thresholds: rules.Thresholds | None = None) -> dict[str, Any]:
    store = store or default_store()
    nb_id = await resolve_notebook_id(client, notebook)
    snap = await snapshot.take(client, nb_id)
    prev = store.last_snapshot(nb_id)
    findings = rules.evaluate(snap, prev, thresholds or rules.Thresholds.from_env())
    store.save_snapshot(nb_id, snap)
    return {
        "notebook_id": nb_id, "title": snap["title"], "first_visit": prev is None,
        "changes": _changes(prev, snap),
        "summary": {
            "original_sources": snap["original_count"],
            "labels": len(snap["labels"]),
            "labels_complete": sum(lb["complete"] for lb in snap["labels"]),
            "unlabeled_sources": len(snap["unlabeled_original_ids"]),
            "has_map": bool(snap["map_source_id"]),
            "chat_customized": snap["chat"]["customized"],
        },
        "recommendations": findings,
    }
