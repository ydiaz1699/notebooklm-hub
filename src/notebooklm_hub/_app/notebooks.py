"""Lógica neutral de notebooks: listar, obtener y resolver "nombre o ID" → ID canónico.

Convención de teng-lin: todas las tools aceptan nombre O ID y devuelven IDs canónicos. Si un
nombre coincide con varios notebooks NO se adivina: AmbiguousError con los candidatos.
"""
from __future__ import annotations

import re
from typing import Any

from ..core.transport.base import RpcRefusedError
from .errors import AmbiguousError, NotFoundError

# Los IDs de notebook son UUID v4 (36 chars con guiones).
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


def looks_like_id(value: str) -> bool:
    return bool(_UUID_RE.match(value.strip()))


def match_notebooks(notebooks: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    """Coincidencia exacta de título (sin mayúsculas/espacios); si no hay, por subcadena."""
    key = name.strip().casefold()
    exact = [nb for nb in notebooks if nb.get("title", "").strip().casefold() == key]
    if exact:
        return exact
    return [nb for nb in notebooks if key in nb.get("title", "").casefold()]


async def resolve_notebook_id(client: Any, notebook: str) -> str:
    """'nombre o ID' → ID. Un ID se devuelve tal cual (sin llamada de red)."""
    if not notebook or not notebook.strip():
        raise ValueError("notebook es obligatorio")
    if looks_like_id(notebook):
        return notebook.strip()
    matches = match_notebooks(await client.list_notebooks(), notebook)
    if not matches:
        raise NotFoundError(f"No hay ningún notebook llamado '{notebook}'. "
                            "Usa notebook_list para ver los disponibles.")
    if len(matches) > 1:
        options = ", ".join(f"'{nb['title']}' ({nb['id']})" for nb in matches[:10])
        raise AmbiguousError(f"'{notebook}' coincide con {len(matches)} notebooks: {options}. "
                             "Pásame el ID exacto.")
    return matches[0]["id"]


def summarize(nb: dict[str, Any]) -> dict[str, Any]:
    """Vista corta para listados (sin la lista completa de fuentes)."""
    return {k: nb.get(k) for k in
            ("id", "title", "emoji", "source_count", "role", "is_owned", "is_shared",
             "created_at", "last_viewed_at")}


async def list_notebooks(client: Any, query: str | None = None) -> list[dict[str, Any]]:
    notebooks = await client.list_notebooks()
    if query and query.strip():
        notebooks = match_notebooks(notebooks, query)
    return [summarize(nb) for nb in notebooks]


_NOT_FOUND_HINT = ("no existe o pertenece a otra cuenta de Google (NotebookLM responde igual en "
                   "ambos casos). Revisa con qué cuenta están las cookies.")


async def get_notebook(client: Any, notebook: str) -> dict[str, Any]:
    nb_id = await resolve_notebook_id(client, notebook)
    try:
        nb = await client.get_notebook(nb_id)
    except RpcRefusedError as exc:
        # Status 5 y payload vacío son las DOS señales de "no encontrado" (teng-lin #2132).
        if exc.status == 5:
            raise NotFoundError(f"El notebook '{notebook}' {_NOT_FOUND_HINT}") from exc
        raise
    if not nb:
        raise NotFoundError(f"El notebook '{notebook}' {_NOT_FOUND_HINT}")
    return nb
