"""Fachada MCP — expone las tools auto-descubiertas a clientes MCP (Kiro, Claude, Cursor…).

Fina a propósito: por cada ToolSpec del registry registra en FastMCP una función que inyecta el
core/client y llama a tool.run. No contiene lógica de negocio.

Requiere el extra MCP: uv pip install '.[mcp]'
"""
from __future__ import annotations

import inspect
from typing import Any

from ..core.client import Client
from ..tools.registry import ToolSpec, discover_tools

# Mapa mínimo del tipo declarado en params → anotación Python (para el schema MCP).
_PY_TYPE = {"string": str, "integer": int, "number": float,
            "boolean": bool, "array": list, "object": dict}


def _make_handler(tool: ToolSpec, client: Client):
    """Crea un handler con firma EXPLÍCITA (FastMCP no admite **kwargs: necesita el schema)."""
    async def _call(**params: Any) -> Any:
        if tool.destructive and not params.get("confirm"):
            return {"status": "needs_confirmation",
                    "preview": f"'{tool.name}' es destructiva; reenvía con confirm=true."}
        # quita los None de parámetros opcionales no pasados
        clean = {k: v for k, v in params.items() if v is not None}
        return await tool.run(client, **clean)

    # Construye la firma a partir de tool.params para que FastMCP genere el input schema.
    sig_params = []
    for pname, spec in tool.params.items():
        ann = _PY_TYPE.get(spec.get("type", "string"), str)
        if spec.get("required"):
            default = inspect.Parameter.empty
        else:
            default = None
            ann = ann | None  # type: ignore[operator]
        sig_params.append(inspect.Parameter(
            pname, inspect.Parameter.KEYWORD_ONLY, default=default, annotation=ann))
    if tool.destructive:
        sig_params.append(inspect.Parameter(
            "confirm", inspect.Parameter.KEYWORD_ONLY, default=False, annotation=bool))

    _call.__signature__ = inspect.Signature(sig_params)  # type: ignore[attr-defined]
    # Pydantic/FastMCP leen type hints vía __annotations__, no solo la firma.
    _call.__annotations__ = {p.name: p.annotation for p in sig_params} | {"return": Any}
    _call.__name__ = tool.name
    _call.__doc__ = tool.description
    return _call


def build_server(client: Client | None = None):  # -> FastMCP
    try:
        from fastmcp import FastMCP
        from fastmcp.tools import Tool
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Instala el extra MCP: uv pip install '.[mcp]'") from exc

    client = client or Client()
    server = FastMCP("notebooklm-hub")
    for tool in discover_tools().values():
        server.add_tool(Tool.from_function(
            _make_handler(tool, client), name=tool.name, description=tool.description))
    return server


def main() -> None:  # entry point: nlmhub-mcp
    build_server().run()  # stdio por defecto
