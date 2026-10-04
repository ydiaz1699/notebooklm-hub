"""Cascada de transporte — ÚNICO sitio del orden y el fallback.

Prueba Android gRPC → batchexecute → browser. Un TransportError cae al siguiente nivel;
cualquier otra excepción (fallo de dominio) se propaga sin caer.

Este archivo es el que se toca para cambiar la estrategia de fallback. Ver docs/transport/README.md.

Fase 0: estructura y lógica de orden. Los transportes concretos se enchufan en Fase 1-2.
"""
from __future__ import annotations

import os
from typing import Any, Sequence

from .base import Transport, TransportError, TransportResult

# Orden de preferencia por defecto. Configurable con NOTEBOOKLM_HUB_BACKEND.
_DEFAULT_ORDER = ("android", "web", "browser")


class Cascade:
    def __init__(self, transports: Sequence[Transport]) -> None:
        # transports llega ya ordenado o se reordena según preferencia
        self._by_name = {t.name: t for t in transports}

    def _order(self) -> tuple[str, ...]:
        forced = os.environ.get("NOTEBOOKLM_HUB_BACKEND", "cascade").strip().lower()
        if forced in self._by_name:          # backend forzado: no hay fallback
            return (forced,)
        return _DEFAULT_ORDER

    async def call(self, operation: str, **params: Any) -> TransportResult:
        last_error: TransportError | None = None
        tried: list[str] = []
        for name in self._order():
            transport = self._by_name.get(name)
            if transport is None or not transport.available():
                continue
            tried.append(name)
            try:
                return await transport.call(operation, **params)
            except TransportError as exc:    # fallo de transporte → siguiente nivel
                last_error = exc
                continue
            # Nota: un fallo de DOMINIO no es TransportError → se propaga aquí sin caer.
        raise TransportError(
            f"Todos los transportes fallaron para '{operation}' (probados: {tried or 'ninguno disponible'})",
            retriable=bool(last_error and last_error.retriable),
        )
