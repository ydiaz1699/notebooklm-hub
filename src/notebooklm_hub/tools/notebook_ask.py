"""Tool: notebook_ask — pregunta a un notebook y devuelve la respuesta con sus citas.

La tool solo describe params y delega en _app/ (neutral), que usa core/client (transporte).
Aparece sola en MCP, REST y CLI vía el registry.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .._app.ask import AskRequest, build_ask_plan, execute_ask
from .registry import ToolSpec

NAME = "notebook_ask"
DESCRIPTION = (
    "Pregunta a un notebook de NotebookLM y devuelve una respuesta fundamentada en sus fuentes, "
    "con las citas ([N] en el texto → references: fuente y fragmento citado). Por defecto continúa "
    "la conversación actual del notebook (la misma que se ve en la web). Para encadenar preguntas, "
    "pasa el conversation_id devuelto."
)

PARAMS: dict[str, Any] = {
    "notebook": {"type": "string", "required": True, "desc": "Nombre o ID del notebook."},
    "question": {"type": "string", "required": True, "desc": "La pregunta a responder."},
    "source_ids": {"type": "array", "required": False,
                   "desc": "IDs de fuentes a consultar (por defecto, todas). Ver notebook_get."},
    "conversation_id": {"type": "string", "required": False,
                        "desc": "ID de conversación devuelto por una llamada anterior, "
                                "para una pregunta de seguimiento."},
}


async def run(client: Any, **params: Any) -> dict[str, Any]:
    plan = build_ask_plan(AskRequest(
        notebook=params["notebook"],
        question=params["question"],
        source_ids=params.get("source_ids"),
        conversation_id=params.get("conversation_id"),
    ))
    result = asdict(await execute_ask(plan, client))
    if result["warning"] is None:
        result.pop("warning")
    return result


TOOL = ToolSpec(name=NAME, description=DESCRIPTION, params=PARAMS, run=run, destructive=False)
