"""Lógica neutral del verbo `ask`. No sabe de MCP/REST/CLI.

Patrón de teng-lin (ADR-0021): Request/Result + build_plan + execute.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .notebooks import resolve_notebook_id


@dataclass(frozen=True)
class AskRequest:
    notebook: str                      # nombre o ID (se resuelve en execute_ask)
    question: str
    source_ids: list[str] | None = None
    conversation_id: str | None = None  # None = continuar la conversación actual del notebook


@dataclass(frozen=True)
class AskResult:
    answer: str
    conversation_id: str | None
    notebook_id: str
    references: list[dict[str, Any]] = field(default_factory=list)
    sources_used: list[str] = field(default_factory=list)
    is_follow_up: bool = False
    warning: str | None = None


def build_ask_plan(req: AskRequest) -> AskRequest:
    """Valida la entrada. Lanza ValueError (lo clasifica _app/errors) si es inválida."""
    if not req.notebook or not req.notebook.strip():
        raise ValueError("notebook es obligatorio")
    if not req.question or not req.question.strip():
        raise ValueError("question es obligatorio")
    if req.source_ids is not None and not all(isinstance(s, str) and s for s in req.source_ids):
        raise ValueError("source_ids debe ser una lista de IDs (texto)")
    return req


async def execute_ask(plan: AskRequest, client: Any) -> AskResult:
    # Acepta nombre o ID; un ID no hace llamada extra. Ambiguo/inexistente → error de dominio.
    notebook_id = await resolve_notebook_id(client, plan.notebook)
    data = await client.ask(notebook_id, plan.question, plan.source_ids,
                            conversation_id=plan.conversation_id)
    return AskResult(
        answer=data.get("answer", ""),
        conversation_id=data.get("conversation_id"),
        notebook_id=data.get("notebook_id", notebook_id),
        references=data.get("references", []),
        sources_used=data.get("sources_used", []),
        is_follow_up=bool(data.get("is_follow_up", False)),
        warning=data.get("warning"),
    )
