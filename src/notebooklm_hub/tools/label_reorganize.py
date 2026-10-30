"""Tool: label_reorganize — BORRA todas las etiquetas y las rehace con IA. Destructiva."""
from __future__ import annotations

from typing import Any

from .._app.labels import auto_label
from .registry import ToolSpec

NAME = "label_reorganize"
DESCRIPTION = (
    "Rehace desde cero TODAS las etiquetas del notebook con la IA de NotebookLM. DESTRUCTIVA: "
    "borra las etiquetas actuales (y su organización manual) y crea otras con IDs nuevos. "
    "Para clasificar solo fuentes nuevas usa label_auto. Requiere confirm=true."
)
PARAMS: dict[str, Any] = {
    "notebook": {"type": "string", "required": True, "desc": "Nombre o ID del notebook."},
}


async def run(client: Any, **params: Any) -> dict[str, Any]:
    return await auto_label(client, params["notebook"], scope="all")


TOOL = ToolSpec(name=NAME, description=DESCRIPTION, params=PARAMS, run=run, destructive=True)
