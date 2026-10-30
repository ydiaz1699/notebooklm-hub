"""Protocolo del chat web (query streamed) — funciones PURAS, sin red, unit-testables.

Decisiones "el mejor de los 7" (detalle en docs/provenance/capabilities-matrix.md §4bis):
la base es teng-lin (`_web/params/chat_stream.py`, `_web/rows/chat_stream.py`, `rows/chat.py`,
`rows/documents.py`), por ser la única verificada en vivo para cada detalle; jacob-bd y roomi
usan una variante anterior (5 campos, UUID inventado, "la más larga gana").

Forma de un fragmento del stream (`wrb.fr` → inner JSON → `inner[0]` = fila de respuesta):
  first[0] texto · first[2] = [session_id, turn_id, turn_code] · first[4] bloque de tipo:
  first[4][4] == 1 → es respuesta (no "pensando") · first[4][3] = citas
  inner[4] = isFinalResponse
Cita: [chunk_block, detalle]; detalle[2] score · detalle[4][0] elementos del fragmento ·
  detalle[5] contiene el UUID de la fuente.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

from .base import RpcRefusedError, TransportError

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)

# Status gRPC que el chat devuelve en item[5] al rechazar (teng-lin #1472).
_CHAT_STATUS = {3: "INVALID_ARGUMENT", 5: "NOT_FOUND", 7: "PERMISSION_DENIED",
                8: "RESOURCE_EXHAUSTED", 9: "FAILED_PRECONDITION"}


# --------------------------------------------------------------------------- petición
def build_query_params(*, notebook_id: str, question: str, source_ids: list[str],
                       history: list[Any] | None, conversation_id: str | None) -> list[Any]:
    """Los 9 campos que manda la web hoy (teng-lin build_streaming_chat_request).

    conversation_id=None → el servidor continúa la conversación actual del notebook (o la crea),
    igual que la web; así el chat aparece en el historial de NotebookLM. NO inventar un UUID:
    teng-lin #659 demostró que un id inventado crea turnos "fantasma" que el servidor no guarda.
    """
    return [
        [[[sid]] for sid in source_ids],   # cada fuente con 2 niveles internos: [[[id]]]
        question,
        history,                           # None, o [[respuesta,None,2],[pregunta,None,1],...]
        [2, None, [1], [1]],
        conversation_id,
        None,
        None,
        notebook_id,
        1,
    ]


def build_history(turns: list[tuple[str, str]]) -> list[Any] | None:
    """Turnos (pregunta, respuesta) → historial del protocolo (teng-lin _build_history_from_turns)."""
    if not turns:
        return None
    history: list[Any] = []
    for question, answer in turns:
        history.append([answer, None, 2])
        history.append([question, None, 1])
    return history


def unwrap_last_conversation_id(raw: Any) -> str | None:
    """Payload de hPTbtc ([[[conv_id]]]) → id real de la conversación, o None si aún no hay."""
    if not isinstance(raw, list):
        return None
    for group in raw:
        for row in group if isinstance(group, list) else []:
            if isinstance(row, list) and row and isinstance(row[0], str) and row[0]:
                return row[0]
    return None


# --------------------------------------------------------------------------- citas
def _find_uuid(node: Any, depth: int = 0) -> str | None:
    """Primer UUID dentro de una estructura anidada (teng-lin extract_uuid_from_nested)."""
    if depth > 10:
        return None
    if isinstance(node, str):
        return node if _UUID_RE.match(node) else None
    if isinstance(node, list):
        for item in node:
            found = _find_uuid(item, depth + 1)
            if found:
                return found
    return None


def _index(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _fragment_text(detail: list[Any]) -> tuple[str | None, int | None, int | None]:
    """Texto citado y su rango en la fuente.

    Elementos en detalle[4][0] (teng-lin #2120: bajar solo a detalle[4] truncaba el texto).
    Elemento estructural: [inicio, fin, párrafo, _, tabla, ...]; párrafo: [[elem, ...], estilo];
    elemento de párrafo: [inicio, fin, [contenido, estilo]]. Las tablas se marcan "[tabla]".
    """
    fragment = detail[4] if len(detail) > 4 and isinstance(detail[4], list) else None
    elements = fragment[0] if fragment and isinstance(fragment[0], list) else None
    if not elements:
        return None, None, None
    spans: list[tuple[int, str]] = []
    starts, ends = [], []
    for el in elements:
        if not isinstance(el, list) or len(el) < 2:
            continue
        s, e = _index(el[0]), _index(el[1])
        if s is None or e is None or e < s:
            continue
        starts.append(s)
        ends.append(e)
        paragraph = el[2] if len(el) > 2 and isinstance(el[2], list) else None
        if paragraph is None:
            if len(el) > 4 and el[4] is not None:
                spans.append((s, "[tabla]"))
            continue
        for pe in paragraph[0] if paragraph and isinstance(paragraph[0], list) else []:
            if isinstance(pe, list) and len(pe) > 2 and isinstance(pe[2], list) and pe[2]:
                content = pe[2][0]
                ps = _index(pe[0])
                if isinstance(content, str) and ps is not None:
                    spans.append((ps, content))
    if not starts:
        return None, None, None
    text = "".join(t for _, t in sorted(spans, key=lambda x: x[0])) or None
    return text, min(starts), max(ends)


def parse_citations(type_block: list[Any]) -> list[dict[str, Any]]:
    """first[4][3] → referencias. El número de cita es la posición (1-based); una cita rota deja
    hueco para que los marcadores [N] del texto nunca apunten a la fuente equivocada."""
    raw = type_block[3] if len(type_block) > 3 else None
    if not isinstance(raw, list):
        return []
    refs: list[dict[str, Any]] = []
    for number, cite in enumerate(raw, start=1):
        if not isinstance(cite, list) or len(cite) < 2 or not isinstance(cite[1], list):
            continue
        detail = cite[1]
        source_id = _find_uuid(detail[5]) if len(detail) > 5 else None
        if not source_id:
            continue
        text, start, end = _fragment_text(detail)
        score = detail[2] if len(detail) > 2 else None
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not (
                math.isfinite(score) and 0.0 <= score <= 1.0):
            score = None
        refs.append({"citation_number": number, "source_id": source_id, "cited_text": text,
                     "start_char": start, "end_char": end,
                     "score": float(score) if score is not None else None})
    return refs


# --------------------------------------------------------------------------- respuesta
def _is_rate_limit(payload: list[Any]) -> bool:
    entries = payload[2] if len(payload) > 2 and isinstance(payload[2], list) else []
    return any(isinstance(e, list) and e and isinstance(e[0], str)
               and "UserDisplayableError" in e[0] for e in entries)


def _reject(payload: Any) -> None:
    """item[5] de un wrb.fr sin respuesta → negativa de dominio (nunca se silencia)."""
    payload = payload if isinstance(payload, list) else []
    if _is_rate_limit(payload):
        raise RpcRefusedError("NotebookLM limitó el chat (cuota o demasiadas peticiones). "
                              "Espera unos segundos y reintenta.", status=8,
                              label="RESOURCE_EXHAUSTED")
    status = payload[0] if payload and isinstance(payload[0], int) else None
    label = _CHAT_STATUS.get(status, f"status {status}")
    hint = (" Suele ser una pregunta demasiado larga; acórtala." if status == 3 else "")
    raise RpcRefusedError(f"NotebookLM rechazó la pregunta ({label}).{hint}",
                          status=status if status is not None else -1, label=label)


def parse_chat_stream(text: str) -> dict[str, Any]:
    """Respuesta streamed → {answer, references, turn_key}. Pura.

    Elección de la respuesta (teng-lin #2122): gana el fragmento de respuesta que el servidor
    marca como FINAL; si ninguno, el fragmento de respuesta más largo; si no hay marcados, el
    texto más largo sin marcar. Contrato de fallos:
      · ningún fragmento decodificable + marco terminal "e" → cuota agotada (status 8)
      · ningún fragmento decodificable → drift (TransportError)
      · marco "er" → error del servidor · wrb.fr sin respuesta con item[5] → negativa
      · fragmentos válidos pero sin texto → respuesta vacía legítima
    """
    body = text.removeprefix(")]}'")
    best: dict[str, tuple[str, list]] = {}       # "final" | "marked" | "unmarked"
    turn_key: list[Any] | None = None
    parseable = 0
    saw_terminal = False

    def keep(slot: str, answer: str, refs: list, *, longest: bool) -> None:
        if not longest or len(answer) > len(best.get(slot, ("", []))[0]):
            best[slot] = (answer, refs)

    for raw in body.strip().split("\n"):
        line = raw.strip()
        if not line.startswith("["):
            continue                              # contadores de bytes y basura
        try:
            frame = json.loads(line)
        except json.JSONDecodeError:
            continue
        for item in frame if isinstance(frame, list) else []:
            if not isinstance(item, list) or len(item) < 2:
                continue
            tag = item[0]
            if tag == "er":
                code = item[2] if len(item) > 2 else None
                raise TransportError(f"El chat devolvió un marco de error (code {code!r}). "
                                     "Puede que el turno sí se guardara: revisa el historial.",
                                     retriable=False)
            if tag == "e":
                saw_terminal = True
                continue
            if tag != "wrb.fr" or len(item) < 3:
                continue
            if not isinstance(item[2], str):
                if len(item) > 5 and item[5] is not None:
                    _reject(item[5])
                continue
            try:
                inner = json.loads(item[2])
            except json.JSONDecodeError:
                continue
            parseable += 1
            if not isinstance(inner, list) or not inner:
                continue                          # heartbeat "[]"
            first = inner[0]
            if not isinstance(first, list):
                raise TransportError("Fila de respuesta del chat no es una lista (drift).",
                                     retriable=False)
            if len(first) > 2 and isinstance(first[2], list) and first[2] \
                    and isinstance(first[2][0], str):
                turn_key = first[2]
            answer = first[0] if first and isinstance(first[0], str) else ""
            if not answer:
                continue
            type_block = first[4] if len(first) > 4 and isinstance(first[4], list) else None
            is_answer = bool(type_block and len(type_block) > 4 and type_block[4] == 1)
            is_final = len(inner) > 4 and inner[4] is True
            if is_answer:
                refs = parse_citations(type_block)
                if is_final:
                    keep("final", answer, refs, longest=False)   # el último final gana
                keep("marked", answer, refs, longest=True)
            else:
                keep("unmarked", answer, [], longest=True)

    if parseable == 0:
        if saw_terminal:
            raise RpcRefusedError("NotebookLM cortó el chat sin respuesta: suele ser cuota "
                                  "agotada. Revisa el historial antes de reintentar.",
                                  status=8, label="RESOURCE_EXHAUSTED")
        raise TransportError("Respuesta del chat sin fragmentos reconocibles: vacía o Google "
                             "cambió el formato (drift).", retriable=False)
    for slot in ("final", "marked", "unmarked"):
        if slot in best:
            answer, refs = best[slot]
            break
    else:
        answer, refs = "", []
    return {
        "answer": answer,
        "references": refs,
        "turn_key": {"session_id": turn_key[0],
                     "turn_id": turn_key[1] if len(turn_key) > 1 else None} if turn_key else None,
    }
