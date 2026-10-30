"""Fase A — Deep Research / Fast Research: iniciar, estado, importar (con informe y
reconciliación). Sin red real."""
import asyncio
import json
from urllib.parse import parse_qs

import httpx
import pytest

from notebooklm_hub._app.errors import Category, NotFoundError, NotReadyError, classify
from notebooklm_hub._app.research import import_results, start, status
from notebooklm_hub.core.transport import batchexecute as be
from notebooklm_hub.core.transport import web_research as wr
from notebooklm_hub.core.transport.base import TransportError, UnconfirmedWriteError
from notebooklm_hub.tools.registry import discover_tools

NB = "aaaaaaaa-0000-4000-8000-000000000001"


def _web(url, title):
    return [url, title, "pista", 1]


def _report(title, md):
    return [None, title, None, 5, None, None, [md, 3], None, 0]


def _task(tid, code, sources=(), query="motores turbo", summary="resumen"):
    return [tid, [None, [query, 1], 2, [list(sources), summary], code]]


# ---------------- protocolo puro ----------------
def test_start_params_fast_and_deep():
    assert wr.build_start_params(NB, "q", "fast") == ("START_FAST_RESEARCH",
                                                      [["q", 1], None, 1, NB])
    assert wr.build_start_params(NB, "q", "deep") == ("START_DEEP_RESEARCH",
                                                      [None, [1], ["q", 1], 5, NB])
    with pytest.raises(ValueError):
        wr.build_start_params(NB, "q", "turbo")


def test_parse_start_requires_task_id():
    assert wr.parse_start(["t-1", "r-1"]) == {"task_id": "t-1", "report_id": "r-1"}
    for bad in (None, [], [None]):
        with pytest.raises(TransportError):
            wr.parse_start(bad)


@pytest.mark.parametrize("code,expected", [
    (1, "in_progress"), (2, "completed"), (6, "completed"),
    (3, "no_results"), (4, "cancelled"), (99, "failed"), (None, "in_progress"),
])
def test_status_codes_never_wait_forever(code, expected):
    # jacob-bd trata 3 y 4 como "en curso" → se quedaría esperando para siempre
    assert wr.parse_poll([[_task("t", code)]])[0]["status"] == expected


def test_parse_poll_results_web_and_report():
    payload = [[_task("t-1", 6, [_web("https://a.com", "A"), _report("Informe", "# MD")])]]
    t = wr.parse_poll(payload)[0]
    assert t["task_id"] == "t-1" and t["query"] == "motores turbo" and t["summary"] == "resumen"
    web, rep = t["results"]
    assert web == {"index": 0, "kind": "web", "url": "https://a.com", "title": "A",
                   "report_markdown": None}
    assert rep["kind"] == "report" and rep["report_markdown"] == "# MD" and rep["url"] is None


def test_parse_poll_compat_report_shape_and_flat_and_garbage():
    compat = [None, ["Informe", "## texto"], None, 5]
    t = wr.parse_poll([_task("t", 2, [compat])])[0]          # lista plana de tareas
    assert t["results"][0]["report_markdown"] == "## texto"
    assert wr.parse_poll(None) == [] and wr.parse_poll([["roto"]]) == []


def test_import_entries_and_params():
    results = [{"kind": "web", "url": "https://a.com", "title": "A", "report_markdown": None},
               {"kind": "report", "url": None, "title": "Inf", "report_markdown": "# md"},
               {"kind": "report", "url": None, "title": "Vacío", "report_markdown": None}]
    entries = wr.build_import_entries(results)
    assert entries == [
        [None, None, ["https://a.com", "A"], None, None, None, None, None, None, None, 2],
        [None, ["Inf", "# md"], None, 3, None, None, None, None, None, None, 3],
    ]
    assert wr.build_import_params(NB, "t", entries) == [None, [1], "t", NB, entries]


def test_parse_import_wrapped_and_flat():
    rows = [[["s1"], "A"], [["s2"], "Inf"]]
    assert wr.parse_import([rows]) == wr.parse_import(rows) == [
        {"id": "s1", "title": "A"}, {"id": "s2", "title": "Inf"}]
    assert wr.parse_import(None) == []


# ---------------- lógica neutral ----------------
class Fake:
    def __init__(self, tasks=None, existing=()):
        self.tasks = tasks if tasks is not None else wr.parse_poll(
            [[_task("t-1", 6, [_web("https://a.com", "A"), _web("https://b.com", "B"),
                               _report("Informe", "# MD")])]])
        self.existing = list(existing)
        self.imported = None

    async def list_notebooks(self):
        return [{"id": NB, "title": "Motores"}]

    async def research_start(self, nb_id, query, mode):
        self.started = (query, mode)
        return {"task_id": "t-new", "report_id": None}

    async def research_poll(self, nb_id):
        return self.tasks

    async def get_notebook(self, nb_id):
        return {"sources": [{"id": f"x{i}", "title": t} for i, t in enumerate(self.existing)]}

    async def research_import(self, nb_id, task_id, results):
        self.imported = results
        return {"imported": [{"id": "n", "title": r["title"]} for r in results],
                "reconciled": False}


def test_start_validates_and_defaults_to_deep():
    f = Fake()
    out = asyncio.run(start(f, "Motores", "  cómo elegir un turbo  "))
    assert out["task_id"] == "t-new" and out["mode"] == "deep" and f.started == (
        "cómo elegir un turbo", "deep")
    for q, m in (("", "deep"), ("x" * 2001, "deep"), ("q", "raro")):
        with pytest.raises(ValueError):
            asyncio.run(start(Fake(), NB, q, m))


