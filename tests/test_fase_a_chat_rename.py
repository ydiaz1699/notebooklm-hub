"""Fase A — personalización del chat (leer/mezclar/escribir/verificar) y renombrar fuente."""
import asyncio
import json
from urllib.parse import parse_qs

import httpx
import pytest

from notebooklm_hub._app.chat_settings import configure, get_settings, plan_settings
from notebooklm_hub._app.errors import NotFoundError
from notebooklm_hub._app.sources import rename
from notebooklm_hub.core.transport import batchexecute as be
from notebooklm_hub.core.transport import web_settings as wst
from notebooklm_hub.core.transport.base import TransportError, UnconfirmedWriteError
from notebooklm_hub.tools.registry import discover_tools

NB = "aaaaaaaa-0000-4000-8000-000000000001"
DEFAULT = {"goal": "default", "response_length": "default", "custom_prompt": None}


def _row(settings=None, n=8):
    row = ["Motores", [[["s1"], "manual"]], NB, None, None, [1], None]
    if settings is not None:
        row.append(settings)
    return row


# ---------------- protocolo puro ----------------
@pytest.mark.parametrize("block,expected", [
    (None, DEFAULT),
    ([[], []], DEFAULT),                                      # la web omite los por defecto
    ([[1], [1]], DEFAULT),
    ([[2, "Eres un tutor"], [4]], {"goal": "custom", "response_length": "longer",
                                   "custom_prompt": "Eres un tutor"}),
    ([[2, "persona"], []], {"goal": "custom", "response_length": "default",
                            "custom_prompt": "persona"}),
    ([[3], [5]], {"goal": "learning_guide", "response_length": "shorter", "custom_prompt": None}),
])
def test_parse_chat_settings_shapes(block, expected):
    row = _row() if block is None else _row(block)
    assert wst.parse_chat_settings(row) == expected


@pytest.mark.parametrize("block", ["raro", [[2, "x"]], [["2"], [1]], [[9], [1]], [[True], [1]]])
def test_parse_chat_settings_drift_is_loud(block):
    with pytest.raises(TransportError):
        wst.parse_chat_settings(_row(block))


def test_configure_params_match_web():
    p = wst.build_configure_params(NB, goal="custom", response_length="longer",
                                   custom_prompt="Responde en español")
    assert p == [NB, [[None, None, None, None, None, None, None,
                       [[2, "Responde en español"], [4]]]]]
    p2 = wst.build_configure_params(NB, goal="default", response_length="default",
                                    custom_prompt="se ignora")
    assert p2[1][0][7] == [[1], [1]]
    with pytest.raises(ValueError):
        wst.build_configure_params(NB, goal="custom", response_length="default", custom_prompt="")
    with pytest.raises(ValueError):
        wst.build_configure_params(NB, goal="custom", response_length="default",
                                   custom_prompt="x" * 10_001)


def test_rename_params():
    assert wst.build_rename_source_params("s1", "MAPA") == [None, ["s1"], [[["MAPA"]]]]


# ---------------- mezcla (lectura-mezcla-escritura) ----------------
CUSTOM_LONG = {"goal": "custom", "response_length": "longer", "custom_prompt": "persona vieja"}


def test_plan_only_prompt_keeps_length_and_sets_custom():
    assert plan_settings(DEFAULT, goal=None, response_length=None, custom_prompt="nuevo") == \
        {"goal": "custom", "response_length": "default", "custom_prompt": "nuevo"}
    assert plan_settings(CUSTOM_LONG, goal=None, response_length=None, custom_prompt="nuevo") == \
        {"goal": "custom", "response_length": "longer", "custom_prompt": "nuevo"}


def test_plan_only_length_keeps_existing_prompt():
    # el error #1751 de teng-lin: cambiar la longitud NO debe borrar la persona
    assert plan_settings(CUSTOM_LONG, goal=None, response_length="shorter",
                         custom_prompt=None)["custom_prompt"] == "persona vieja"


def test_plan_validation():
    with pytest.raises(ValueError):
        plan_settings(DEFAULT, goal=None, response_length=None, custom_prompt=None)
    with pytest.raises(ValueError):
        plan_settings(DEFAULT, goal="custom", response_length=None, custom_prompt=None)
    with pytest.raises(ValueError):
        plan_settings(DEFAULT, goal="raro", response_length=None, custom_prompt=None)
    with pytest.raises(ValueError):
        plan_settings(DEFAULT, goal=None, response_length=None, custom_prompt="x" * 10_001)


