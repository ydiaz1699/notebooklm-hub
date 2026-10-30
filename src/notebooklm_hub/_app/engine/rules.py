"""Reglas deterministas: foto del cuaderno (+ la anterior) → qué receta proponer y por qué.

Tabla de docs/design/recetas.md §3. Función PURA (sin red, sin LLM): mismas entradas, misma
salida; por eso es comprobable y explicable ("propongo R3 porque hay 14 fuentes sin etiquetas").
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Thresholds:
    few_sources: int = 2          # ≤ esto → buscar fuentes (R2)
    many_sources: int = 10        # ≥ esto sin etiquetas → método de las 3 notas (R3)

    @classmethod
    def from_env(cls) -> Thresholds:
        def _int(name: str, default: int) -> int:
            try:
                return int(os.environ.get(name, default))
            except ValueError:
                return default
        return cls(few_sources=_int("NOTEBOOKLM_HUB_FEW_SOURCES", cls.few_sources),
                   many_sources=_int("NOTEBOOKLM_HUB_MANY_SOURCES", cls.many_sources))


def _finding(recipe: str, reason: str, priority: int, **scope: Any) -> dict[str, Any]:
    return {"recipe": recipe, "reason": reason, "priority": priority, "scope": scope}


def evaluate(snap: dict[str, Any], previous: dict[str, Any] | None = None,
             th: Thresholds | None = None) -> list[dict[str, Any]]:
    """Hallazgos ordenados por prioridad (1 = lo primero que conviene hacer)."""
    th = th or Thresholds()
    n = snap["original_count"]
    labels = snap["labels"]
    out: list[dict[str, Any]] = []

    if n <= th.few_sources:
        out.append(_finding("buscar_fuentes",
                            f"El cuaderno tiene {n} fuente(s): poco material con el que trabajar.",
                            1))
    if n == 1 and not snap["map_source_id"]:
        out.append(_finding("mapa_de_cobertura",
                            "Hay un único documento y no tiene MAPA de cobertura: si es largo, el "
                            "mapa mejora mucho la precisión de las respuestas.", 2))

    if not labels and n >= th.many_sources:
        out.append(_finding("metodo_3_notas",
                            f"{n} fuentes mezcladas sin categorías: conviene agruparlas y crear "
                            "las 3 notas por categoría.", 1, labels="all"))
    elif labels:
        if snap["unlabeled_original_ids"]:
            out.append(_finding("metodo_3_notas",
                                f"{len(snap['unlabeled_original_ids'])} fuente(s) nueva(s) sin "
                                "categoría.", 2, labels="unlabeled",
                                source_ids=snap["unlabeled_original_ids"]))
        pending = [lb["name"] for lb in labels if lb["original_source_ids"] and not lb["complete"]]
        if pending:
            out.append(_finding("metodo_3_notas",
                                f"Categorías sin sus 3 notas: {', '.join(pending)}.", 2,
                                labels=pending))
        if previous:
            before = {lb["id"]: lb for lb in previous.get("labels", [])}
            stale = [lb["name"] for lb in labels
                     if lb["complete"] and lb["id"] in before
                     and before[lb["id"]]["fingerprint"] != lb["fingerprint"]]
            if stale:
                out.append(_finding("metodo_3_notas",
                                    "Cambiaron las fuentes de categorías ya procesadas; sus notas "
                                    f"están desactualizadas: {', '.join(stale)}.", 2,
                                    labels=stale, refresh=True))

    if not snap["chat"]["customized"]:
        out.append(_finding("configurar_chat",
                            "El chat no está personalizado (objetivo, tono, prohibiciones).", 3))

    return sorted(out, key=lambda f: f["priority"])
