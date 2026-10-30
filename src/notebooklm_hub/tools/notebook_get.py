"""Tool: notebook_get — detalle de un notebook con sus fuentes (solo lectura)."""
from __future__ import annotations

from typing import Any

from .._app.notebooks import get_notebook
from .registry import ToolSpec

NAME = "notebook_get"
DESCRIPTION = (
    "Devuelve el detalle de un notebook de NotebookLM (título, fechas y la lista de fuentes con "
    "sus IDs). Úsala antes de notebook_ask si quieres preguntar solo a ciertas fuentes."
)

PARAMS: dict[str, Any] = {
    "notebook": {"type": "string", "required": True, "desc": "Nombre o ID del notebook."},
}


async def run(client: Any, **params: Any) -> dict[str, Any]:
    return await get_notebook(client, params["notebook"])


TOOL = ToolSpec(name=NAME, description=DESCRIPTION, params=PARAMS, run=run, destructive=False)
