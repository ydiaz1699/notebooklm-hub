"""Tool: label_add_source — mete una fuente en una etiqueta (idempotente)."""
from __future__ import annotations

from typing import Any

from .._app.labels import assign_source
from .registry import ToolSpec

NAME = "label_add_source"
DESCRIPTION = (
    "Añade una fuente a una etiqueta (categoría) del notebook. Si ya estaba, no hace nada "
    "(changed=false). No quita la fuente de otras etiquetas ni la borra del notebook."
)
PARAMS: dict[str, Any] = {
    "notebook": {"type": "string", "required": True, "desc": "Nombre o ID del notebook."},
    "label": {"type": "string", "required": True, "desc": "Nombre o ID de la etiqueta."},
    "source_id": {"type": "string", "required": True, "desc": "ID de la fuente (ver label_list)."},
}


async def run(client: Any, **params: Any) -> dict[str, Any]:
    return await assign_source(client, params["notebook"], params["label"], params["source_id"])


TOOL = ToolSpec(name=NAME, description=DESCRIPTION, params=PARAMS, run=run, destructive=False)
