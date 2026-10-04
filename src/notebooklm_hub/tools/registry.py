"""Registro de tools — auto-descubre los archivos de este paquete.

Cada archivo `tools/<algo>.py` que defina un objeto `TOOL` (ver `_template.py`) se publica
automáticamente a las tres fachadas (MCP, REST, CLI). Añadir una tool = añadir un archivo; no se
toca nada aquí ni en las fachadas.
"""
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    params: dict[str, Any]          # esquema de parámetros (JSON-schema-like)
    run: Callable[..., Any]         # run(client, **params)
    destructive: bool = False       # si True, el núcleo exige confirm + devuelve preview


def discover_tools() -> dict[str, ToolSpec]:
    """Importa cada módulo del paquete `tools` y recoge su `TOOL`."""
    import notebooklm_hub.tools as pkg

    found: dict[str, ToolSpec] = {}
    for mod in pkgutil.iter_modules(pkg.__path__):
        if mod.name.startswith("_") or mod.name == "registry":
            continue
        module = importlib.import_module(f"notebooklm_hub.tools.{mod.name}")
        tool = getattr(module, "TOOL", None)
        if isinstance(tool, ToolSpec):
            found[tool.name] = tool
    return found
