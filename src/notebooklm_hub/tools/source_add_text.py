"""Tool: source_add_text — añade un texto como fuente nueva del notebook."""
from __future__ import annotations

from typing import Any

from .._app.sources import add_text
from .registry import ToolSpec

NAME = "source_add_text"
DESCRIPTION = (
    "Añade un texto (por ejemplo una respuesta del chat o una nota) como FUENTE nueva del notebook, "
    "con el título indicado. Si la respuesta del servidor es dudosa, comprueba si se creó antes de "
    "dar error (reconciled=true) para no duplicarla."
)
PARAMS: dict[str, Any] = {
    "notebook": {"type": "string", "required": True, "desc": "Nombre o ID del notebook."},
    "title": {"type": "string", "required": True, "desc": "Título de la fuente."},
    "content": {"type": "string", "required": True, "desc": "Texto de la fuente."},
}


async def run(client: Any, **params: Any) -> dict[str, Any]:
    return await add_text(client, params["notebook"], params["title"], params["content"])


TOOL = ToolSpec(name=NAME, description=DESCRIPTION, params=PARAMS, run=run, destructive=False)
