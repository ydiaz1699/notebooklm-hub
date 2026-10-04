"""Fachada REST — expone las mismas tools por HTTP para n8n / Zapier / Make / curl / cron.

Fina a propósito: genera POST /tools/<name> por cada ToolSpec del registry, más /health. Mismo
núcleo que la fachada MCP → cero duplicación. Traduce errores de _app/errors a HTTP status.

Requiere el extra REST: uv pip install '.[rest]'
"""
from __future__ import annotations

from typing import Any

from .._app.errors import Category, classify
from ..core.client import Client
from ..tools.registry import ToolSpec, discover_tools

_HTTP_FOR = {
    Category.CONFIG: 400, Category.DEPENDENCY: 501, Category.NOT_FOUND: 404,
    Category.AMBIGUOUS: 409, Category.NOTEBOOK_LIMIT: 429, Category.ARTIFACT_TIMEOUT: 504,
    Category.TRANSPORT: 502, Category.NEEDS_CONFIRMATION: 428, Category.UNKNOWN: 500,
}


def build_app(client: Client | None = None):  # -> FastAPI
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Instala el extra REST: uv pip install '.[rest]'") from exc

    # Cliente perezoso: /health no debe fallar aunque no haya credenciales todavía.
    _client: dict[str, Client | None] = {"c": client}

    def get_client() -> Client:
        if _client["c"] is None:
            _client["c"] = Client()
        return _client["c"]

    app = FastAPI(title="notebooklm-hub", version="0.1.0")
    tools = discover_tools()

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "tools": sorted(tools)}

    def _register(tool: ToolSpec) -> None:
        @app.post(f"/tools/{tool.name}", name=tool.name)
        async def endpoint(body: dict[str, Any]) -> Any:
            try:
                if tool.destructive and not body.get("confirm"):
                    return JSONResponse(status_code=428, content={
                        "status": "needs_confirmation",
                        "preview": f"'{tool.name}' es destructiva; reenvía con confirm=true."})
                return await tool.run(get_client(), **body)
            except Exception as exc:  # noqa: BLE001 — se clasifica y se proyecta a HTTP
                ce = classify(exc)
                return JSONResponse(
                    status_code=_HTTP_FOR.get(ce.category, 500),
                    content={"error": {"category": ce.category.value, "message": ce.message,
                                       "retriable": ce.retriable}},
                )

    for t in tools.values():
        _register(t)
    return app


def main() -> None:  # entry point: nlmhub-rest
    import uvicorn

    uvicorn.run(build_app(), host="127.0.0.1", port=9420)
