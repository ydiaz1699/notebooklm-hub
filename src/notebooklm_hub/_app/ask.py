"""Lógica neutral del verbo `ask`. No sabe de MCP/REST/CLI.

Patrón de teng-lin (ADR-0021): Request/Result + build_plan + execute. En Fase 1 es simple
(un solo paso), pero deja el molde para los verbos complejos (studio/research) de fases futuras.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .notebooks import resolve_notebook_id


@dataclass(frozen=True)
class AskRequest:
    notebook: str                      # nombre o ID (se resuelve en execute_ask)
    question: str
    source_ids: list[str] | None = None


@dataclass(frozen=True)
class AskResult:
    answer: str
    conversation_id: str
    notebook_id: str


def build_ask_plan(req: AskRequest) -> AskRequest:
    """Valida la entrada. Lanza ValueError (lo clasifica _app/errors) si es inválida."""
    if not req.notebook or not req.notebook.strip():
        raise ValueError("notebook es obligatorio")
    if not req.question or not req.question.strip():
        raise ValueError("question es obligatorio")
    return req


async def execute_ask(plan: AskRequest, client: Any) -> AskResult:
    # Acepta nombre o ID; un ID no hace llamada extra. Ambiguo/inexistente → error de dominio.
    notebook_id = await resolve_notebook_id(client, plan.notebook)
    data = await client.ask(notebook_id, plan.question, plan.source_ids)
    return AskResult(
        answer=data.get("answer", ""),
        conversation_id=data.get("conversation_id", ""),
        notebook_id=data.get("notebook_id", notebook_id),
    )
