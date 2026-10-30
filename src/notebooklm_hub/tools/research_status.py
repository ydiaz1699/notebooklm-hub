"""Tool: research_status — estado y resultados de una investigación. Solo lectura."""
from __future__ import annotations

from typing import Any

from .._app.research import status
from .registry import ToolSpec

NAME = "research_status"
DESCRIPTION = (
    "Estado de una investigación del notebook: in_progress, completed, no_results, cancelled o "
    "failed (done=true cuando ya no está en curso), con la lista de resultados encontrados. Sin "
    "task_id muestra la más reciente. Solo lee."
)
PARAMS: dict[str, Any] = {
    "notebook": {"type": "string", "required": True, "desc": "Nombre o ID del notebook."},
    "task_id": {"type": "string", "required": False, "desc": "ID devuelto por research_start."},
}


async def run(client: Any, **params: Any) -> dict[str, Any]:
    return await status(client, params["notebook"], params.get("task_id"))


TOOL = ToolSpec(name=NAME, description=DESCRIPTION, params=PARAMS, run=run, destructive=False)
