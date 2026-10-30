"""Fase 3 — ask "el mejor de los 7": petición de 9 campos, respuesta final, citas, errores,
conversación real (hPTbtc) y seguimientos. Sin red real (servidor HTTP simulado)."""
import asyncio
import json
from urllib.parse import parse_qs

import httpx
import pytest

from notebooklm_hub._app.errors import Category, classify
from notebooklm_hub.core.transport import batchexecute as be
from notebooklm_hub.core.transport import web_chat as wc
from notebooklm_hub.core.transport.base import RpcRefusedError, TransportError
from notebooklm_hub.tools.registry import discover_tools

NB = "aaaaaaaa-0000-4000-8000-000000000001"
SRC1 = "11111111-1111-4111-8111-111111111111"
SRC2 = "22222222-2222-4222-8222-222222222222"


# ---------- helpers: construyen fragmentos con la forma real del protocolo ----------
def _cite(source_id, text="", start=10, score=0.8):
    para_el = [start, start + len(text), [text, None]]
    struct_el = [start, start + len(text), [[para_el], None]]
    detail = [None, None, score, [[None, start, start + len(text)]], [[struct_el]], [[[source_id]]]]
    return [["chunk-1"], detail]


def _answer(text, *, marker=1, final=False, cites=None, session="sess-1"):
    type_block = [None, None, None, cites, marker]
    row = [text, None, [session, "turn-1", 1], None, type_block]
    return json.dumps(["wrb.fr", None, json.dumps([row, None, None, None, final])])


def _stream(*envelopes, terminal=False):
    lines = [")]}'"]
    for env in envelopes:
        lines += ["123", f"[{env}]"]
    if terminal:
        lines += ["25", '[["e",4,null,null,1234]]']
    return "\n".join(lines)


# ---------- petición ----------
def test_query_params_have_9_fields_and_no_invented_id():
    p = wc.build_query_params(notebook_id=NB, question="q", source_ids=[SRC1],
                              history=None, conversation_id=None)
    assert len(p) == 9 and p[0] == [[[SRC1]]] and p[1] == "q"
    assert p[3] == [2, None, [1], [1]] and p[4] is None and p[7] == NB and p[8] == 1


def test_history_shape():
    assert wc.build_history([]) is None
    assert wc.build_history([("p1", "r1")]) == [["r1", None, 2], ["p1", None, 1]]


def test_unwrap_last_conversation_id():
    assert wc.unwrap_last_conversation_id([[["c-1"]]]) == "c-1"
    assert wc.unwrap_last_conversation_id(None) is None
    assert wc.unwrap_last_conversation_id([[[None]], [["c-2"]]]) == "c-2"


# ---------- elección de la respuesta ----------
def test_final_marked_chunk_wins_even_if_shorter():
    body = _stream(_answer("Respuesta larga provisional que luego se corrige"),
                   _answer("Respuesta final", final=True))
    assert wc.parse_chat_stream(body)["answer"] == "Respuesta final"


def test_longest_marked_when_no_final_flag():
    body = _stream(_answer("Corta"), _answer("La más larga de todas"))
    assert wc.parse_chat_stream(body)["answer"] == "La más larga de todas"


def test_thinking_never_beats_an_answer():
    body = _stream(_answer("Pensando... " * 20, marker=0), _answer("Hecho"))
    assert wc.parse_chat_stream(body)["answer"] == "Hecho"


def test_only_unmarked_text_is_fallback():
    assert wc.parse_chat_stream(_stream(_answer("solo esto", marker=0)))["answer"] == "solo esto"


def test_heartbeats_only_is_empty_answer_not_error():
    heartbeat = json.dumps(["wrb.fr", None, "[]"])
    assert wc.parse_chat_stream(_stream(heartbeat))["answer"] == ""


def test_turn_key_is_read():
    tk = wc.parse_chat_stream(_stream(_answer("x")))["turn_key"]
    assert tk == {"session_id": "sess-1", "turn_id": "turn-1"}


