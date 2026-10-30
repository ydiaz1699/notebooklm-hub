"""Transporte batchexecute (Web RPC) — nivel 2 de la cascada.

Habla el MISMO protocolo interno que la web de NotebookLM: endpoints `batchexecute` y el endpoint
de query `GenerateFreeFormStreamed`. 10-100x más rápido que raspar el DOM e inmune a rediseños de UI.

El protocolo (endpoint, armado de `f.req`, prefijo anti-XSSI `)]}'`, parseo de envelopes `wrb.fr`,
drift vs refusal, bootstrap de tokens SNlM0e/FdrFJe/cfb2h) está destilado y portado de la impl de
referencia `roomi-fields/notebooklm-mcp` (MIT) y `jacob-bd/gemini-notebook-mcp-cli` (MIT), verificado
contra su código el 2026-10-04. Ver docs/transport/README.md. El chat (petición de 9 campos, respuesta
y citas) vive en web_chat.py, basado en teng-lin (la mejor de las 7 para esa parte).

⚠️ Google rota estos endpoints/ids sin aviso. Si un id deja de responder, parchear en caliente con
   NOTEBOOKLM_HUB_RPC_OVERRIDES='{"LIST_NOTEBOOKS":"<nuevo-id>"}'  (no hace falta release).

⚠️ VERIFICAR EN ENTORNO REAL: este archivo no se ha podido probar contra una cuenta de Google desde
   el sandbox de desarrollo (sin salida a Google ni credenciales). La forma del protocolo está
   portada fielmente de la fuente, pero el primer run real debe hacerse en el NAS/máquina del usuario.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from .base import RpcRefusedError, Transport, TransportError, TransportResult
from .web_chat import (
    build_history,
    build_query_params,
    parse_chat_stream,
    unwrap_last_conversation_id,
)

DEFAULT_HOST = "notebooklm.google.com"
BATCH_ENDPOINT = "/_/LabsTailwindUi/data/batchexecute"
QUERY_ENDPOINT = (
    "/_/LabsTailwindUi/data/"
    "google.internal.labs.tailwind.orchestration.v1."
    "LabsTailwindOrchestrationService/GenerateFreeFormStreamed"
)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

# IDs internos de batchexecute (interop facts, verificados contra roomi-fields rpc-ids.ts).
# Google los rota: override en caliente con NOTEBOOKLM_HUB_RPC_OVERRIDES.
_RPC_IDS = {
    "LIST_NOTEBOOKS": "wXbhsf",
    "GET_NOTEBOOK": "rLM1Ne",
    "CREATE_NOTEBOOK": "CCqFvf",
    "DELETE_NOTEBOOK": "WWINqb",
    "ADD_SOURCE": "izAoDd",
    "GET_SOURCE": "hizoJc",
    "DELETE_SOURCE": "tGMBJ",
    "GET_LAST_CONVERSATION_ID": "hPTbtc",   # teng-lin rpc/_identifiers.py
}

# Códigos gRPC estándar que el backend pone en el índice 5 del envelope al rechazar.
_GRPC_STATUS = {
    5: "NOT_FOUND", 7: "PERMISSION_DENIED", 8: "RESOURCE_EXHAUSTED",
    9: "FAILED_PRECONDITION", 12: "UNIMPLEMENTED", 16: "UNAUTHENTICATED",
}
# Status que son del CANAL (la cascada puede caer a otro transporte). El resto son de dominio.
_TRANSPORT_STATUSES = {12, 16}


def _resolve_rpc_id(name: str) -> str:
    overrides = os.environ.get("NOTEBOOKLM_HUB_RPC_OVERRIDES")
    if overrides:
        try:
            table = json.loads(overrides)
            if name in table:
                return str(table[name])
        except json.JSONDecodeError:
            pass
    if name not in _RPC_IDS:
        raise TransportError(f"RPC desconocido: {name}", retriable=False)
    return _RPC_IDS[name]


def parse_batchexecute(text: str, rpc_id: str) -> Any:
    """Parsea una respuesta batchexecute (anti-XSSI + chunked) y devuelve el payload interno.

    Pura (sin red), unit-testable. Devuelve None si el envelope existe pero está vacío;
    lanza TransportError si hay drift (ningún envelope para el id) o refusal (status gRPC).
    """
    body = text[4:] if text.startswith(")]}'") else text
    for raw in body.split("\n"):
        line = raw.strip()
        if not line or not line.startswith("["):
            continue
        try:
            chunk = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(chunk, list):
            continue
        for env in chunk:
            if not isinstance(env, list):
                continue
            if len(env) >= 2 and env[0] == "wrb.fr" and env[1] == rpc_id:
                if len(env) >= 3 and isinstance(env[2], str):
                    return json.loads(env[2])
                status = env[5][0] if len(env) >= 6 and isinstance(env[5], list) else None
                if isinstance(status, int) and status != 0:
                    label = _GRPC_STATUS.get(status, f"status {status}")
                    if status in _TRANSPORT_STATUSES:
                        # Problema del canal (sesión/método): otro transporte podría funcionar.
                        raise TransportError(f"NotebookLM rechazó la llamada: {label}",
                                             retriable=(status == 16))
                    # Negativa de dominio: repetir por otro transporte daría lo mismo.
                    raise RpcRefusedError(f"NotebookLM rechazó la llamada: {label}",
                                          status=status, label=label)
                return None
            if len(env) >= 1 and env[0] == "er":
                raise TransportError("batchexecute devolvió un envelope de error", retriable=False)
    # Ningún envelope para este id → el id casi seguro rotó (drift).
    raise TransportError(
        f"RPC id '{rpc_id}' no está en la respuesta (drift). "
        f"Parchea con NOTEBOOKLM_HUB_RPC_OVERRIDES.",
        retriable=False,
    )


def build_batch_body(rpc_id: str, rpc_params: Any, csrf: str = "") -> str:
    """Cuerpo form-urlencoded de batchexecute. Pura (sin red), unit-testable.

    Forma: f.req=[[[rpc_id, json(params), null, "generic"]]] (&at=csrf) + "&" final.
    JSON compacto (sin espacios) como Chrome. Portado de jacob-bd base._build_request_body (MIT).
    """
    params_json = json.dumps(rpc_params, separators=(",", ":"), ensure_ascii=False)
    f_req = json.dumps([[[rpc_id, params_json, None, "generic"]]],
                       separators=(",", ":"), ensure_ascii=False)
    parts = [f"f.req={quote(f_req, safe='')}"]
    if csrf:
        parts.append(f"at={quote(csrf, safe='')}")
    return "&".join(parts) + "&"


def _ts(value: Any) -> str | None:
    """[segundos, nanos] → ISO-8601 UTC. None si no tiene esa forma."""
    if isinstance(value, list) and value and isinstance(value[0], (int, float)):
        return datetime.fromtimestamp(value[0], tz=timezone.utc).isoformat()
    return None


# meta[0] = userRole de la cuenta que llama (proto OWNER/WRITER/READER). Fuente: teng-lin enums.
_ROLES = {1: "owner", 2: "editor", 3: "viewer"}


def parse_source_id(envelope: Any) -> str:
    """Envoltorio del id de fuente → id ("" si está mal formado). Pura.

    Tres variantes (teng-lin SourceRow.id, la más completa de los 7 repos):
      "id" (plano) · ["id"] (típico) · [None, True, ["id"]] (fuente de Google Drive).
    jacob-bd/ishandutta solo cubren las dos primeras → perdían las fuentes de Drive.
    """
    if envelope is None:
        return ""
    if not isinstance(envelope, list):
        return str(envelope)
    if envelope and envelope[0] is not None:
        return str(envelope[0])
    if len(envelope) > 2 and isinstance(envelope[2], list) and envelope[2]:
        return str(envelope[2][0]) if envelope[2][0] is not None else ""
    return ""


def _parse_notebook_entry(nb: Any) -> dict[str, Any] | None:
    """Una fila `Project` del protocolo → dict canónico. Pura.

    Posiciones (contrastadas teng-lin _web/rows/notebooks.py + jacob-bd notebooks.py):
      [0] título · [1] fuentes [[id_envelope, título, ...], ...] (None si vacío) · [2] id
      [3] emoji · [5] metadata: [0]=rol (1 owner/2 editor/3 viewer), [1]=compartido (jacob-bd),
          [5]=último visto [s,ns] (teng-lin, live-observed; NO "modificado"), [8]=creado [s,ns]
    """
    if not isinstance(nb, list) or len(nb) < 3 or not isinstance(nb[2], str) or not nb[2]:
        return None
    sources = []
    for src in nb[1] if isinstance(nb[1], list) else []:
        if isinstance(src, list) and src:
            sid = parse_source_id(src[0])
            if sid:
                title = src[1] if len(src) > 1 and isinstance(src[1], str) else "Untitled"
                sources.append({"id": sid, "title": title})
    meta = nb[5] if len(nb) > 5 and isinstance(nb[5], list) else []
    raw_role = meta[0] if meta else None
    role = _ROLES.get(raw_role) if isinstance(raw_role, int) and not isinstance(
        raw_role, bool) else None
    # Google a veces antepone "thought\n" al título (teng-lin decode_notebook).
    title = nb[0].replace("thought\n", "").strip() if isinstance(nb[0], str) else ""
    return {
        "id": nb[2],
        "title": title or "Untitled",
        "emoji": nb[3] if len(nb) > 3 and isinstance(nb[3], str) else None,
        "source_count": len(sources),
        "sources": sources,
        "role": role,
        "is_owned": role == "owner" if role else None,
        "is_shared": bool(meta[1]) if len(meta) > 1 else None,
        "last_viewed_at": _ts(meta[5]) if len(meta) > 5 else None,
        "created_at": _ts(meta[8]) if len(meta) > 8 else None,
    }


def parse_notebook_list(payload: Any) -> list[dict[str, Any]]:
    """Payload de LIST_NOTEBOOKS ([[fila, fila, ...]]) → notebooks, más recientes primero. Pura.

    Vacío/None = "sin notebooks" legítimo. Una forma desconocida NO se silencia: es drift
    (Google cambió el formato) y se avisa, en vez de devolver [] y aparentar que no hay nada.
    """
    if not payload:
        return []
    if isinstance(payload, list):
        rows = payload[0]
        if rows is None:
            return []
        if isinstance(rows, list):
            return [nb for nb in (_parse_notebook_entry(r) for r in rows) if nb]
    raise TransportError("Formato de LIST_NOTEBOOKS no reconocido (drift). "
                         "Revisa docs/transport/README.md.", retriable=False)


def parse_notebook_detail(payload: Any) -> dict[str, Any] | None:
    """Payload de GET_NOTEBOOK ([[título, fuentes, id, ...]]) → notebook canónico. Pura."""
    if isinstance(payload, list) and payload and isinstance(payload[0], list):
        return _parse_notebook_entry(payload[0])
    return None


class BatchExecuteTransport:
    """Implementa el contrato Transport sobre batchexecute. name='web'."""

    name = "web"

    def __init__(self, cookie_header: str, *, host: str = DEFAULT_HOST, hl: str = "en") -> None:
        self._cookie = cookie_header
        self._base = f"https://{host}"
        self._hl = hl
        self._csrf = ""
        self._sid = ""
        self._bl = ""
        self._ready = False
        self._reqid = 100000
        # Turnos (pregunta, respuesta) por conversación hechos en ESTE proceso, para mandar el
        # historial en los seguimientos explícitos (teng-lin ConversationCache). En memoria.
        self._turns: dict[str, list[tuple[str, str]]] = {}

    def available(self) -> bool:
        return bool(self._cookie)

    async def _bootstrap(self, client: httpx.AsyncClient, force: bool = False) -> None:
        if self._ready and not force:
            return
        res = await client.get(
            f"{self._base}/?hl={self._hl}",
            headers={"User-Agent": USER_AGENT, "Cookie": self._cookie},
            follow_redirects=True,
        )
        if "accounts.google.com" in str(res.url):
            raise TransportError("No autenticado: la home redirige a login (sesión caducada).",
                                 retriable=False)
        html = res.text
        csrf = re.search(r'"SNlM0e":"([^"]+)"', html) or re.search(r'"FdrFJe":"([^"]+)"', html)
        sid = re.search(r'"FdrFJe":"([^"]+)"', html)
        bl = re.search(r'"cfb2h":"([^"]+)"', html)
        if not csrf:
            raise TransportError("No se pudo extraer el token CSRF (SNlM0e) de la home.",
                                 retriable=False)
        self._csrf = csrf.group(1)
        self._sid = sid.group(1) if sid else ""
        self._bl = bl.group(1) if bl else self._bl
        self._ready = True

    _OPERATIONS = ("ask", "list_notebooks", "get_notebook")

    async def call(self, operation: str, **params: Any) -> TransportResult:
        """Operaciones: 'ask', 'list_notebooks', 'get_notebook'. Devuelven datos ya parseados."""
        if operation not in self._OPERATIONS:
            raise TransportError(f"operación '{operation}' no implementada aún en batchexecute",
                                 retriable=False)
        async with httpx.AsyncClient(timeout=120) as client:
            await self._bootstrap(client)
            if operation == "list_notebooks":
                # Params de la web: [null, 1, null, [2]]
                payload = await self._rpc(client, "LIST_NOTEBOOKS", [None, 1, None, [2]])
                data: Any = parse_notebook_list(payload)
            elif operation == "get_notebook":
                nb_id = params["notebook_id"]
                payload = await self._rpc(client, "GET_NOTEBOOK", [nb_id, None, [2], None, 0],
                                          source_path=f"/notebook/{nb_id}")
                data = parse_notebook_detail(payload)
            else:
                nb_id = params["notebook_id"]
                source_ids = params.get("source_ids")
                if not source_ids:
                    # Sin fuentes explícitas → TODAS las del notebook (igual que la web;
                    # coinciden jacob-bd y teng-lin get_source_ids).
                    payload = await self._rpc(client, "GET_NOTEBOOK",
                                              [nb_id, None, [2], None, 0],
                                              source_path=f"/notebook/{nb_id}")
                    detail = parse_notebook_detail(payload)
                    source_ids = [s["id"] for s in (detail or {}).get("sources", [])]
                data = await self._ask(client, nb_id, params["question"], source_ids,
                                       params.get("conversation_id"))
            return TransportResult(data=data, backend=self.name)

    async def _rpc(self, client: httpx.AsyncClient, name: str, rpc_params: Any,
                   *, source_path: str = "/") -> Any:
        """Llamada batchexecute genérica: arma f.req, hace POST y devuelve el payload interno."""
        rpc_id = _resolve_rpc_id(name)
        body = build_batch_body(rpc_id, rpc_params, self._csrf)
        self._reqid += 100000
        query = {"rpcids": rpc_id, "source-path": source_path, "bl": self._bl, "hl": self._hl,
                 "_reqid": str(self._reqid), "rt": "c"}
        if self._sid:
            query["f.sid"] = self._sid
        headers = {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Origin": self._base, "Referer": f"{self._base}/",
            "X-Same-Domain": "1", "User-Agent": USER_AGENT, "Cookie": self._cookie,
        }
        res = await client.post(f"{self._base}{BATCH_ENDPOINT}", params=query, content=body,
                                headers=headers)
        if res.status_code in (401, 403) or "accounts.google.com" in str(res.url):
            await self._bootstrap(client, force=True)
            body = build_batch_body(rpc_id, rpc_params, self._csrf)
            res = await client.post(f"{self._base}{BATCH_ENDPOINT}", params=query, content=body,
                                    headers=headers)
        if res.status_code >= 400:
            raise TransportError(f"batchexecute {name} HTTP {res.status_code}", retriable=False)
        return parse_batchexecute(res.text, rpc_id)

    async def _ask(self, client, notebook_id, question, source_ids, conversation_id=None):
        """Pregunta con el protocolo actual de la web (decisiones en web_chat.py).

        Sin conversation_id: se manda None y el servidor continúa la conversación actual del
        notebook; después se lee el id REAL con hPTbtc (teng-lin #659). Con conversation_id:
        seguimiento explícito, con el historial de los turnos hechos en este proceso.
        """
        history = build_history(self._turns.get(conversation_id, [])) if conversation_id else None
        inner = build_query_params(notebook_id=notebook_id, question=question,
                                   source_ids=list(source_ids or []), history=history,
                                   conversation_id=conversation_id)
        parsed = parse_chat_stream(await self._post_query_streamed(client, inner))
        is_follow_up = conversation_id is not None
        if conversation_id is None:
            raw = await self._rpc(client, "GET_LAST_CONVERSATION_ID",
                                  [[], None, notebook_id, 1],
                                  source_path=f"/notebook/{notebook_id}")
            conversation_id = unwrap_last_conversation_id(raw)
            if conversation_id is None:
                # Hubo respuesta pero no se pudo leer el id: no se inventa uno (crearía
                # turnos fantasma). Se devuelve la respuesta y se avisa.
                parsed["warning"] = ("No se pudo leer el id de la conversación; la respuesta es "
                                     "válida pero no podrás encadenar seguimientos con ella.")
            else:
                is_follow_up = bool(self._turns.get(conversation_id))
        if conversation_id and parsed["answer"]:
            self._turns.setdefault(conversation_id, []).append((question, parsed["answer"]))
        refs = parsed["references"]
        return {
            "answer": parsed["answer"],
            "references": refs,
            "sources_used": list(dict.fromkeys(r["source_id"] for r in refs)),
            "conversation_id": conversation_id,
            "is_follow_up": is_follow_up,
            "notebook_id": notebook_id,
            **({"warning": parsed["warning"]} if "warning" in parsed else {}),
        }

    async def _post_query_streamed(self, client: httpx.AsyncClient, inner: Any) -> str:
        def build() -> tuple[dict[str, str], str, dict[str, str]]:
            self._reqid += 100000
            query = {"bl": self._bl, "hl": self._hl, "_reqid": str(self._reqid), "rt": "c"}
            if self._sid:
                query["f.sid"] = self._sid
            f_req = json.dumps([None, json.dumps(inner, separators=(",", ":"),
                                                 ensure_ascii=False)],
                               separators=(",", ":"), ensure_ascii=False)
            body = f"f.req={quote(f_req, safe='')}"
            if self._csrf:
                body += f"&at={quote(self._csrf, safe='')}"
            headers = {
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Origin": self._base, "Referer": f"{self._base}/",
                "X-Same-Domain": "1", "User-Agent": USER_AGENT, "Cookie": self._cookie,
            }
            return query, body + "&", headers

        query, body, headers = build()
        res = await client.post(f"{self._base}{QUERY_ENDPOINT}", params=query, content=body,
                                headers=headers)
        if res.status_code in (401, 403) or "accounts.google.com" in str(res.url):
            await self._bootstrap(client, force=True)
            query, body, headers = build()        # el CSRF nuevo tiene que ir en el cuerpo
            res = await client.post(f"{self._base}{QUERY_ENDPOINT}", params=query,
                                    content=body, headers=headers)
        if res.status_code >= 400:
            raise TransportError(f"query endpoint HTTP {res.status_code}", retriable=False)
        return res.text


# Comprobación estructural: cumple el contrato Transport.
_: type[Transport] = BatchExecuteTransport  # type: ignore[assignment]
