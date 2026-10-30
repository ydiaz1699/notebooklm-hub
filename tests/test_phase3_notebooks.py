"""Fase 3 (bloque 1) — notebooks: parsers, resolución nombre→ID, tools y transporte simulado.

Sin red real: el transporte se prueba contra un servidor HTTP simulado (httpx.MockTransport) que
devuelve respuestas con la forma del protocolo. La verificación contra Google se hace en el NAS.
"""
import asyncio
import json
from urllib.parse import parse_qs, unquote

import httpx
import pytest

from notebooklm_hub._app.errors import AmbiguousError, Category, NotFoundError, classify
from notebooklm_hub._app.notebooks import (
    get_notebook,
    list_notebooks,
    looks_like_id,
    resolve_notebook_id,
)
from notebooklm_hub.core.transport import batchexecute as be
from notebooklm_hub.tools.registry import discover_tools

ID_A = "aaaaaaaa-0000-4000-8000-000000000001"
ID_B = "bbbbbbbb-0000-4000-8000-000000000002"
ID_C = "cccccccc-0000-4000-8000-000000000003"


def _nb(title, nb_id, sources=(), owner=1, shared=False):
    """Entrada de notebook con la forma del protocolo real."""
    srcs = [[[sid], stitle, [None], [None, 2]] for sid, stitle in sources]
    meta = [owner, shared, True, None, None, [1760000000, 0], None, None, [1750000000, 0]]
    return [title, srcs, nb_id, "📘", None, meta]


LIST_PAYLOAD = [[
    _nb("Motores", ID_A, [("s1", "manual.pdf"), ("s2", "notas")]),
    _nb("Motores diésel", ID_B, [("s3", "x")], owner=2, shared=True),
    _nb("Recetas", ID_C),
]]


# ---- parsers puros ----
def test_parse_notebook_list_shape():
    nbs = be.parse_notebook_list(LIST_PAYLOAD)
    assert [n["id"] for n in nbs] == [ID_A, ID_B, ID_C]
    a = nbs[0]
    assert a["title"] == "Motores" and a["emoji"] == "📘" and a["source_count"] == 2
    assert a["sources"][0] == {"id": "s1", "title": "manual.pdf"}
    assert a["is_owned"] is True and a["is_shared"] is False
    assert a["created_at"].startswith("2025-") and a["modified_at"].startswith("2025-")
    assert nbs[1]["is_owned"] is False and nbs[1]["is_shared"] is True


def test_parse_notebook_list_tolerates_garbage_and_empty():
    assert be.parse_notebook_list(None) == []
    assert be.parse_notebook_list([[]]) == []
    assert be.parse_notebook_list([[["sin id"], _nb("ok", ID_A)]])[0]["id"] == ID_A


def test_parse_notebook_detail():
    nb = be.parse_notebook_detail([_nb("Motores", ID_A, [("s1", "manual.pdf")])])
    assert nb["id"] == ID_A and nb["sources"] == [{"id": "s1", "title": "manual.pdf"}]
    assert be.parse_notebook_detail(None) is None


def test_build_batch_body_matches_web_format():
    body = be.build_batch_body("wXbhsf", [None, 1, None, [2]], "tok/en")
    assert body.endswith("&") and "at=tok%2Fen" in body
    f_req = json.loads(unquote(body.split("&")[0][len("f.req="):]))
    assert f_req == [[["wXbhsf", "[null,1,null,[2]]", None, "generic"]]]


# ---- resolución nombre → ID ----
class FakeClient:
    def __init__(self):
        self.list_calls = 0
        self.asked = None

    async def list_notebooks(self):
        self.list_calls += 1
        return be.parse_notebook_list(LIST_PAYLOAD)

    async def get_notebook(self, nb_id):
        return next((n for n in be.parse_notebook_list(LIST_PAYLOAD) if n["id"] == nb_id), None)

    async def ask(self, nb_id, question, source_ids=None):
        self.asked = (nb_id, question, source_ids)
        return {"answer": "ok", "conversation_id": "c", "notebook_id": nb_id}


def test_looks_like_id():
    assert looks_like_id(ID_A) and not looks_like_id("Motores")


def test_resolve_id_passthrough_without_network():
    c = FakeClient()
    assert asyncio.run(resolve_notebook_id(c, ID_C)) == ID_C
    assert c.list_calls == 0


def test_resolve_exact_title_wins_over_partial():
    # "motores" es exacto para "Motores" aunque también sea subcadena de "Motores diésel"
    assert asyncio.run(resolve_notebook_id(FakeClient(), "  motores ")) == ID_A


def test_resolve_partial_unique():
    assert asyncio.run(resolve_notebook_id(FakeClient(), "receta")) == ID_C