# ---------- citas ----------
def test_citations_full_text_source_and_score():
    cites = [_cite(SRC1, "El motor gira a 3000 rpm.", start=5, score=0.91),
             _cite(SRC2, "Par máximo 400 Nm.", start=100)]
    refs = wc.parse_chat_stream(_stream(_answer("Gira a 3000 rpm [1] y 400 Nm [2].",
                                                cites=cites)))["references"]
    assert refs[0] == {"citation_number": 1, "source_id": SRC1,
                       "cited_text": "El motor gira a 3000 rpm.", "start_char": 5,
                       "end_char": 30, "score": 0.91}
    assert refs[1]["citation_number"] == 2 and refs[1]["source_id"] == SRC2


def test_broken_citation_leaves_a_gap_so_numbers_never_shift():
    cites = [["roto"], _cite(SRC2, "texto")]
    refs = wc.parse_chat_stream(_stream(_answer("a [2]", cites=cites)))["references"]
    assert [r["citation_number"] for r in refs] == [2]


def test_bad_score_is_dropped_not_crashing():
    refs = wc.parse_chat_stream(_stream(_answer("a", cites=[_cite(SRC1, "t", score=True)])))
    assert refs["references"][0]["score"] is None


def test_table_fragment_is_marked():
    detail = [None, None, 0.5, None, [[[0, 9, None, None, ["tabla-raw"]]]], [[[SRC1]]]]
    refs = wc.parse_citations([None, None, None, [[["c"], detail]]])
    assert refs[0]["cited_text"] == "[tabla]"


# ---------- errores (nunca silenciados) ----------
def test_rate_limit_user_displayable_error():
    env = json.dumps(["wrb.fr", None, None, None, None,
                      [8, None, [["type.googleapis.com/x.UserDisplayableError"]]]])
    with pytest.raises(RpcRefusedError) as e:
        wc.parse_chat_stream(_stream(env))
    assert e.value.status == 8 and classify(e.value).category == Category.NOTEBOOK_LIMIT


def test_stream_cut_without_payload_is_quota():
    with pytest.raises(RpcRefusedError) as e:
        wc.parse_chat_stream(_stream(terminal=True))
    assert e.value.status == 8


def test_question_too_long_status_3():
    env = json.dumps(["wrb.fr", None, None, None, None, [3]])
    with pytest.raises(RpcRefusedError) as e:
        wc.parse_chat_stream(_stream(env))
    assert "demasiado larga" in str(e.value) and e.value.status == 3


def test_error_frame_er():
    with pytest.raises(TransportError):
        wc.parse_chat_stream(_stream('["er", null, 500]'))


def test_garbage_is_drift():
    with pytest.raises(TransportError) as e:
        wc.parse_chat_stream("<html>nada</html>")
    assert "drift" in str(e.value)


def test_answer_row_not_list_is_drift():
    env = json.dumps(["wrb.fr", None, json.dumps(["texto suelto"])])
    with pytest.raises(TransportError):
        wc.parse_chat_stream(_stream(env))


# ---------- transporte completo contra servidor simulado ----------
HOME = '<script>{"SNlM0e":"CSRF","FdrFJe":"SID","cfb2h":"bl"}</script>'


