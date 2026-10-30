"""Configuración del chat del notebook y renombrado de fuente — funciones PURAS, sin red.

"El mejor de los 7" (docs/provenance/capabilities-matrix.md §4bis):
  · Escribir: RENAME_NOTEBOOK (s0tc2d, "MutateProject") con los ajustes en params[1][0][7] —
    coinciden teng-lin `_web/chat.py:_send_configure` y jacob-bd `core/notebooks.py:configure_chat`.
  · Leer: GET_NOTEBOOK fila[7] = [[objetivo, prompt?], [longitud]] — teng-lin
    `_web/rows/chat.py:unwrap_chat_settings` (live #1751). La web omite los valores por defecto
    como listas vacías ([[], []]). Una forma rara es drift y se avisa: en lectura-mezcla-escritura
    un valor por defecto silencioso borraría lo que el usuario quería conservar.
  · Renombrar fuente: UPDATE_SOURCE (b7Wfje) [None, [id], [[[título]]]] — coinciden ambos.
"""
from __future__ import annotations

from typing import Any

from .base import TransportError

GOALS = {"default": 1, "custom": 2, "learning_guide": 3}
LENGTHS = {"default": 1, "longer": 4, "shorter": 5}
_GOAL_NAMES = {v: k for k, v in GOALS.items()}
_LENGTH_NAMES = {v: k for k, v in LENGTHS.items()}
MAX_CUSTOM_PROMPT = 10_000
_SETTINGS_POS = 7


def _code(child: Any, what: str) -> int | None:
    if child is None or child == []:
        return None                                   # omitido = por defecto
    if not isinstance(child, list) or not isinstance(child[0], int) or isinstance(child[0], bool):
        raise TransportError(f"Ajustes del chat: {what} con formato no reconocido (drift).",
                             retriable=False)
    return child[0]


def parse_chat_settings(nb_row: Any) -> dict[str, Any]:
    """Fila del notebook (GET_NOTEBOOK payload[0]) → {goal, response_length, custom_prompt}."""
    if not isinstance(nb_row, list):
        raise TransportError("Fila del notebook no es una lista (drift).", retriable=False)
    block = nb_row[_SETTINGS_POS] if len(nb_row) > _SETTINGS_POS else None
    if block is None:
        return {"goal": "default", "response_length": "default", "custom_prompt": None}
    if not isinstance(block, list) or len(block) < 2:
        raise TransportError("Ajustes del chat con formato no reconocido (drift).",
                             retriable=False)
    goal_code = _code(block[0], "objetivo")
    length_code = _code(block[1], "longitud")
    goal = _GOAL_NAMES.get(goal_code or 1)
    length = _LENGTH_NAMES.get(length_code or 1)
    if goal is None or length is None:
        raise TransportError(f"Código de ajustes desconocido (objetivo={goal_code}, "
                             f"longitud={length_code}) (drift).", retriable=False)
    prompt = None
    if goal == "custom" and isinstance(block[0], list) and len(block[0]) > 1 \
            and isinstance(block[0][1], str):
        prompt = block[0][1]
    return {"goal": goal, "response_length": length, "custom_prompt": prompt}


def build_configure_params(notebook_id: str, *, goal: str, response_length: str,
                           custom_prompt: str | None) -> list[Any]:
    if goal not in GOALS or response_length not in LENGTHS:
        raise ValueError(f"goal ∈ {sorted(GOALS)}, response_length ∈ {sorted(LENGTHS)}")
    if goal == "custom":
        if not custom_prompt or not custom_prompt.strip():
            raise ValueError("custom_prompt es obligatorio cuando goal='custom'")
        if len(custom_prompt) > MAX_CUSTOM_PROMPT:
            raise ValueError(f"custom_prompt supera {MAX_CUSTOM_PROMPT} caracteres")
        goal_array: list[Any] = [GOALS[goal], custom_prompt]
    else:
        goal_array = [GOALS[goal]]
    settings = [goal_array, [LENGTHS[response_length]]]
    return [notebook_id, [[None, None, None, None, None, None, None, settings]]]


def build_rename_source_params(source_id: str, title: str) -> list[Any]:
    return [None, [source_id], [[[title]]]]
