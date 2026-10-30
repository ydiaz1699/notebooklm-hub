"""Tool: label_auto — autoetiqueta con la IA de NotebookLM solo las fuentes SIN etiqueta."""
from __future__ import annotations

from typing import Any

from .._app.labels import auto_label
from .registry import ToolSpec

NAME = "label_auto"
DESCRIPTION = (
    "Agrupa por tema, con la IA de NotebookLM, las fuentes del notebook que todavía no tienen "
    "etiqueta (el botón de etiquetas de la web). Conserva las etiquetas existentes. Devuelve el "
    "conjunto completo de etiquetas resultante."
)
PARAMS: dict[str, Any] = {
    "notebook": {"type": "string", "required": True, "desc": "Nombre o ID del notebook."},
}


async def run(client: Any, **params: Any) -> dict[str, Any]:
    return await auto_label(client, params["notebook"], scope="unlabeled")


TOOL = ToolSpec(name=NAME, description=DESCRIPTION, params=PARAMS, run=run, destructive=False)