def test_resolve_ambiguous_does_not_guess():
    with pytest.raises(AmbiguousError) as e:
        asyncio.run(resolve_notebook_id(FakeClient(), "motor"))
    assert ID_A in str(e.value) and ID_B in str(e.value)
    assert classify(e.value).category == Category.AMBIGUOUS


def test_resolve_not_found():
    with pytest.raises(NotFoundError) as e:
        asyncio.run(resolve_notebook_id(FakeClient(), "astronomía"))
    assert classify(e.value).category == Category.NOT_FOUND


def test_list_filter_and_summary_hides_sources():
    res = asyncio.run(list_notebooks(FakeClient(), "motores"))
    assert [n["id"] for n in res] == [ID_A]
    assert "sources" not in res[0] and res[0]["source_count"] == 2


def test_get_notebook_by_name_includes_sources():
    nb = asyncio.run(get_notebook(FakeClient(), "Recetas"))
    assert nb["id"] == ID_C and nb["sources"] == []


# ---- tools auto-descubiertas ----
def test_registry_has_new_tools_readonly():
    tools = discover_tools()
    for name in ("notebook_list", "notebook_get", "notebook_ask"):
        assert name in tools and tools[name].destructive is False


def test_tool_notebook_list_output():
    out = asyncio.run(discover_tools()["notebook_list"].run(FakeClient()))
    assert out["count"] == 3 and len(out["notebooks"]) == 3


def test_tool_notebook_ask_resolves_name():
    c = FakeClient()
    out = asyncio.run(discover_tools()["notebook_ask"].run(c, notebook="Recetas", question="¿?"))
    assert out["notebook_id"] == ID_C and c.asked[0] == ID_C


# ---- transporte contra servidor simulado ----
HOME_HTML = '<script>{"SNlM0e":"CSRF123","FdrFJe":"SID9","cfb2h":"bl_test"}</script>'


def _batch_response(rpc_id, payload):
    return ")]}'\n\n123\n" + json.dumps([["wrb.fr", rpc_id, json.dumps(payload), None, None, None]])


def _run_transport(monkeypatch, operation, **params):
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.method == "GET":
            return httpx.Response(200, text=HOME_HTML)
        if req.url.path == be.BATCH_ENDPOINT:
            rpc = req.url.params["rpcids"]
            payload = LIST_PAYLOAD if rpc == "wXbhsf" else [LIST_PAYLOAD[0][0]]
            return httpx.Response(200, text=_batch_response(rpc, payload))
        if req.url.path == be.QUERY_ENDPOINT:
            inner = json.dumps(["wrb.fr", None, json.dumps([["respuesta fundamentada larga"]])])
            return httpx.Response(200, text=")]}'\n" + f"[{inner}]")
        return httpx.Response(404)

    real = httpx.AsyncClient
    monkeypatch.setattr(be.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    t = be.BatchExecuteTransport("SID=x")
    return asyncio.run(t.call(operation, **params)), seen


def test_transport_list_notebooks(monkeypatch):
    res, seen = _run_transport(monkeypatch, "list_notebooks")
    assert res.backend == "web" and [n["id"] for n in res.data] == [ID_A, ID_B, ID_C]
    post = seen[1]
    assert post.url.params["rpcids"] == "wXbhsf" and post.url.params["bl"] == "bl_test"
    assert post.url.params["f.sid"] == "SID9"
    assert parse_qs(post.content.decode())["at"] == ["CSRF123"]


def test_transport_get_notebook_uses_source_path(monkeypatch):
    res, seen = _run_transport(monkeypatch, "get_notebook", notebook_id=ID_A)
    assert res.data["id"] == ID_A
    assert seen[1].url.params["source-path"] == f"/notebook/{ID_A}"


def test_transport_ask_without_sources_fetches_them_first(monkeypatch):
    """Regresión del bug de Fase 1: sin source_ids se enviaba la lista vacía."""
    res, seen = _run_transport(monkeypatch, "ask", notebook_id=ID_A, question="¿qué dice?")
    assert res.data["answer"] == "respuesta fundamentada larga"
    assert seen[1].url.params["rpcids"] == "rLM1Ne"          # primero GET_NOTEBOOK
    query = seen[2]
    assert query.url.path == be.QUERY_ENDPOINT
    f_req = json.loads(parse_qs(query.content.decode())["f.req"][0])
    inner = json.loads(f_req[1])
    assert inner[0] == [[["s1"]], [["s2"]]] and inner[1] == "¿qué dice?"


def test_transport_ask_with_explicit_sources_skips_lookup(monkeypatch):
    _, seen = _run_transport(monkeypatch, "ask", notebook_id=ID_A, question="q",
                             source_ids=["s2"])
    assert [r.url.path for r in seen[1:]] == [be.QUERY_ENDPOINT]
    inner = json.loads(json.loads(parse_qs(seen[1].content.decode())["f.req"][0])[1])
    assert inner[0] == [[["s2"]]]
