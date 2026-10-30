"""Tool: source_rename — cambia el título de una fuente (verificado releyendo)."""
from __future__ import annotations

from typing import Any

from .._app.sources import rename
from .registry import ToolSpec

NAME = "source_rename"
DESCRIPTION = (
    "Cambia el título de una fuente del notebook. Comprueba que la fuente existe y que quedó con "
    "el título nuevo; devuelve previous_title para poder deshacer. Si ya tenía ese título, no hace "
    "nada (changed=false)."
)
PARAMS: dict[str, Any] = {
    "notebook": {"type": "string", "required": True, "desc": "Nombre o ID del notebook."},
    "source_id": {"type": "string", "required": True, "desc": "ID de la fuente (ver notebook_get)."},
    "title": {"type": "string", "required": True, "desc": "Título nuevo."},
}


async def run(client: Any, **params: Any) -> dict[str, Any]:
    return await rename(client, params["notebook"], params["source_id"], params["title"])


TOOL = ToolSpec(name=NAME, description=DESCRIPTION, params=PARAMS, run=run, destructive=False)
