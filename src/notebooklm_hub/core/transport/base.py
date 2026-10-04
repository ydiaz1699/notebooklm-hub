"""Contrato común de transporte.

Los tres transportes (android_grpc, batchexecute, browser) implementan esta interfaz, de modo que
`_app/` y las tools NUNCA saben cuál se usó. La cascada (`cascade.py`) prueba uno tras otro.

Fase 0: solo el contrato. Las implementaciones llegan en Fase 1-2 (ver docs/ROADMAP.md).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class TransportError(Exception):
    """Fallo *de transporte* (endpoint caído, red, método no disponible).

    Hace que la cascada caiga al siguiente nivel. NO usar para fallos de dominio
    (notebook inexistente, cuota agotada): esos se propagan sin caer.
    """

    def __init__(self, message: str, *, retriable: bool = True) -> None:
        super().__init__(message)
        self.retriable = retriable


@dataclass(frozen=True)
class TransportResult:
    """Respuesta cruda normalizada que devuelve cualquier transporte."""

    data: Any
    backend: str  # "android" | "web" | "browser" — de dónde salió


@runtime_checkable
class Transport(Protocol):
    """Interfaz que todo transporte debe cumplir."""

    name: str  # "android" | "web" | "browser"

    def available(self) -> bool:
        """¿Está este transporte utilizable ahora (auth/deps presentes)?"""
        ...

    async def call(self, operation: str, **params: Any) -> TransportResult:
        """Ejecuta una operación de bajo nivel. Lanza TransportError si falla a nivel de transporte."""
        ...
