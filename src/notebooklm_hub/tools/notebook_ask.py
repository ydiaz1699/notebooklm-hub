"""Tool: notebook_ask — pregunta a un notebook y devuelve respuesta citada.

Primera tool real. Demuestra el patrón: la tool solo describe params y delega en _app/ (neutral),
que a su vez usa core/client (transporte). Aparece sola en MCP, REST y CLI vía el registry.
"""
from __future__ import annotations

from typing import Any

from .._app.ask import AskRequest, build_ask_plan, execute_ask
from .registry import ToolSpec

NAME = "notebook_ask"
DESCRIPTION = (
    "Pregunta a un notebook de NotebookLM y devuelve una respuesta fundamentada en sus fuentes. "
    "Úsala para consultar documentos ya subidos a un notebook."
)

PARAMS: dict[str, Any] = {
    "notebook": {"type": "string", "required": True, "desc": "Nombre o ID del notebook."},
    "question": {"type": "string", "required": True, "desc": "La pregunta a responder."},
    "source_ids": {"type": "array", "required": False,
                   "desc": "IDs de fuentes a consultar (por defecto, todas)."},
}


async def run(client: Any, **params: Any) -> dict[str, Any]:
    plan = build_ask_plan(AskRequest(
        notebook=params["notebook"],
        question=params["question"],
        source_ids=params.get("source_ids"),
    ))
    result = await execute_ask(plan, client)
    return {
        "answer": result.answer,
        "conversation_id": result.conversation_id,
        "notebook_id": result.notebook_id,
    }


TOOL = ToolSpec(name=NAME, description=DESCRIPTION, params=PARAMS, run=run, destructive=False)