def test_status_latest_and_by_id_and_missing():
    out = asyncio.run(status(Fake(), NB))
    assert out["status"] == "completed" and out["done"] is True and out["result_count"] == 3
    assert out["results"][2] == {"index": 2, "kind": "report", "title": "Informe", "url": None,
                                 "has_report": True}
    with pytest.raises(NotFoundError):
        asyncio.run(status(Fake(), NB, "otro"))
    with pytest.raises(NotFoundError):
        asyncio.run(status(Fake(tasks=[]), NB))


def test_import_requires_completed():
    running = wr.parse_poll([[_task("t-1", 1)]])
    with pytest.raises(NotReadyError) as e:
        asyncio.run(import_results(Fake(tasks=running), NB, "t-1"))
    assert classify(e.value).category == Category.NOT_READY and classify(e.value).retriable


def test_import_all_including_report_by_default():
    f = Fake()
    out = asyncio.run(import_results(f, NB, "t-1"))
    assert [r["title"] for r in f.imported] == ["A", "B", "Informe"]
    assert len(out["imported"]) == 3 and out["skipped"] == []


def test_import_indices_and_without_report():
    f = Fake()
    asyncio.run(import_results(f, NB, "t-1", indices=[1, 2], include_report=False))
    assert [r["title"] for r in f.imported] == ["B"]
    with pytest.raises(ValueError):
        asyncio.run(import_results(Fake(), NB, "t-1", indices=[7]))


def test_import_is_idempotent_by_title():
    f = Fake(existing=["A", "Informe"])
    out = asyncio.run(import_results(f, NB, "t-1"))
    assert [r["title"] for r in f.imported] == ["B"] and out["skipped"] == ["A", "Informe"]
    g = Fake(existing=["A", "B", "Informe"])
    out2 = asyncio.run(import_results(g, NB, "t-1"))
    assert g.imported is None and out2["imported"] == []


def test_tools_registered():
    t = discover_tools()
    for name in ("research_start", "research_status", "research_import"):
        assert name in t and t[name].destructive is False


# ---------------- transporte (servidor simulado) ----------------
HOME = '<script>{"SNlM0e":"CSRF","FdrFJe":"SID","cfb2h":"bl"}</script>'


def _env(rpc, payload=None, status_code=None):
    inner = json.dumps(payload) if status_code is None else None
    return ")]}'\n" + json.dumps([["wrb.fr", rpc, inner, None, None,
                                   [status_code] if status_code else None]])


def _nb(sources):
    return [["Motores", [[[sid], t] for sid, t in sources], NB]]


def _transport(monkeypatch, handler_map):
    seen = []
    counters = {}

    def handler(req):
        seen.append(req)
        if req.method == "GET":
            return httpx.Response(200, text=HOME)
        rpc = req.url.params["rpcids"]
        counters[rpc] = counters.get(rpc, 0) + 1
        r = handler_map[rpc]
        r = r(counters[rpc]) if callable(r) else r
        if isinstance(r, Exception):
            raise r
        return httpx.Response(200, text=r)

    real = httpx.AsyncClient
    monkeypatch.setattr(be.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    return be.BatchExecuteTransport("SID=x"), seen


def _f_req(req):
    return json.loads(json.loads(parse_qs(req.content.decode())["f.req"][0])[0][0][1])


def test_transport_start_deep_and_poll(monkeypatch):
    t, seen = _transport(monkeypatch, {
        "QA9ei": _env("QA9ei", ["t-1", "r-1"]),
        "e3bVqc": _env("e3bVqc", [[_task("t-1", 2, [_web("https://a.com", "A")])]]),
    })
    started = asyncio.run(t.call("research_start", notebook_id=NB, query="q", mode="deep")).data
    assert started["task_id"] == "t-1" and _f_req(seen[1]) == [None, [1], ["q", 1], 5, NB]
    tasks = asyncio.run(t.call("research_poll", notebook_id=NB)).data
    assert tasks[0]["status"] == "completed" and _f_req(seen[2]) == [None, None, NB]


def test_transport_import_ok_uses_long_timeout(monkeypatch):
    t, seen = _transport(monkeypatch, {
        "rLM1Ne": _env("rLM1Ne", _nb([("s0", "viejo")])),
        "LBwxtb": _env("LBwxtb", [[[["s1"], "A"]]]),
    })
    entries = wr.build_import_entries([{"kind": "web", "url": "https://a.com", "title": "A",
                                        "report_markdown": None}])
    data = asyncio.run(t.call("research_import", notebook_id=NB, task_id="t-1",
                              entries=entries)).data
    assert data == {"imported": [{"id": "s1", "title": "A"}], "reconciled": False}
    imp = next(r for r in seen if r.url.params.get("rpcids") == "LBwxtb")
    assert _f_req(imp) == [None, [1], "t-1", NB, entries]


def test_transport_import_cut_reconciles_by_id_diff(monkeypatch):
    t, _ = _transport(monkeypatch, {
        "rLM1Ne": lambda n: _env("rLM1Ne", _nb([("s0", "viejo")] if n == 1
                                               else [("s0", "viejo"), ("s1", "A")])),
        "LBwxtb": httpx.ReadTimeout("cortado"),
    })
    data = asyncio.run(t.call("research_import", notebook_id=NB, task_id="t", entries=[])).data
    assert data == {"imported": [{"id": "s1", "title": "A"}], "reconciled": True}


def test_transport_import_cut_without_changes_is_unconfirmed(monkeypatch):
    t, _ = _transport(monkeypatch, {
        "rLM1Ne": _env("rLM1Ne", _nb([("s0", "viejo")])),
        "LBwxtb": httpx.ReadTimeout("cortado"),
    })
    with pytest.raises(UnconfirmedWriteError):
        asyncio.run(t.call("research_import", notebook_id=NB, task_id="t", entries=[]))
