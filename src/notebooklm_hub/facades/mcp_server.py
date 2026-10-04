"""Fachada MCP — expone las tools auto-descubiertas a clientes MCP (Kiro, Claude, Cursor…).

Fina a propósito: toma cada ToolSpec del registry y la registra en FastMCP. No contiene lógica de
negocio. Las destructivas se proyectan con el hint correspondiente para que el cliente pida `ask`.

Fase 0: esqueleto que ilustra el patrón. Requiere `fastmcp` (extra, Fase 1).
"""
from __future__ import annotations

from ..tools.registry import discover_tools


def build_server():  # -> FastMCP
    try:
        from fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Instala el extra MCP: uv pip install '.[mcp]'") from exc

    server = FastMCP("notebooklm-hub")
    for tool in discover_tools().values():
        # En Fase 1: envolver tool.run inyectando core/client y, si tool.destructive,
        # exigir confirm/preview antes de ejecutar. Aquí solo se muestra el cableado.
        server.add_tool(tool.run, name=tool.name, description=tool.description)
    return server


def main() -> None:  # entry point: nlmhub-mcp
    build_server().run()  # stdio por defecto
