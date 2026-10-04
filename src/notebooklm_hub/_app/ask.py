"""Lógica neutral del verbo `ask`. No sabe de MCP/REST/CLI.

Patrón de teng-lin (ADR-0021): Request/Result + build_plan + execute. En Fase 1 es simple
(un solo paso), pero deja el molde para los verbos complejos (studio/research) de fases futuras.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AskRequest:
    notebook: str                      # nombre o ID (Fase 3 resuelve nombre→ID)
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
    data = await client.ask(plan.notebook, plan.question, plan.source_ids)
    return AskResult(
        answer=data.get("answer", ""),
        conversation_id=data.get("conversation_id", ""),
        notebook_id=data.get("notebook_id", plan.notebook),
    )
