"""Tool: label_list — etiquetas (categorías) del notebook con sus fuentes. Solo lectura."""
from __future__ import annotations

from typing import Any

from .._app.labels import list_labels
from .registry import ToolSpec

NAME = "label_list"
DESCRIPTION = (
    "Lista las etiquetas (categorías) de un notebook de NotebookLM con las fuentes de cada una y "
    "las fuentes que aún no tienen etiqueta. Solo lee: nunca crea ni cambia etiquetas."
)
PARAMS: dict[str, Any] = {
    "notebook": {"type": "string", "required": True, "desc": "Nombre o ID del notebook."},
}


async def run(client: Any, **params: Any) -> dict[str, Any]:
    return await list_labels(client, params["notebook"])


TOOL = ToolSpec(name=NAME, description=DESCRIPTION, params=PARAMS, run=run, destructive=False)
