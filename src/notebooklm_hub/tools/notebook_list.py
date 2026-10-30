"""Tool: notebook_list — lista los notebooks de la cuenta (solo lectura)."""
from __future__ import annotations

from typing import Any

from .._app.notebooks import list_notebooks
from .registry import ToolSpec

NAME = "notebook_list"
DESCRIPTION = (
    "Lista los notebooks de NotebookLM de la cuenta con su ID, título y número de fuentes. "
    "Úsala para descubrir qué notebooks existen o para obtener el ID de uno por su nombre."
)

PARAMS: dict[str, Any] = {
    "query": {"type": "string", "required": False,
              "desc": "Filtra por título (coincidencia exacta o parcial, sin mayúsculas)."},
}


async def run(client: Any, **params: Any) -> dict[str, Any]:
    notebooks = await list_notebooks(client, params.get("query"))
    return {"count": len(notebooks), "notebooks": notebooks}


TOOL = ToolSpec(name=NAME, description=DESCRIPTION, params=PARAMS, run=run, destructive=False)
