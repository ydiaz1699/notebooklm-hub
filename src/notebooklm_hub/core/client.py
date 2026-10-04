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
from .transport.batchexecute import BatchExecuteTransport, DEFAULT_HOST
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
                  source_ids: list[str] | None = None) -> dict[str, Any]:
        res = await self.call("ask", notebook_id=notebook_id, question=question,
                              source_ids=source_ids)
        return res.data
