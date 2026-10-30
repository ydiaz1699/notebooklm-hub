"""Tool: research_start — lanza una investigación (Deep Research por defecto) sin esperar."""
from __future__ import annotations

from typing import Any

from .._app.research import start
from .registry import ToolSpec

NAME = "research_start"
DESCRIPTION = (
    "Lanza una búsqueda de fuentes en la web para un notebook. mode='deep' (por defecto) es Deep "
    "Research: ~5 min, ~40 fuentes y un informe; mode='fast': ~30 s, ~10 fuentes. Formula la "
    "consulta por INTENCIÓN (qué quieres lograr), no solo por tema. No espera: devuelve task_id "
    "para research_status y research_import. No añade fuentes por sí sola."
)
PARAMS: dict[str, Any] = {
    "notebook": {"type": "string", "required": True, "desc": "Nombre o ID del notebook."},
    "query": {"type": "string", "required": True, "desc": "Qué investigar (objetivo/intención)."},
    "mode": {"type": "string", "required": False, "desc": "deep (por defecto) | fast."},
}


async def run(client: Any, **params: Any) -> dict[str, Any]:
    return await start(client, params["notebook"], params["query"], params.get("mode") or "deep")


TOOL = ToolSpec(name=NAME, description=DESCRIPTION, params=PARAMS, run=run, destructive=False)
