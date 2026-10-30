"""Tool: chat_settings_get — cómo está personalizado el chat del notebook. Solo lectura."""
from __future__ import annotations

from typing import Any

from .._app.chat_settings import get_settings
from .registry import ToolSpec

NAME = "chat_settings_get"
DESCRIPTION = (
    "Lee la personalización del chat de un notebook (Configurar → Personalizar): objetivo "
    "(default / custom / learning_guide), longitud de respuesta (default / longer / shorter) y "
    "el prompt personalizado si existe. Solo lee."
)
PARAMS: dict[str, Any] = {
    "notebook": {"type": "string", "required": True, "desc": "Nombre o ID del notebook."},
}


async def run(client: Any, **params: Any) -> dict[str, Any]:
    return await get_settings(client, params["notebook"])


TOOL = ToolSpec(name=NAME, description=DESCRIPTION, params=PARAMS, run=run, destructive=False)
