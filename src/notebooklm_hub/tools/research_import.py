"""Tool: research_import — importa como fuentes los resultados de una investigación."""
from __future__ import annotations

from typing import Any

from .._app.research import import_results
from .registry import ToolSpec

NAME = "research_import"
DESCRIPTION = (
    "Importa como fuentes del notebook los resultados de una investigación COMPLETADA (y, en "
    "Deep Research, su informe). Por defecto todos; usa indices para elegir. No reimporta lo que "
    "ya existe con el mismo título (skipped)."
)
PARAMS: dict[str, Any] = {
    "notebook": {"type": "string", "required": True, "desc": "Nombre o ID del notebook."},
    "task_id": {"type": "string", "required": True, "desc": "ID devuelto por research_start."},
    "indices": {"type": "array", "required": False,
                "desc": "Índices de los resultados a importar (ver research_status)."},
    "include_report": {"type": "boolean", "required": False,
                       "desc": "Importar también el informe de Deep Research (por defecto sí)."},
}


async def run(client: Any, **params: Any) -> dict[str, Any]:
    include = params.get("include_report")
    return await import_results(client, params["notebook"], params["task_id"],
                                indices=params.get("indices"),
                                include_report=True if include is None else bool(include))


TOOL = ToolSpec(name=NAME, description=DESCRIPTION, params=PARAMS, run=run, destructive=False)