def _transport(monkeypatch, *, conv_payload=(("conv-real",),), chat=None):
    seen = []
    nb_row = ["NB", [[[SRC1], "doc"], [[SRC2], "doc2"]], NB]
    chat = chat or _stream(_answer("Respuesta [1]", final=True, cites=[_cite(SRC1, "cita")]))

    def handler(req):
        seen.append(req)
        if req.method == "GET":
            return httpx.Response(200, text=HOME)
        if req.url.path == be.QUERY_ENDPOINT:
            return httpx.Response(200, text=chat)
        rpc = req.url.params["rpcids"]
        payload = {"rLM1Ne": [nb_row], "hPTbtc": [[list(r) for r in conv_payload]]}[rpc]
        return httpx.Response(200, text=")]}'\n" + json.dumps(
            [["wrb.fr", rpc, json.dumps(payload), None, None, None]]))

    real = httpx.AsyncClient
    monkeypatch.setattr(be.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    return be.BatchExecuteTransport("SID=x"), seen


def _query_inner(req):
    return json.loads(json.loads(parse_qs(req.content.decode())["f.req"][0])[1])


def test_ask_flow_returns_real_conversation_and_citations(monkeypatch):
    t, seen = _transport(monkeypatch)
    data = asyncio.run(t.call("ask", notebook_id=NB, question="¿qué?")).data
    assert [r.url.params.get("rpcids") for r in seen[1:]] == ["rLM1Ne", None, "hPTbtc"]
    assert data["conversation_id"] == "conv-real" and data["is_follow_up"] is False
    assert data["sources_used"] == [SRC1] and data["references"][0]["cited_text"] == "cita"
    assert _query_inner(seen[2])[4] is None


def test_follow_up_sends_conversation_and_history(monkeypatch):
    t, seen = _transport(monkeypatch)
    first = asyncio.run(t.call("ask", notebook_id=NB, question="p1")).data
    seen.clear()
    data = asyncio.run(t.call("ask", notebook_id=NB, question="p2", source_ids=[SRC1],
                              conversation_id=first["conversation_id"])).data
    assert all(r.method == "POST" for r in seen)                       # sesión reutilizada
    inner = _query_inner(next(r for r in seen if r.url.path == be.QUERY_ENDPOINT))
    assert inner[4] == "conv-real"
    assert inner[2] == [["Respuesta [1]", None, 2], ["p1", None, 1]]
    assert data["is_follow_up"] is True
    assert all(r.url.params.get("rpcids") != "hPTbtc" for r in seen)   # ya conocido


def test_missing_conversation_id_warns_instead_of_inventing(monkeypatch):
    t, _ = _transport(monkeypatch, conv_payload=())
    data = asyncio.run(t.call("ask", notebook_id=NB, question="q")).data
    assert data["conversation_id"] is None and "warning" in data
    assert data["answer"] == "Respuesta [1]"


def test_csrf_refresh_rebuilds_body(monkeypatch):
    calls = {"n": 0}
    seen = []

    def handler(req):
        seen.append(req)
        if req.method == "GET":
            calls["n"] += 1
            return httpx.Response(200, text=HOME.replace("CSRF", f"CSRF{calls['n']}"))
        if req.url.path == be.QUERY_ENDPOINT and len([r for r in seen
                                                      if r.url.path == be.QUERY_ENDPOINT]) == 1:
            return httpx.Response(401)
        if req.url.path == be.QUERY_ENDPOINT:
            return httpx.Response(200, text=_stream(_answer("ok", final=True)))
        return httpx.Response(200, text=")]}'\n" + json.dumps(
            [["wrb.fr", "hPTbtc", json.dumps([[["c"]]]), None, None, None]]))

    real = httpx.AsyncClient
    monkeypatch.setattr(be.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    t = be.BatchExecuteTransport("SID=x")
    asyncio.run(t.call("ask", notebook_id=NB, question="q", source_ids=[SRC1]))
    queries = [r for r in seen if r.url.path == be.QUERY_ENDPOINT]
    assert parse_qs(queries[0].content.decode())["at"] == ["CSRF1"]
    assert parse_qs(queries[1].content.decode())["at"] == ["CSRF2"]   # antes reusaba el viejo


# ---------- tool ----------
class _Fake:
    def __init__(self):
        self.kw = None

    async def list_notebooks(self):
        return [{"id": NB, "title": "Motores"}]

    async def ask(self, nb_id, q, source_ids=None, conversation_id=None):
        self.kw = (nb_id, q, source_ids, conversation_id)
        return {"answer": "r", "references": [{"citation_number": 1, "source_id": SRC1}],
                "sources_used": [SRC1], "conversation_id": "c9", "is_follow_up": True,
                "notebook_id": nb_id}


def test_tool_passes_conversation_and_returns_citations():
    f = _Fake()
    out = asyncio.run(discover_tools()["notebook_ask"].run(
        f, notebook="Motores", question="q", conversation_id="c9"))
    assert f.kw == (NB, "q", None, "c9")
    assert out["references"][0]["source_id"] == SRC1 and out["is_follow_up"] is True
    assert "warning" not in out


def test_tool_rejects_bad_source_ids():
    with pytest.raises(ValueError):
        asyncio.run(discover_tools()["notebook_ask"].run(
            _Fake(), notebook=NB, question="q", source_ids=[""]))
