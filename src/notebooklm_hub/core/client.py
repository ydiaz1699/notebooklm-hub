"""Núcleo — API pública única. Une auth + transporte(s) en cascada.

Las tools y _app/ hablan SOLO con este cliente; nunca con los transportes directamente. Así, el día
que se añadan android_grpc y browser, las tools no cambian: solo se enchufan a la cascada aquí.

Fase 1: cascada con un único transporte (web/batchexecute). Fase 2 añade android y browser.
"""
from __future__ import annotations

import os
from typing import Any

from .auth import load_cookie_header
from .transport.base import TransportResult
from .transport.batchexecute import DEFAULT_HOST, BatchExecuteTransport
from .transport.cascade import Cascade


class Client:
    def __init__(self, *, cookie_header: str | None = None, host: str | None = None) -> None:
        cookies = cookie_header or load_cookie_header()
        host = host or os.environ.get("NOTEBOOKLM_HUB_HOST", DEFAULT_HOST)
        # Fase 1: solo transporte web. En Fase 2 la lista crece: [android, web, browser].
        self._cascade = Cascade([BatchExecuteTransport(cookies, host=host)])

    async def call(self, operation: str, **params: Any) -> TransportResult:
        return await self._cascade.call(operation, **params)

    # Operaciones de alto nivel (envoltura legible sobre call). Crecerán por fase.
    async def ask(self, notebook_id: str, question: str,
                  source_ids: list[str] | None = None,
                  conversation_id: str | None = None) -> dict[str, Any]:
        res = await self.call("ask", notebook_id=notebook_id, question=question,
                              source_ids=source_ids, conversation_id=conversation_id)
        return res.data

    async def list_notebooks(self) -> list[dict[str, Any]]:
        return (await self.call("list_notebooks")).data

    async def get_notebook(self, notebook_id: str) -> dict[str, Any] | None:
        return (await self.call("get_notebook", notebook_id=notebook_id)).data

    async def list_labels(self, notebook_id: str) -> list[dict[str, Any]]:
        return (await self.call("list_labels", notebook_id=notebook_id)).data

    async def generate_labels(self, notebook_id: str, scope: str) -> list[dict[str, Any]]:
        return (await self.call("generate_labels", notebook_id=notebook_id, scope=scope)).data

    async def assign_source_to_label(self, notebook_id: str, label_id: str,
                                     source_id: str) -> dict[str, Any]:
        return (await self.call("assign_source_to_label", notebook_id=notebook_id,
                                label_id=label_id, source_id=source_id)).data

    async def get_chat_settings(self, notebook_id: str) -> dict[str, Any] | None:
        return (await self.call("get_chat_settings", notebook_id=notebook_id)).data

    async def configure_chat(self, notebook_id: str, *, goal: str, response_length: str,
                             custom_prompt: str | None) -> dict[str, Any]:
        return (await self.call("configure_chat", notebook_id=notebook_id, goal=goal,
                                response_length=response_length,
                                custom_prompt=custom_prompt)).data

    async def rename_source(self, notebook_id: str, source_id: str, title: str) -> dict[str, Any]:
        return (await self.call("rename_source", notebook_id=notebook_id, source_id=source_id,
                                title=title)).data

    async def add_text_source(self, notebook_id: str, title: str,
                              content: str) -> dict[str, Any]:
        return (await self.call("add_text_source", notebook_id=notebook_id, title=title,
                                content=content)).data