# ---------------- lógica neutral con cliente falso ----------------
class Fake:
    def __init__(self, settings=None, apply=True, titles=None):
        self.settings = dict(settings or DEFAULT)
        self.apply = apply
        self.sent = None
        self.titles = titles or {"s1": "manual.pdf"}
        self.renamed = None

    async def list_notebooks(self):
        return [{"id": NB, "title": "Motores"}]

    async def get_chat_settings(self, nb_id):
        return dict(self.settings)

    async def configure_chat(self, nb_id, **kw):
        self.sent = kw
        if self.apply:
            self.settings = dict(kw)
        return {"ok": True}

    async def get_notebook(self, nb_id):
        return {"id": nb_id, "sources": [{"id": k, "title": v} for k, v in self.titles.items()]}

    async def rename_source(self, nb_id, sid, title):
        self.renamed = (sid, title)
        if self.apply:
            self.titles[sid] = title
        return {}


def test_get_settings_reports_customization():
    out = asyncio.run(get_settings(Fake(CUSTOM_LONG), "Motores"))
    assert out["is_customized"] is True and out["notebook_id"] == NB
    assert asyncio.run(get_settings(Fake(), NB))["is_customized"] is False


def test_configure_verifies_and_returns_previous():
    f = Fake(CUSTOM_LONG)
    out = asyncio.run(configure(f, NB, custom_prompt="nueva persona"))
    assert out["changed"] is True and out["previous"] == CUSTOM_LONG
    assert f.sent == {"goal": "custom", "response_length": "longer",
                      "custom_prompt": "nueva persona"}


def test_configure_noop_when_equal():
    f = Fake(CUSTOM_LONG)
    out = asyncio.run(configure(f, NB, custom_prompt="persona vieja"))
    assert out["changed"] is False and f.sent is None


def test_configure_unconfirmed_if_readback_differs():
    with pytest.raises(UnconfirmedWriteError):
        asyncio.run(configure(Fake(apply=False), NB, custom_prompt="x"))


def test_rename_checks_before_and_after():
    f = Fake()
    out = asyncio.run(rename(f, NB, "s1", " 1. Puntos clave – Turbo "))
    assert out == {"notebook_id": NB, "source_id": "s1", "title": "1. Puntos clave – Turbo",
                   "previous_title": "manual.pdf", "changed": True}
    with pytest.raises(NotFoundError):
        asyncio.run(rename(Fake(), NB, "no-existe", "x"))
    same = asyncio.run(rename(Fake(), NB, "s1", "manual.pdf"))
    assert same["changed"] is False
    with pytest.raises(UnconfirmedWriteError):
        asyncio.run(rename(Fake(apply=False), NB, "s1", "otro"))


def test_tools_registered():
    t = discover_tools()
    for name in ("chat_settings_get", "chat_configure", "source_rename"):
        assert name in t and t[name].destructive is False


# ---------------- transporte (servidor simulado) ----------------
HOME = '<script>{"SNlM0e":"CSRF","FdrFJe":"SID","cfb2h":"bl"}</script>'


def _env(rpc, payload):
    return ")]}'\n" + json.dumps([["wrb.fr", rpc, json.dumps(payload), None, None, None]])


def _transport(monkeypatch, responses):
    seen = []

    def handler(req):
        seen.append(req)
        if req.method == "GET":
            return httpx.Response(200, text=HOME)
        rpc = req.url.params["rpcids"]
        return httpx.Response(200, text=responses[rpc])

    real = httpx.AsyncClient
    monkeypatch.setattr(be.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    return be.BatchExecuteTransport("SID=x"), seen


def _f_req(req):
    return json.loads(json.loads(parse_qs(req.content.decode())["f.req"][0])[0][0][1])


def test_transport_get_chat_settings(monkeypatch):
    t, _ = _transport(monkeypatch, {"rLM1Ne": _env("rLM1Ne", [_row([[2, "p"], [5]])])})
    data = asyncio.run(t.call("get_chat_settings", notebook_id=NB)).data
    assert data == {"goal": "custom", "response_length": "shorter", "custom_prompt": "p"}


def test_transport_configure_and_rename_send_web_format(monkeypatch):
    t, seen = _transport(monkeypatch, {"s0tc2d": _env("s0tc2d", []),
                                       "b7Wfje": _env("b7Wfje", [])})
    asyncio.run(t.call("configure_chat", notebook_id=NB, goal="custom",
                       response_length="default", custom_prompt="hola"))
    assert _f_req(seen[1])[1][0][7] == [[2, "hola"], [1]]
    asyncio.run(t.call("rename_source", notebook_id=NB, source_id="s1", title="MAPA"))
    assert _f_req(seen[2]) == [None, ["s1"], [[["MAPA"]]]]
    assert seen[2].url.params["source-path"] == f"/notebook/{NB}"
