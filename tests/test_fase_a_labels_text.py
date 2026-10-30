"""Fase A — etiquetas y fuente de texto (base del método de las 3 notas). Sin red real."""
import asyncio
import json
from urllib.parse import parse_qs

import httpx
import pytest

from notebooklm_hub._app.errors import AmbiguousError, Category, NotFoundError, classify
from notebooklm_hub._app.labels import assign_source, auto_label, list_labels, match_label
from notebooklm_hub._app.sources import add_text
from notebooklm_hub.core.transport import batchexecute as be
from notebooklm_hub.core.transport import web_labels as wl
from notebooklm_hub.core.transport import web_sources as ws
from notebooklm_hub.core.transport.base import (
    RpcRefusedError,
    TransportError,
    UnconfirmedWriteError,
)
from notebooklm_hub.core.transport.cascade import Cascade
from notebooklm_hub.tools.registry import discover_tools

NB = "aaaaaaaa-0000-4000-8000-000000000001"
S1, S2, S3 = "s-1", "s-2", "s-3"
OPTS = [2, None, None, [1, None, None, None, None, None, None, None, None, None, [1]]]


def _label(name, ids, lid, emoji="🔧"):
    return [name, [[i] for i in ids] if ids is not None else None, lid, emoji]


# ---------------- protocolo puro ----------------
def test_params_match_web_format():
    assert wl.build_list_labels_params(NB) == [OPTS, NB]
    assert wl.build_generate_labels_params(NB, "unlabeled") == [OPTS, NB, None, None, [False]]
    assert wl.build_generate_labels_params(NB, "all") == [OPTS, NB, None, None, [True]]
    assert wl.build_assign_source_params(NB, "L1", S1) == [OPTS, NB, "L1", [[None, [[S1]]]]]
    with pytest.raises(ValueError):
        wl.build_generate_labels_params(NB, "todo")


def test_opts_is_fresh_each_call():
    a, b = wl.opts(), wl.opts()
    a[3].append("x")
    assert b == OPTS


def test_parse_label_set_list_and_create_envelopes():
    rows = [_label("Turbo", [S1, S2], "L1"), _label("Vacía", None, "L2", "")]
    listed = wl.parse_label_set([rows], index=0)
    created = wl.parse_label_set([None, rows], index=1)
    assert listed == created
    assert listed[0] == {"id": "L1", "name": "Turbo", "emoji": "🔧", "source_ids": [S1, S2]}
    assert listed[1]["source_ids"] == [] and listed[1]["emoji"] is None
    assert wl.parse_label_set(None, index=0) == [] and wl.parse_label_set([None], index=0) == []


def test_parse_label_drift_is_loud():
    with pytest.raises(TransportError):
        wl.parse_label_set([[["sin id", []]]], index=0)
    with pytest.raises(TransportError):
        wl.parse_label_set([[["X", "no-lista", "L1", ""]]], index=0)
    with pytest.raises(TransportError):
        wl.parse_label_set({"raro": 1}, index=0)


def test_add_text_params_nested_template_block():
    p = ws.build_add_text_params(NB, "1. Puntos clave – Turbo", "contenido")
    assert p[0] == [[None, ["1. Puntos clave – Turbo", "contenido"], None, 2,
                     None, None, None, None, None, None, 1]]
    assert p[1] == NB and p[2] == OPTS           # anidado (teng-lin #1546), no plano


@pytest.mark.parametrize("payload", [
    [[[[["src-9"], "Título"]]]],     # profunda
    [[["src-9"], "Título"]],         # media
    ["src-9", "Título"],             # plana
])
def test_parse_added_source_three_shapes(payload):
    assert ws.parse_added_source(payload, "fb") == {"id": "src-9", "title": "Título"}


def test_parse_added_source_unknown():
    assert ws.parse_added_source(None, "fb") is None
    assert ws.parse_added_source([[None]], "fb") is None


