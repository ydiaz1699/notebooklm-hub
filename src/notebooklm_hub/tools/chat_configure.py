"""Tool: chat_configure — personaliza el chat del notebook (solo cambia lo que se indica)."""
from __future__ import annotations

from typing import Any

from .._app.chat_settings import configure
from .registry import ToolSpec

NAME = "chat_configure"
DESCRIPTION = (
    "Personaliza el chat de un notebook: objetivo, tono/formato y prohibiciones van en "
    "custom_prompt (máx. 10 000 caracteres); response_length = default / longer / shorter. Solo "
    "cambia lo que pases y conserva el resto. Devuelve 'previous' para poder deshacer."
)
PARAMS: dict[str, Any] = {
    "notebook": {"type": "string", "required": True, "desc": "Nombre o ID del notebook."},
    "custom_prompt": {"type": "string", "required": False,
                      "desc": "Instrucciones del chat. Si se pasa, el objetivo pasa a 'custom'."},
    "goal": {"type": "string", "required": False,
             "desc": "default | custom | learning_guide."},
    "response_length": {"type": "string", "required": False,
                        "desc": "default | longer | shorter."},
}


async def run(client: Any, **params: Any) -> dict[str, Any]:
    return await configure(client, params["notebook"], goal=params.get("goal"),
                           response_length=params.get("response_length"),
                           custom_prompt=params.get("custom_prompt"))


TOOL = ToolSpec(name=NAME, description=DESCRIPTION, params=PARAMS, run=run, destructive=False)
