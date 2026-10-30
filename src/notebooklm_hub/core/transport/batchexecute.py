"""Transporte batchexecute (Web RPC) — nivel 2 de la cascada.

Habla el MISMO protocolo interno que la web de NotebookLM: endpoints `batchexecute` y el endpoint
de query `GenerateFreeFormStreamed`. 10-100x más rápido que raspar el DOM e inmune a rediseños de UI.

El protocolo (endpoint, armado de `f.req`, prefijo anti-XSSI `)]}'`, parseo de envelopes `wrb.fr`,
drift vs refusal, bootstrap de tokens SNlM0e/FdrFJe/cfb2h) está destilado y portado de la impl de
referencia `roomi-fields/notebooklm-mcp` (MIT) y `jacob-bd/gemini-notebook-mcp-cli` (MIT), verificado
contra su código el 2026-10-04. Ver docs/transport/README.md.

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
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from .base import Transport, TransportError, TransportResult

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
}

# Códigos gRPC estándar que el backend pone en el índice 5 del envelope al rechazar.
_GRPC_STATUS = {
    5: "NOT_FOUND", 7: "PERMISSION_DENIED", 8: "RESOURCE_EXHAUSTED",
    9: "FAILED_PRECONDITION", 12: "UNIMPLEMENTED", 16: "UNAUTHENTICATED",
}


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
                    raise TransportError(
                        f"NotebookLM rechazó la llamada: {label}",
                        retriable=(status == 16),  # solo UNAUTHENTICATED se reintenta
                    )
                return None
            if len(env) >= 1 and env[0] == "er":
                raise TransportError("batchexecute devolvió un envelope de error", retriable=False)
    # Ningún envelope para este id → el id casi seguro rotó (drift).
    raise TransportError(
        f"RPC id '{rpc_id}' no está en la respuesta (drift). "
        f"Parchea con NOTEBOOKLM_HUB_RPC_OVERRIDES.",
        retriable=False,
    )


def parse_query_response(text: str) -> dict[str, Any]:
    """Parsea la respuesta streamed de query: elige el chunk de respuesta más largo.

    Pura (sin red). Portado de roomi query-rpc.ts parseQueryResponse (forma simplificada
    para Fase 1: devuelve el texto de la respuesta; las citas detalladas llegan en Fase 3).
    """
    body = text[4:] if text.startswith(")]}'") else text
    longest = ""
    for raw in body.strip().split("\n"):
        line = raw.strip()
        if not line or not line.startswith("["):
            continue
        try:
            chunk = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Un chunk es una lista de envelopes. El contenido útil de un envelope wrb.fr viene en el
        # índice 2 como JSON *string* → hay que decodificarlo antes de buscar el texto.
        for env in chunk if isinstance(chunk, list) else []:
            inner = env
            if isinstance(env, list) and len(env) >= 3 and env[0] == "wrb.fr" and isinstance(env[2], str):
                try:
                    inner = json.loads(env[2])
                except json.JSONDecodeError:
                    continue
            candidate = _longest_string(inner)
            if len(candidate) > len(longest):
                longest = candidate
    return {"answer": longest}


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


def _parse_notebook_entry(nb: Any) -> dict[str, Any] | None:
    """Una entrada de notebook del protocolo → dict canónico.

    Estructura observada (jacob-bd notebooks.py, MIT):
      [0] título · [1] fuentes [[ [source_id], título, ...], ...] · [2] notebook id
      [3] emoji|null · [5] metadata: [0]=propiedad (1=mío, 2=compartido conmigo),
          [1]=compartido (bool), [5]=modificado [s,ns], [8]=creado [s,ns]
    """
    if not isinstance(nb, list) or len(nb) < 3 or not isinstance(nb[2], str) or not nb[2]:
        return None
    sources = []
    for src in nb[1] if isinstance(nb[1], list) else []:
        if isinstance(src, list) and src:
            sid = src[0][0] if isinstance(src[0], list) and src[0] else src[0]
            if isinstance(sid, str):
                title = src[1] if len(src) > 1 and isinstance(src[1], str) else "Untitled"
                sources.append({"id": sid, "title": title})
    meta = nb[5] if len(nb) > 5 and isinstance(nb[5], list) else []
    return {
        "id": nb[2],
        "title": nb[0] if isinstance(nb[0], str) and nb[0] else "Untitled",
        "emoji": nb[3] if len(nb) > 3 and isinstance(nb[3], str) else None,
        "source_count": len(sources),
        "sources": sources,
        "is_owned": (meta[0] == 1) if meta else True,
        "is_shared": bool(meta[1]) if len(meta) > 1 else False,
        "modified_at": _ts(meta[5]) if len(meta) > 5 else None,
        "created_at": _ts(meta[8]) if len(meta) > 8 else None,
    }


def parse_notebook_list(payload: Any) -> list[dict[str, Any]]:
    """Payload de LIST_NOTEBOOKS → lista de notebooks canónicos. Pura."""
    if not isinstance(payload, list) or not payload:
        return []
    entries = payload[0] if isinstance(payload[0], list) and (
        not payload[0] or isinstance(payload[0][0], list)) else payload
    return [nb for nb in (_parse_notebook_entry(e) for e in entries) if nb]


def parse_notebook_detail(payload: Any) -> dict[str, Any] | None:
    """Payload de GET_NOTEBOOK ([[título, fuentes, id, ...]]) → notebook canónico. Pura."""
    if isinstance(payload, list) and payload and isinstance(payload[0], list):
        return _parse_notebook_entry(payload[0])
    return None


def _longest_string(node: Any) -> str:
    if isinstance(node, str):
        return node
    best = ""
    if isinstance(node, list):
        for item in node:
            s = _longest_string(item)
            if len(s) > len(best):
                best = s
    return best


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
                source_ids = params.get("source_ids")
                if not source_ids:
                    # Sin fuentes explícitas → TODAS las del notebook. El payload de query NO
                    # lleva el notebook id: el contexto lo dan las fuentes (verificado en
                    # jacob-bd conversation.py: get_notebook → _extract_source_ids).
                    nb_id = params["notebook_id"]
                    payload = await self._rpc(client, "GET_NOTEBOOK",
                                              [nb_id, None, [2], None, 0],
                                              source_path=f"/notebook/{nb_id}")
                    detail = parse_notebook_detail(payload)
                    source_ids = [s["id"] for s in (detail or {}).get("sources", [])]
                data = await self._ask(client, params["notebook_id"], params["question"],
                                       source_ids)
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

    async def _ask(self, client, notebook_id, question, source_ids):
        sources_array = [[[sid]] for sid in (source_ids or [])]
        conversation_id = str(uuid.uuid4())
        inner = [sources_array, question, None, [2, None, [1]], conversation_id]
        text = await self._post_query_streamed(client, inner)
        parsed = parse_query_response(text)
        return {
            "answer": parsed["answer"],
            "conversation_id": conversation_id,
            "notebook_id": notebook_id,
        }

    async def _post_query_streamed(self, client: httpx.AsyncClient, inner: Any) -> str:
        self._reqid += 100000
        query = {"bl": self._bl, "hl": self._hl, "_reqid": str(self._reqid), "rt": "c"}
        if self._sid:
            query["f.sid"] = self._sid
        f_req = [None, json.dumps(inner)]
        body = f"f.req={httpx.QueryParams({'x': json.dumps(f_req)})['x']}"
        if self._csrf:
            body += f"&at={httpx.QueryParams({'x': self._csrf})['x']}"
        body += "&"
        res = await client.post(
            f"{self._base}{QUERY_ENDPOINT}",
            params=query,
            content=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Origin": self._base, "Referer": f"{self._base}/",
                "X-Same-Domain": "1", "X-Goog-Csrf-Token": self._csrf,
                "User-Agent": USER_AGENT, "Cookie": self._cookie,
            },
        )
        if res.status_code in (401, 403) or "accounts.google.com" in str(res.url):
            await self._bootstrap(client, force=True)
            res = await client.post(
                f"{self._base}{QUERY_ENDPOINT}", params=query, content=body,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                    "Origin": self._base, "Referer": f"{self._base}/",
                    "X-Same-Domain": "1", "X-Goog-Csrf-Token": self._csrf,
                    "User-Agent": USER_AGENT, "Cookie": self._cookie,
                },
            )
        if res.status_code >= 400:
            raise TransportError(f"query endpoint HTTP {res.status_code}", retriable=False)
        return res.text


# Comprobación estructural: cumple el contrato Transport.
_: type[Transport] = BatchExecuteTransport  # type: ignore[assignment]
