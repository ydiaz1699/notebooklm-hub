"""Clasificación central de errores — ÚNICO sitio que decide la *categoría* de un fallo.

Cada fachada proyecta la categoría a su propio vocabulario:
  - MCP   → code del manifiesto
  - REST  → HTTP status + {"error": {"category", "message"}}
  - CLI   → código de string + exit code
Patrón destilado de teng-lin (ADR-0019/0021). Fase 0: categorías y clasificador base.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Category(str, Enum):
    CONFIG = "CONFIG"                   # falta auth/parámetro de entorno
    DEPENDENCY = "DEPENDENCY"           # falta una dependencia opcional (browser, grpc…)
    NOT_FOUND = "NOT_FOUND"             # notebook/source/artifact inexistente
    AMBIGUOUS = "AMBIGUOUS"             # nombre que resuelve a varios → no adivinar
    NOTEBOOK_LIMIT = "NOTEBOOK_LIMIT"   # cuota/límite de la cuenta
    ARTIFACT_TIMEOUT = "ARTIFACT_TIMEOUT"
    SOURCE_ADD = "SOURCE_ADD"
    SOURCE_MUTATION = "SOURCE_MUTATION"
    TRANSPORT = "TRANSPORT"             # todos los transportes fallaron
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"  # destructiva sin confirm → preview
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ClassifiedError:
    category: Category
    message: str
    retriable: bool = False


def classify(exc: Exception) -> ClassifiedError:
    """Mapea una excepción a una categoría neutral. Único sitio de la decisión de categoría."""
    from ..core.auth import AuthError
    from ..core.transport.base import TransportError

    if isinstance(exc, TransportError):
        return ClassifiedError(Category.TRANSPORT, str(exc), retriable=exc.retriable)
    if isinstance(exc, AuthError):
        return ClassifiedError(Category.CONFIG, str(exc))
    if isinstance(exc, ValueError):
        return ClassifiedError(Category.CONFIG, str(exc))
    return ClassifiedError(Category.UNKNOWN, str(exc))
