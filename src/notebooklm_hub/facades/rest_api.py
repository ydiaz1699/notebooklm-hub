"""Fachada REST — expone las mismas tools por HTTP para n8n / Zapier / Make / curl / cron.

Fina a propósito: genera un endpoint POST /tools/<name> por cada ToolSpec del registry, más
/health. Mismo núcleo que la fachada MCP → cero duplicación de lógica. Las destructivas exigen
`confirm` en el body (lo valida el núcleo) y se proyectan a HTTP status.

Fase 0: esqueleto que ilustra el patrón. Requiere `fastapi`+`uvicorn` (extra, Fase 1).
"""
from __future__ import annotations

from ..tools.registry import discover_tools


def build_app():  # -> FastAPI
    try:
        from fastapi import FastAPI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Instala el extra REST: uv pip install '.[rest]'") from exc

    app = FastAPI(title="notebooklm-hub", version="0.0.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "tools": str(len(discover_tools()))}

    for tool in discover_tools().values():
        # En Fase 1: registrar app.post(f"/tools/{tool.name}") que valide params contra
        # tool.params, inyecte core/client, aplique confirm/preview si tool.destructive,
        # y traduzca errores de _app/errors.py a HTTP status.
        pass

    return app


def main() -> None:  # entry point: nlmhub-rest
    import uvicorn

    uvicorn.run(build_app(), host="127.0.0.1", port=9420)
