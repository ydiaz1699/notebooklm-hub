"""Protocolo de investigación (Fast / Deep Research) — funciones PURAS, sin red.

"El mejor de los 7" (docs/provenance/capabilities-matrix.md §4bis). Base teng-lin
(`_web/research.py`, `_web/rows/research.py`, `_web/rows/research_task.py`, `_types/research.py`);
de jacob-bd (`core/research.py`) se toma la reconciliación de la importación por diferencia de IDs.

  START_FAST_RESEARCH  Ljjv0c  [[consulta, tipo], None, 1, nb]
  START_DEEP_RESEARCH  QA9ei   [None, [1], [consulta, tipo], 5, nb]        (solo web)
     → [task_id, report_id?]
  POLL_RESEARCH        e3bVqc  [None, None, nb]
     → [[tarea, ...]] o [tarea, ...];  tarea = [task_id, info, ...]
       info[1] = [consulta, tipo] · info[3] = [fuentes, resumen] · info[4] = estado
       fuente = [url, título, pista, tipo_resultado, _, _, [texto, tipo_contenido], _, ordinal]
       (informe de Deep: url None, contenido tipo 3 = markdown del informe)
  IMPORT_RESEARCH      LBwxtb  [None, [1], task_id, nb, [entrada, ...]]
     web:     [None, None, [url, título], None×7, 2]
     informe: [None, [título, markdown], None, 3, None×6, 3]
"""
from __future__ import annotations

from typing import Any

from .base import TransportError

SOURCE_TYPE_WEB = 1
RESULT_WEB, RESULT_REPORT = 1, 5
_REPORT_CONTENT_KIND = 3

# Códigos de estado (teng-lin _types/research.py). jacob-bd trata 3 y 4 como "en curso".
STATUS = {1: "in_progress", 2: "completed", 3: "no_results", 4: "cancelled", 6: "completed"}


def build_start_params(notebook_id: str, query: str, mode: str) -> tuple[str, list[Any]]:
    if mode == "fast":
        return "START_FAST_RESEARCH", [[query, SOURCE_TYPE_WEB], None, 1, notebook_id]
    if mode == "deep":
        return "START_DEEP_RESEARCH", [None, [1], [query, SOURCE_TYPE_WEB], 5, notebook_id]
    raise ValueError(f"mode debe ser 'fast' o 'deep', no {mode!r}")


def parse_start(payload: Any) -> dict[str, Any]:
    """[task_id, report_id?] → dict. Sin task_id = no se creó la tarea (teng-lin #1342)."""
    task_id = payload[0] if isinstance(payload, list) and payload else None
    if not isinstance(task_id, str) or not task_id:
        raise TransportError("NotebookLM no creó la investigación (respuesta sin task_id). "
                             "Puede que Deep Research no esté disponible en esta cuenta.",
                             retriable=False)
    report_id = payload[1] if len(payload) > 1 and isinstance(payload[1], str) else None
    return {"task_id": task_id, "report_id": report_id}


def _status(code: Any) -> str:
    if isinstance(code, bool) or not isinstance(code, int):
        return "in_progress"            # aún sin estado (teng-lin: None → in_progress)
    return STATUS.get(code, "failed")


def _parse_result(src: Any, index: int) -> dict[str, Any] | None:
    if not isinstance(src, list) or not src:
        return None
    url = src[0] if isinstance(src[0], str) else None
    title_slot = src[1] if len(src) > 1 else None
    rtype = src[3] if len(src) > 3 and isinstance(src[3], int) \
        and not isinstance(src[3], bool) else None
    title, report = "", ""
    if isinstance(title_slot, list) and len(title_slot) >= 2 \
            and all(isinstance(x, str) for x in title_slot[:2]):
        title, report = title_slot[0], title_slot[1]           # forma compatible [t, md]
    elif isinstance(title_slot, str):
        title = title_slot
    block = src[6] if len(src) > 6 and isinstance(src[6], list) else None
    if not report and block and len(block) > 1 and type(block[1]) is int \
            and block[1] == _REPORT_CONTENT_KIND and isinstance(block[0], str):
        report = block[0]
    if url is None and (report or rtype == RESULT_REPORT):
        kind = "report"
    else:
        kind = "web"
    if not (url or title or report):
        return None
    return {"index": index, "kind": kind, "url": url, "title": title or (url or "Informe"),
            "report_markdown": report or None}


def _unwrap_tasks(payload: Any) -> list[Any]:
    if not isinstance(payload, list) or not payload:
        return []
    first = payload[0]
    if isinstance(first, list) and first and isinstance(first[0], list):
        return first
    return payload


def parse_poll(payload: Any) -> list[dict[str, Any]]:
    """POLL_RESEARCH → tareas. Una tarea mal formada se salta (las demás siguen valiendo)."""
    tasks = []
    for task in _unwrap_tasks(payload):
        if not (isinstance(task, list) and len(task) > 1 and isinstance(task[0], str)
                and isinstance(task[1], list)):
            continue
        info = task[1]
        query_info = info[1] if len(info) > 1 and isinstance(info[1], list) else []
        bundle = info[3] if len(info) > 3 and isinstance(info[3], list) else []
        raw_sources = bundle[0] if bundle and isinstance(bundle[0], list) else []
        summary = bundle[1] if len(bundle) > 1 and isinstance(bundle[1], str) else ""
        results = [r for r in (_parse_result(s, i) for i, s in enumerate(raw_sources)) if r]
        tasks.append({
            "task_id": task[0],
            "query": query_info[0] if query_info and isinstance(query_info[0], str) else "",
            "status": _status(info[4] if len(info) > 4 else None),
            "status_code": info[4] if len(info) > 4 and isinstance(info[4], int) else None,
            "summary": summary,
            "results": results,
        })
    return tasks


def build_import_entries(results: list[dict[str, Any]]) -> list[list[Any]]:
    entries = []
    for r in results:
        if r["kind"] == "report":
            if not r.get("report_markdown"):
                continue                 # informe sin contenido: nada que importar
            entries.append([None, [r["title"], r["report_markdown"]], None, 3,
                            None, None, None, None, None, None, 3])
        elif r.get("url"):
            entries.append([None, None, [r["url"], r["title"]],
                            None, None, None, None, None, None, None, 2])
    return entries


def build_import_params(notebook_id: str, task_id: str, entries: list[list[Any]]) -> list[Any]:
    return [None, [1], task_id, notebook_id, entries]


def parse_import(payload: Any) -> list[dict[str, Any]]:
    """Filas importadas [[id], título] (envuelta o plana) → [{id, title}]."""
    if not isinstance(payload, list) or not payload:
        return []
    rows = payload
    first = payload[0]
    if isinstance(first, list) and first and isinstance(first[0], list) \
            and first[0] and isinstance(first[0][0], list):
        rows = first
    out = []
    for row in rows:
        if isinstance(row, list) and row and isinstance(row[0], list) and row[0] \
                and isinstance(row[0][0], str):
            out.append({"id": row[0][0],
                        "title": row[1] if len(row) > 1 and isinstance(row[1], str) else ""})
    return out
