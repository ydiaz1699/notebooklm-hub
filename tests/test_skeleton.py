"""Smoke test de Fase 0: el esqueleto importa y el patrón de registro/cascada funciona.

No prueba acceso real a NotebookLM (eso es Fase 1+). Prueba que la *arquitectura* es coherente.
"""
import asyncio

from notebooklm_hub.core.transport.base import Transport, TransportError, TransportResult
from notebooklm_hub.core.transport.cascade import Cascade
from notebooklm_hub.tools.registry import ToolSpec, discover_tools
from notebooklm_hub._app.errors import Category, classify


def test_registry_discovers_nothing_but_template():
    # En Fase 0 no hay tools reales; la plantilla (_template) se ignora por el prefijo "_".
    tools = discover_tools()
    assert isinstance(tools, dict)


def test_toolspec_shape():
    t = ToolSpec(name="x", description="d", params={}, run=lambda c: None)
    assert t.destructive is False


class _FakeTransport:
    def __init__(self, name, *, ok, available=True):
        self.name = name
        self._ok = ok
        self._available = available

    def available(self):
        return self._available

    async def call(self, operation, **params):
        if self._ok:
            return TransportResult(data={"op": operation, "via": self.name}, backend=self.name)
        raise TransportError(f"{self.name} caído")


def test_cascade_falls_back_to_next_level():
    # android falla → web responde: la cascada debe devolver el de web.
    casc = Cascade([
        _FakeTransport("android", ok=False),
        _FakeTransport("web", ok=True),
        _FakeTransport("browser", ok=True),
    ])
    res = asyncio.run(casc.call("ask", question="hola"))
    assert res.backend == "web"


def test_cascade_all_fail_raises_transport_error():
    casc = Cascade([_FakeTransport("web", ok=False)])
    try:
        asyncio.run(casc.call("ask"))
        assert False, "debería haber lanzado"
    except TransportError as exc:
        assert classify(exc).category == Category.TRANSPORT
