"""PLANTILLA de tool — copia este archivo para crear una capacidad nueva.

Pasos (ver CONTRIBUTING.md):
  1. copia a tools/<mi_tool>.py
  2. rellena NAME, DESCRIPTION, PARAMS y run()
  3. si es destructiva, pon destructive=True en el ToolSpec
Nada más: registry.py la descubre y aparece en MCP, REST y CLI.
"""
from __future__ import annotations

from typing import Any

from .registry import ToolSpec

NAME = "ejemplo_tool"
DESCRIPTION = "Describe en una frase qué hace y cuándo usarla."

# Esquema de parámetros (estilo JSON-schema simplificado). Las fachadas lo traducen a su formato.
PARAMS: dict[str, Any] = {
    "notebook": {"type": "string", "required": True, "desc": "Nombre o ID del notebook."},
    # "confirm": {"type": "boolean", "default": False}  # lo añade el núcleo si destructive=True
}


async def run(client: Any, **params: Any) -> dict[str, Any]:
    """Lógica de la tool. `client` es core/client.py (resuelve transporte por detrás).

    Devuelve un dict serializable. No imprime, no renderiza: eso es trabajo de la fachada.
    """
    raise NotImplementedError("plantilla — implementar en la tool real")


TOOL = ToolSpec(
    name=NAME,
    description=DESCRIPTION,
    params=PARAMS,
    run=run,
    destructive=False,
)
