"""Lógica neutral de la personalización del chat del notebook (receta R1; la instrucción del
MAPA de R4 también va aquí).

Lectura-mezcla-escritura (teng-lin #1751): la escritura reemplaza TODOS los ajustes, así que se
lee lo actual y solo se cambia lo que el llamador pide. Después se relee para verificar.
"""
from __future__ import annotations

from typing import Any

from ..core.transport.base import UnconfirmedWriteError
from ..core.transport.web_settings import GOALS, LENGTHS, MAX_CUSTOM_PROMPT
from .errors import NotFoundError
from .notebooks import resolve_notebook_id


async def get_settings(client: Any, notebook: str) -> dict[str, Any]:
    nb_id = await resolve_notebook_id(client, notebook)
    settings = await client.get_chat_settings(nb_id)
    if settings is None:
        raise NotFoundError(f"El notebook '{notebook}' no existe o pertenece a otra cuenta.")
    return {"notebook_id": nb_id, **settings,
            "is_customized": settings["goal"] == "custom" and bool(settings["custom_prompt"])}


def plan_settings(current: dict[str, Any], *, goal: str | None, response_length: str | None,
                  custom_prompt: str | None) -> dict[str, Any]:
    """Mezcla lo pedido con lo actual. Pura. Pasar solo custom_prompt implica goal='custom'."""
    if goal is not None and goal not in GOALS:
        raise ValueError(f"goal debe ser uno de {sorted(GOALS)}")
    if response_length is not None and response_length not in LENGTHS:
        raise ValueError(f"response_length debe ser uno de {sorted(LENGTHS)}")
    if custom_prompt is not None:
        if not custom_prompt.strip():
            raise ValueError("custom_prompt no puede estar vacío")
        if len(custom_prompt) > MAX_CUSTOM_PROMPT:
            raise ValueError(f"custom_prompt supera {MAX_CUSTOM_PROMPT} caracteres "
                             f"(tiene {len(custom_prompt)})")
    if goal is None and response_length is None and custom_prompt is None:
        raise ValueError("indica al menos goal, response_length o custom_prompt")
    new_goal = goal or ("custom" if custom_prompt is not None else current["goal"])
    new_prompt = None
    if new_goal == "custom":
        new_prompt = custom_prompt if custom_prompt is not None else current.get("custom_prompt")
        if not new_prompt:
            raise ValueError("goal='custom' necesita custom_prompt (el notebook no tiene uno)")
    return {"goal": new_goal,
            "response_length": response_length or current["response_length"],
            "custom_prompt": new_prompt}


async def configure(client: Any, notebook: str, *, goal: str | None = None,
                    response_length: str | None = None,
                    custom_prompt: str | None = None) -> dict[str, Any]:
    nb_id = await resolve_notebook_id(client, notebook)
    current = await client.get_chat_settings(nb_id)
    if current is None:
        raise NotFoundError(f"El notebook '{notebook}' no existe o pertenece a otra cuenta.")
    target = plan_settings(current, goal=goal, response_length=response_length,
                           custom_prompt=custom_prompt)
    if target == current:
        return {"notebook_id": nb_id, "changed": False, "settings": current, "previous": current}
    await client.configure_chat(nb_id, **target)
    after = await client.get_chat_settings(nb_id)
    if after != target:
        raise UnconfirmedWriteError(
            "Se enviaron los ajustes del chat pero al releerlos no coinciden. "
            f"Esperado {target}, leído {after}.")
    # 'previous' permite deshacer: el prompt anterior no se pierde.
    return {"notebook_id": nb_id, "changed": True, "settings": after, "previous": current}
