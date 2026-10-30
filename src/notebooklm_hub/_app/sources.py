"""Lógica neutral de fuentes (escritura). Hoy: añadir texto como fuente.

Es la pieza que usa el motor para guardar cada nota del "método de las 3 notas" y el MAPA de
cobertura como fuente con nombre fijo (docs/design/recetas.md).
"""
from __future__ import annotations

from typing import Any

from ..core.transport.base import UnconfirmedWriteError
from .errors import NotFoundError
from .notebooks import resolve_notebook_id

MAX_TITLE = 200          # límite propio y prudente; el real de NotebookLM no está documentado


async def rename(client: Any, notebook: str, source_id: str, title: str) -> dict[str, Any]:
    """Renombra una fuente. Comprueba antes (existe) y después (quedó con el título): la
    respuesta del servidor NO avisa si la fuente no existe (teng-lin: miss-detection por relectura)."""
    if not source_id or not source_id.strip():
        raise ValueError("source_id es obligatorio")
    if not title or not title.strip():
        raise ValueError("title es obligatorio")
    if len(title) > MAX_TITLE:
        raise ValueError(f"title supera {MAX_TITLE} caracteres")
    title = title.strip()
    nb_id = await resolve_notebook_id(client, notebook)

    def find(nb: dict[str, Any] | None) -> dict[str, Any] | None:
        return next((s for s in (nb or {}).get("sources", []) if s["id"] == source_id), None)

    before = find(await client.get_notebook(nb_id))
    if before is None:
        raise NotFoundError(f"La fuente '{source_id}' no está en este notebook.")
    if before["title"] == title:
        return {"notebook_id": nb_id, "source_id": source_id, "title": title,
                "previous_title": title, "changed": False}
    await client.rename_source(nb_id, source_id, title)
    after = find(await client.get_notebook(nb_id))
    if after is None or after["title"] != title:
        raise UnconfirmedWriteError(
            f"Se pidió renombrar '{before['title']}' a '{title}' pero al releer no coincide.")
    return {"notebook_id": nb_id, "source_id": source_id, "title": title,
            "previous_title": before["title"], "changed": True}


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
