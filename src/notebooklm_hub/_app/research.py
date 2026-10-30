"""Lógica neutral de investigación (receta R2 · buscar fuentes con Deep Research).

Flujo asíncrono, sin bloquear (patrón teng-lin *_start → *_status → *_import):
  research_start  → task_id (Deep tarda ~5 min y trae ~40 fuentes + un informe)
  research_status → en curso / completada / sin resultados / cancelada / fallida + resultados
  research_import → importa los resultados elegidos (y el informe) como fuentes
"""
from __future__ import annotations

from typing import Any

from .errors import NotFoundError, NotReadyError
from .notebooks import resolve_notebook_id

MODES = {"deep": "~5 min, ~40 fuentes + informe (solo web)", "fast": "~30 s, ~10 fuentes"}
MAX_QUERY = 2_000        # prudente; el límite real no está documentado


async def start(client: Any, notebook: str, query: str, mode: str = "deep") -> dict[str, Any]:
    if not query or not query.strip():
        raise ValueError("query es obligatorio")
    if len(query) > MAX_QUERY:
        raise ValueError(f"query supera {MAX_QUERY} caracteres")
    if mode not in MODES:
        raise ValueError(f"mode debe ser uno de {sorted(MODES)}")
    nb_id = await resolve_notebook_id(client, notebook)
    started = await client.research_start(nb_id, query.strip(), mode)
    return {"notebook_id": nb_id, "task_id": started["task_id"], "mode": mode,
            "estimated": MODES[mode],
            "next": "consulta research_status con este task_id hasta status=completed"}


def _pick(tasks: list[dict[str, Any]], task_id: str | None) -> dict[str, Any]:
    if task_id:
        task = next((t for t in tasks if t["task_id"] == task_id), None)
        if task is None:
            raise NotFoundError(f"No hay ninguna investigación con task_id '{task_id}' en este "
                                "notebook.")
        return task
    if not tasks:
        raise NotFoundError("Este notebook no tiene investigaciones. Usa research_start.")
    return tasks[0]                                  # la más reciente


def _summary(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task["task_id"], "query": task["query"], "status": task["status"],
        "done": task["status"] != "in_progress", "summary": task["summary"],
        "result_count": len(task["results"]),
        "results": [{"index": r["index"], "kind": r["kind"], "title": r["title"],
                     "url": r["url"], "has_report": bool(r["report_markdown"])}
                    for r in task["results"]],
    }


async def status(client: Any, notebook: str, task_id: str | None = None) -> dict[str, Any]:
    nb_id = await resolve_notebook_id(client, notebook)
    return {"notebook_id": nb_id, **_summary(_pick(await client.research_poll(nb_id), task_id))}


async def import_results(client: Any, notebook: str, task_id: str, *,
                         indices: list[int] | None = None,
                         include_report: bool = True) -> dict[str, Any]:
    if not task_id or not task_id.strip():
        raise ValueError("task_id es obligatorio")
    nb_id = await resolve_notebook_id(client, notebook)
    task = _pick(await client.research_poll(nb_id), task_id)
    if task["status"] != "completed":
        raise NotReadyError(f"La investigación está '{task['status']}', no 'completed'. "
                            "Espera con research_status antes de importar.")
    results = task["results"]
    if indices is not None:
        valid = {r["index"] for r in results}
        bad = [i for i in indices if i not in valid]
        if bad:
            raise ValueError(f"Índices inexistentes: {bad}. Válidos: {sorted(valid)}")
        results = [r for r in results if r["index"] in set(indices)]
    if not include_report:
        results = [r for r in results if r["kind"] != "report"]
    # Idempotencia: no reimportar lo que ya está en el cuaderno con el mismo título
    # (el motor puede reintentar tras un corte sin duplicar fuentes).
    existing = {s["title"].strip() for s in
                ((await client.get_notebook(nb_id)) or {}).get("sources", [])}
    skipped = [r["title"] for r in results if r["title"].strip() in existing]
    results = [r for r in results if r["title"].strip() not in existing]
    if not results:
        return {"notebook_id": nb_id, "task_id": task_id, "imported": [], "skipped": skipped,
                "reconciled": False}
    out = await client.research_import(nb_id, task_id, results)
    return {"notebook_id": nb_id, "task_id": task_id, "imported": out["imported"],
            "skipped": skipped, "reconciled": out["reconciled"]}
