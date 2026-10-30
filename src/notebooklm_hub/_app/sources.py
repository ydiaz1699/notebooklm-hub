"""Lógica neutral de fuentes (escritura). Hoy: añadir texto como fuente.

Es la pieza que usa el motor para guardar cada nota del "método de las 3 notas" y el MAPA de
cobertura como fuente con nombre fijo (docs/design/recetas.md).
"""
from __future__ import annotations

from typing import Any

from .notebooks import resolve_notebook_id

MAX_TITLE = 200          # límite propio y prudente; el real de NotebookLM no está documentado


async def add_text(client: Any, notebook: str, title: str, content: str) -> dict[str, Any]:
    if not title or not title.strip():
        raise ValueError("title es obligatorio")
    if len(title) > MAX_TITLE:
        raise ValueError(f"title supera {MAX_TITLE} caracteres")
    if not content or not content.strip():
        raise ValueError("content es obligatorio (no se crean fuentes vacías)")
    nb_id = await resolve_notebook_id(client, notebook)
    added = await client.add_text_source(nb_id, title.strip(), content)
    return {"notebook_id": nb_id, "source_id": added["id"], "title": added["title"],
            "reconciled": bool(added.get("reconciled"))}
