"""Tool: notebook_state — qué le falta a un cuaderno y qué conviene hacer. Solo lee NotebookLM."""
from __future__ import annotations

from typing import Any

from .._app.engine.state import notebook_state
from .registry import ToolSpec

NAME = "notebook_state"
DESCRIPTION = (
    "Revisa un cuaderno y dice qué le falta y qué conviene hacer, con el motivo: buscar fuentes, "
    "crear el MAPA de un documento largo, organizar por categorías con el método de las 3 notas, "
    "notas desactualizadas o pendientes, personalizar el chat. Recuerda la visita anterior y "
    "muestra qué cambió. Úsala al empezar a trabajar en un cuaderno. No modifica NotebookLM."
)
PARAMS: dict[str, Any] = {
    "notebook": {"type": "string", "required": True, "desc": "Nombre o ID del notebook."},
}


async def run(client: Any, **params: Any) -> dict[str, Any]:
    return await notebook_state(client, params["notebook"])


TOOL = ToolSpec(name=NAME, description=DESCRIPTION, params=PARAMS, run=run, destructive=False)
