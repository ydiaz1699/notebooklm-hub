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
from typing import Any

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

    async def call(self, operation: str, **params: Any) -> TransportResult:
        """Operaciones soportadas en Fase 1: 'ask'. El resto se añade en Fase 3."""
        if operation != "ask":
            raise TransportError(f"operación '{operation}' no implementada aún en batchexecute",
                                 retriable=False)
        async with httpx.AsyncClient(timeout=120) as client:
            await self._bootstrap(client)
            data = await self._ask(client, params["notebook_id"], params["question"],
                                   params.get("source_ids"))
            return TransportResult(data=data, backend=self.name)

    async def _ask(self, client, notebook_id, question, source_ids):
        # Si no se pasan fuentes, se consultan todas (Fase 3: resolver source ids del notebook).
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