# ---------------- lógica neutral ----------------
class Fake:
    def __init__(self, labels=None):
        self.labels = labels if labels is not None else [
            {"id": "L1", "name": "Turbo", "emoji": None, "source_ids": [S1]},
            {"id": "L2", "name": "Turbo diésel", "emoji": None, "source_ids": []},
        ]
        self.assigned = []
        self.scope = None

    async def list_notebooks(self):
        return [{"id": NB, "title": "Motores"}]

    async def get_notebook(self, nb_id):
        return {"id": nb_id, "sources": [{"id": S1, "title": "manual.pdf"},
                                         {"id": S2, "title": "notas"}, {"id": S3, "title": "x"}]}

    async def list_labels(self, nb_id):
        return self.labels

    async def generate_labels(self, nb_id, scope):
        self.scope = scope
        return self.labels

    async def assign_source_to_label(self, nb_id, lid, sid):
        self.assigned.append((lid, sid))
        return {}

    async def add_text_source(self, nb_id, title, content):
        return {"id": "new", "title": title, "reconciled": False}


def test_list_labels_enriches_and_reports_unlabeled():
    out = asyncio.run(list_labels(Fake(), "Motores"))
    assert out["notebook_id"] == NB and out["count"] == 2
    assert out["labels"][0]["sources"] == [{"id": S1, "title": "manual.pdf"}]
    assert {s["id"] for s in out["unlabeled_sources"]} == {S2, S3}


def test_auto_label_default_is_incremental():
    f = Fake()
    asyncio.run(auto_label(f, NB))
    assert f.scope == "unlabeled"


def test_match_label_exact_beats_partial_and_ambiguous_not_guessed():
    labels = Fake().labels
    assert match_label(labels, "turbo")["id"] == "L1"
    assert match_label(labels, "L2")["id"] == "L2"
    assert match_label(labels, "diésel")["id"] == "L2"
    with pytest.raises(AmbiguousError):
        match_label(labels + [{"id": "L3", "name": "Turbo", "source_ids": []}], "turbo")
    with pytest.raises(NotFoundError):
        match_label(labels, "frenos")


def test_assign_source_is_idempotent():
    f = Fake()
    already = asyncio.run(assign_source(f, NB, "Turbo", S1))
    assert already["changed"] is False and f.assigned == []
    done = asyncio.run(assign_source(f, NB, "Turbo", S2))
    assert done["changed"] is True and f.assigned == [("L1", S2)]


def test_assign_source_must_exist_in_notebook():
    with pytest.raises(NotFoundError):
        asyncio.run(assign_source(Fake(), NB, "Turbo", "no-existe"))


def test_add_text_validation():
    for title, content in (("", "x"), ("t", "   "), ("t" * 201, "x")):
        with pytest.raises(ValueError):
            asyncio.run(add_text(Fake(), NB, title, content))
    out = asyncio.run(add_text(Fake(), NB, "  MAPA ", "índice"))
    assert out == {"notebook_id": NB, "source_id": "new", "title": "MAPA", "reconciled": False}


# ---------------- tools ----------------
def test_tools_registered_with_right_destructiveness():
    t = discover_tools()
    for name in ("label_list", "label_auto", "label_add_source", "source_add_text"):
        assert t[name].destructive is False
    assert t["label_reorganize"].destructive is True


def test_label_reorganize_uses_scope_all():
    f = Fake()
    asyncio.run(discover_tools()["label_reorganize"].run(f, notebook=NB))
    assert f.scope == "all"


# ---------------- transporte (servidor simulado) ----------------
HOME = '<script>{"SNlM0e":"CSRF","FdrFJe":"SID","cfb2h":"bl"}</script>'
NB_ROW = ["Motores", [[[S1], "manual.pdf"], [["MAPA-ID"], "MAPA"]], NB]


def _env(rpc, payload=None, status=None):
    return ")]}'\n" + json.dumps([["wrb.fr", rpc, json.dumps(payload) if status is None else None,
                                  None, None, [status] if status else None]])


