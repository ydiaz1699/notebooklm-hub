"""Fase 1 — tests de lo verificable SIN red (parsers puros, registry, verbo ask, errores).

El acceso real a NotebookLM (cookies + salida a Google) se verifica en el NAS del usuario; aquí se
prueba que la lógica, el parseo del protocolo y el cableado de las fachadas son correctos.
"""
import asyncio
import json

import pytest

from notebooklm_hub._app.ask import AskRequest, build_ask_plan, execute_ask
from notebooklm_hub._app.errors import Category, classify
from notebooklm_hub.core.transport.base import TransportError, TransportResult
from notebooklm_hub.core.transport.batchexecute import parse_batchexecute, parse_query_response
from notebooklm_hub.tools.registry import discover_tools


# ---- registry: la tool real aparece sola ----
def test_registry_discovers_notebook_ask():
    tools = discover_tools()
    assert "notebook_ask" in tools
    assert tools["notebook_ask"].destructive is False


# ---- parser batchexecute (protocolo real) ----
def test_parse_batchexecute_extracts_inner_payload():
    inner = {"hello": "world"}
    text = ")]}'\n\n" + json.dumps([["wrb.fr", "wXbhsf", json.dumps(inner), None, None, None]])
    assert parse_batchexecute(text, "wXbhsf") == inner


def test_parse_batchexecute_drift_when_no_envelope():
    text = ")]}'\n" + json.dumps([["wrb.fr", "OTRO_ID", "[]", None, None, None]])
    with pytest.raises(TransportError) as e:
        parse_batchexecute(text, "wXbhsf")
    assert "drift" in str(e.value).lower()
    assert e.value.retriable is False


def test_parse_batchexecute_refusal_status():
    # status 7 = PERMISSION_DENIED en el índice 5 → negativa de DOMINIO (no cae en cascada)
    from notebooklm_hub.core.transport.base import RpcRefusedError
    text = ")]}'\n" + json.dumps([["wrb.fr", "wXbhsf", None, None, None, [7]]])
    with pytest.raises(RpcRefusedError) as e:
        parse_batchexecute(text, "wXbhsf")
    assert "PERMISSION_DENIED" in str(e.value) and e.value.status == 7


def test_parse_batchexecute_unauthenticated_is_transport():
    # status 16 = UNAUTHENTICATED → problema del canal: TransportError reintentable
    text = ")]}'\n" + json.dumps([["wrb.fr", "wXbhsf", None, None, None, [16]]])
    with pytest.raises(TransportError) as e:
        parse_batchexecute(text, "wXbhsf")
    assert e.value.retriable is True


def test_parse_query_response_picks_longest_string():
    body = ")]}'\n" + json.dumps([["wrb.fr", "x", json.dumps(["corto", "esta es la respuesta larga del notebook"])]])
    assert parse_query_response(body)["answer"] == "esta es la respuesta larga del notebook"


# ---- verbo ask (neutral) ----
def test_build_ask_plan_validates():
    with pytest.raises(ValueError):
        build_ask_plan(AskRequest(notebook="", question="x"))
    with pytest.raises(ValueError):
        build_ask_plan(AskRequest(notebook="nb", question="  "))
    ok = build_ask_plan(AskRequest(notebook="nb", question="¿qué dice?"))
    assert ok.notebook == "nb"


_NB_ID = "11111111-2222-4333-8444-555555555555"


class _FakeClient:
    async def list_notebooks(self):
        return [{"id": _NB_ID, "title": "mi-nb"}]

    async def ask(self, notebook_id, question, source_ids=None):
        return {"answer": "respuesta de prueba", "conversation_id": "c1", "notebook_id": notebook_id}


def test_execute_ask_end_to_end_with_fake_client():
    # Desde Fase 3 el nombre se resuelve a ID canónico antes de preguntar.
    plan = build_ask_plan(AskRequest(notebook="mi-nb", question="hola"))
    res = asyncio.run(execute_ask(plan, _FakeClient()))
    assert res.answer == "respuesta de prueba"
    assert res.notebook_id == _NB_ID


# ---- clasificación de errores ----
def test_classify_valueerror_is_config():
    assert classify(ValueError("falta notebook")).category == Category.CONFIG


def test_classify_transport_error():
    ce = classify(TransportError("todo cayó", retriable=True))
    assert ce.category == Category.TRANSPORT and ce.retriable is True


# ---- transporte: contrato y disponibilidad ----
def test_batchexecute_available_requires_cookies():
    from notebooklm_hub.core.transport.batchexecute import BatchExecuteTransport
    assert BatchExecuteTransport("").available() is False
    assert BatchExecuteTransport("SID=abc").available() is True
    assert isinstance(TransportResult(data=1, backend="web").backend, str)