def _transport(monkeypatch, responses):
    seen = []

    def handler(req):
        seen.append(req)
        if req.method == "GET":
            return httpx.Response(200, text=HOME)
        rpc = req.url.params["rpcids"]
        r = responses[rpc]
        if isinstance(r, Exception):
            raise r
        return r if isinstance(r, httpx.Response) else httpx.Response(200, text=r)

    real = httpx.AsyncClient
    monkeypatch.setattr(be.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    return be.BatchExecuteTransport("SID=x"), seen


def _f_req(req):
    return json.loads(json.loads(parse_qs(req.content.decode())["f.req"][0])[0][0][1])


def test_transport_list_labels(monkeypatch):
    t, seen = _transport(monkeypatch, {"I3xc3c": _env("I3xc3c", [[_label("Turbo", [S1], "L1")]])})
    data = asyncio.run(t.call("list_labels", notebook_id=NB)).data
    assert data[0]["id"] == "L1"
    assert seen[1].url.params["source-path"] == f"/notebook/{NB}"
    assert _f_req(seen[1]) == [OPTS, NB]


def test_transport_generate_labels_reads_index_1(monkeypatch):
    t, seen = _transport(monkeypatch,
                         {"agX4Bc": _env("agX4Bc", [None, [_label("Turbo", [S1], "L1")]])})
    data = asyncio.run(t.call("generate_labels", notebook_id=NB, scope="unlabeled")).data
    assert data[0]["name"] == "Turbo" and _f_req(seen[1])[4] == [False]


def test_transport_add_text_ok(monkeypatch):
    t, seen = _transport(monkeypatch, {"izAoDd": _env("izAoDd", [[[["new-src"], "MAPA"]]])})
    data = asyncio.run(t.call("add_text_source", notebook_id=NB, title="MAPA",
                              content="índice")).data
    assert data == {"id": "new-src", "title": "MAPA", "reconciled": False}
    assert _f_req(seen[1])[2] == OPTS


def test_transport_add_text_pending_status_reconciles_by_title(monkeypatch):
    t, _ = _transport(monkeypatch, {"izAoDd": _env("izAoDd", status=9),
                                    "rLM1Ne": _env("rLM1Ne", [NB_ROW])})
    data = asyncio.run(t.call("add_text_source", notebook_id=NB, title="MAPA", content="x")).data
    assert data == {"id": "MAPA-ID", "title": "MAPA", "reconciled": True}


def test_transport_add_text_connection_cut_reconciles(monkeypatch):
    t, _ = _transport(monkeypatch, {"izAoDd": httpx.ReadTimeout("cortado"),
                                    "rLM1Ne": _env("rLM1Ne", [NB_ROW])})
    data = asyncio.run(t.call("add_text_source", notebook_id=NB, title="MAPA", content="x")).data
    assert data["reconciled"] is True


def test_transport_add_text_unconfirmed_when_not_found(monkeypatch):
    t, _ = _transport(monkeypatch, {"izAoDd": httpx.ReadTimeout("cortado"),
                                    "rLM1Ne": _env("rLM1Ne", [NB_ROW])})
    with pytest.raises(UnconfirmedWriteError) as e:
        asyncio.run(t.call("add_text_source", notebook_id=NB, title="Otra", content="x"))
    assert classify(e.value).category == Category.SOURCE_ADD


def test_transport_add_text_real_refusal_is_not_reconciled(monkeypatch):
    t, seen = _transport(monkeypatch, {"izAoDd": _env("izAoDd", status=7)})
    with pytest.raises(RpcRefusedError):
        asyncio.run(t.call("add_text_source", notebook_id=NB, title="MAPA", content="x"))
    assert all(r.url.params.get("rpcids") != "rLM1Ne" for r in seen)


def test_unconfirmed_write_is_not_resent_by_cascade():
    class _T:
        def __init__(self, name, exc):
            self.name, self.exc, self.calls = name, exc, 0

        def available(self):
            return True

        async def call(self, op, **kw):
            self.calls += 1
            raise self.exc

    first = _T("android", UnconfirmedWriteError("dudosa"))
    second = _T("web", RuntimeError("no debería llamarse"))
    with pytest.raises(UnconfirmedWriteError):
        asyncio.run(Cascade([first, second]).call("add_text_source"))
    assert second.calls == 0
