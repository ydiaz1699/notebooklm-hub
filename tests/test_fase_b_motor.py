"""Fase B — motor: rutas, almacén SQLite, foto, reglas, ejecutor y notebook_state.

Sin NotebookLM: cliente falso + base SQLite temporal. "Reiniciar el servidor" = abrir otro Store
sobre el mismo archivo.
"""
import asyncio
import sqlite3
import threading
from pathlib import Path

import pytest

from notebooklm_hub._app.engine import conventions as cv
from notebooklm_hub._app.engine import paths, rules, snapshot
from notebooklm_hub._app.engine.runner import Step, advance, approve, resume
from notebooklm_hub._app.engine.state import notebook_state
from notebooklm_hub._app.engine.store import Store
from notebooklm_hub._app.errors import NotFoundError, NotReadyError
from notebooklm_hub.core.transport.base import RpcRefusedError, UnconfirmedWriteError
from notebooklm_hub.tools.registry import discover_tools

NB = "aaaaaaaa-0000-4000-8000-000000000001"


@pytest.fixture
def db(tmp_path):
    return tmp_path / "state" / "state.db"


# ======================= rutas =======================
def test_state_dir_override_and_platform_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("NOTEBOOKLM_HUB_STATE_DIR", str(tmp_path / "x"))
    assert paths.state_dir() == tmp_path / "x" and paths.db_path() == tmp_path / "x" / "state.db"
    monkeypatch.delenv("NOTEBOOKLM_HUB_STATE_DIR")
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    assert paths.state_dir() == tmp_path / "xdg" / "notebooklm-hub"
    monkeypatch.delenv("XDG_STATE_HOME")
    assert paths.state_dir() == Path.home() / ".local" / "state" / "notebooklm-hub"
    monkeypatch.setattr(paths.sys, "platform", "darwin")
    assert paths.state_dir() == Path.home() / "Library" / "Application Support" / "notebooklm-hub"
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "lad"))
    assert paths.state_dir() == tmp_path / "lad" / "notebooklm-hub"


def test_profile_default_and_env(monkeypatch):
    monkeypatch.delenv("NOTEBOOKLM_HUB_PROFILE", raising=False)
    assert paths.profile() == "default"
    monkeypatch.setenv("NOTEBOOKLM_HUB_PROFILE", "trabajo")
    assert paths.profile() == "trabajo"


# ======================= almacén =======================
def test_one_active_run_and_persistence(db):
    s = Store(db)
    run, created = s.get_or_create_run(NB, "wf", 1, {"a": 1})
    again, created2 = Store(db).get_or_create_run(NB, "wf", 1)       # "reinicio"
    assert created and not created2 and again["run_id"] == run["run_id"]
    assert again["params"] == {"a": 1}
    s.set_run_status(run["run_id"], "completed")
    new, created3 = s.get_or_create_run(NB, "wf", 1)
    assert created3 and new["run_id"] != run["run_id"]
    assert s.last_run(NB, "wf")["run_id"] == new["run_id"]


def test_concurrent_creation_never_duplicates(db):
    Store(db)
    ids, errors = [], []

    def worker():
        try:
            ids.append(Store(db).get_or_create_run(NB, "wf", 1)[0]["run_id"])
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors and len(set(ids)) == 1
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1


def test_profiles_are_isolated(db):
    a, b = Store(db, profile="a"), Store(db, profile="b")
    ra = a.get_or_create_run(NB, "wf", 1)[0]
    rb = b.get_or_create_run(NB, "wf", 1)[0]
    assert ra["run_id"] != rb["run_id"]
    a.approve(NB, "wf", 1)
    assert a.is_approved(NB, "wf", 1) and not b.is_approved(NB, "wf", 1)


def test_approval_scope_and_revoke(db):
    s = Store(db)
    s.approve(NB, "wf", 1)
    assert Store(db).is_approved(NB, "wf", 1)                        # sobrevive al reinicio
    assert not s.is_approved(NB, "wf", 2)                           # otra versión
    assert not s.is_approved(NB, "otro", 1)                         # otro workflow
    assert not s.is_approved("otro-nb", "wf", 1)                    # otro cuaderno
    s.revoke(NB, "wf")
    assert not s.is_approved(NB, "wf", 1)


def test_steps_snapshot_events(db):
    s = Store(db)
    run = s.get_or_create_run(NB, "wf", 1)[0]
    assert s.start_step(run["run_id"], "k") == 1 and s.start_step(run["run_id"], "k") == 2
    s.finish_step(run["run_id"], "k", {"x": "ñ"})
    st = Store(db).steps(run["run_id"])["k"]
    assert st["status"] == "done" and st["output"] == {"x": "ñ"} and st["attempts"] == 2
    s.save_snapshot(NB, {"v": 1})
    s.save_snapshot(NB, {"v": 2})
    assert s.last_snapshot(NB) == {"v": 2} and s.last_snapshot("otro") is None
    s.log(run["run_id"], "k", "mensaje", {"d": 1})
    assert s.events(run["run_id"])[-1]["data"] == {"d": 1}
    with pytest.raises(ValueError):
        s.set_run_status(run["run_id"], "inventado")


def test_newer_schema_is_rejected(db):
    Store(db)
    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA user_version = 99")
    with pytest.raises(RuntimeError):
        Store(db)


# ======================= convenciones =======================
def test_note_titles_roundtrip_and_variants():
    t = cv.note_title(1, " Turbo ")
    assert t == "1. Puntos clave – Turbo" and cv.parse_note_title(t) == (1, "Turbo")
    assert cv.parse_note_title("2. índice de preguntas - Motor diésel") == (2, "Motor diésel")
    assert cv.parse_note_title("3.Síntesis — X") == (3, "X")
    assert cv.parse_note_title("1. Síntesis – X") is None          # número y tipo no casan
    assert cv.parse_note_title("manual.pdf") is None
    assert cv.is_map(" MAPA ") and not cv.is_map("Mapa mental")


# ======================= foto =======================
class FakeNB:
    def __init__(self, sources, labels=(), chat=None):
        self.sources = list(sources)
        self.labels = list(labels)
        self.chat = chat or {"goal": "default", "response_length": "default",
                             "custom_prompt": None}
        self.writes = 0

    async def list_notebooks(self):
        return [{"id": NB, "title": "Motores"}]

    async def get_notebook(self, nb_id):
        return {"id": nb_id, "title": "Motores",
                "sources": [{"id": i, "title": t} for i, t in self.sources]}

    async def list_labels(self, nb_id):
        return [{"id": lid, "name": n, "emoji": None, "source_ids": list(ids)}
                for lid, n, ids in self.labels]

    async def get_chat_settings(self, nb_id):
        return self.chat


def _many(n):
    return [(f"s{i}", f"doc{i}.pdf") for i in range(n)]


def test_snapshot_classifies_sources_and_notes():
    nb = FakeNB(sources=[("s1", "a.pdf"), ("s2", "b.pdf"), ("n1", cv.note_title(1, "Turbo")),
                         ("n2", cv.note_title(2, "turbo")), ("n3", cv.note_title(3, "Turbo")),
                         ("m", "MAPA"), ("s3", "c.pdf")],
                labels=[("L1", "Turbo", ["s1", "s2", "n1"])])
    snap = asyncio.run(snapshot.take(nb, NB))
    assert snap["original_count"] == 3 and snap["map_source_id"] == "m"
    assert snap["unlabeled_original_ids"] == ["s3"]
    lb = snap["labels"][0]
    assert lb["original_source_ids"] == ["s1", "s2"]                # las notas no cuentan
    assert lb["notes"] == {1: "n1", 2: "n2", 3: "n3"} and lb["complete"] is True
    assert snap["chat"]["customized"] is False
    assert nb.writes == 0                                           # solo lecturas


# ======================= reglas =======================
def _snap(**kw):
    base = {"original_count": 0, "labels": [], "unlabeled_original_ids": [],
            "map_source_id": None, "chat": {"customized": True}}
    base.update(kw)
    return base


def _lb(lid, name, ids, complete=False, fp=None):
    return {"id": lid, "name": name, "original_source_ids": ids, "complete": complete,
            "fingerprint": fp or snapshot._fingerprint(ids)}


def _recipes(findings):
    return [f["recipe"] for f in findings]


def test_rules_empty_notebook_wants_sources_and_chat():
    f = rules.evaluate(_snap(chat={"customized": False}))
    assert _recipes(f) == ["buscar_fuentes", "configurar_chat"]


def test_rules_single_document_wants_map():
    f = rules.evaluate(_snap(original_count=1))
    assert "mapa_de_cobertura" in _recipes(f)
    assert "mapa_de_cobertura" not in _recipes(rules.evaluate(_snap(original_count=1,
                                                                     map_source_id="m")))


def test_rules_many_mixed_sources_want_3_notes():
    f = rules.evaluate(_snap(original_count=14))
    assert f[0]["recipe"] == "metodo_3_notas" and f[0]["scope"] == {"labels": "all"}
    assert rules.evaluate(_snap(original_count=5)) == []            # pocas: nada que proponer
    th = rules.Thresholds(many_sources=5)
    assert _recipes(rules.evaluate(_snap(original_count=5), th=th)) == ["metodo_3_notas"]


def test_rules_pending_and_unlabeled_categories():
    snap = _snap(original_count=12, unlabeled_original_ids=["s9"],
                 labels=[_lb("L1", "Turbo", ["s1"], complete=True), _lb("L2", "Frenos", ["s2"]),
                         _lb("L3", "Vacía", [])])
    f = rules.evaluate(snap)
    scopes = [x["scope"] for x in f]
    assert {"labels": "unlabeled", "source_ids": ["s9"]} in scopes
    assert {"labels": ["Frenos"]} in scopes                         # Vacía no cuenta


def test_rules_stale_notes_when_sources_change():
    prev = _snap(labels=[_lb("L1", "Turbo", ["s1"], complete=True)])
    now = _snap(original_count=12, labels=[_lb("L1", "Turbo", ["s1", "s5"], complete=True)])
    f = rules.evaluate(now, prev)
    assert any(x["scope"].get("refresh") and x["scope"]["labels"] == ["Turbo"] for x in f)
    assert not rules.evaluate(prev | {"original_count": 12}, prev)


def test_thresholds_from_env(monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_HUB_MANY_SOURCES", "20")
    monkeypatch.setenv("NOTEBOOKLM_HUB_FEW_SOURCES", "nope")
    th = rules.Thresholds.from_env()
    assert th.many_sources == 20 and th.few_sources == 2


# ======================= ejecutor =======================
class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class Demo:
    """Workflow de prueba: aprobación → leer categorías → un paso por categoría → cierre."""
    id = "demo"
    version = 1

    def __init__(self, categories=("A", "B"), fail=None, clock=None):
        self.categories = categories
        self.calls = []
        self.fail = fail or {}
        self.clock = clock

    def describe(self, ctx):
        return {"plan": ["leer", "procesar cada categoría", "cerrar"]}

    def _act(self, key, value=None):
        async def run(ctx):
            self.calls.append(key)
            if self.clock:
                self.clock.t += 10
            exc = self.fail.get(key)
            if isinstance(exc, list):
                exc = exc.pop(0) if exc else None
            if exc:
                raise exc
            return value if value is not None else {"ok": key}
        return run

    def plan(self, ctx):
        steps = [Step("approval", "approval", "Aprobación del usuario"),
                 Step("read", "read", "Leer categorías", self._act("read", list(self.categories)))]
        for cat in ctx.outputs.get("read", []):                     # dinámico: según lo leído
            steps.append(Step(f"cat:{cat}", "write", f"Procesar {cat}", self._act(f"cat:{cat}")))
        if "read" in ctx.outputs:
            steps.append(Step("close", "read", "Cerrar", self._act("close")))
        return steps


def _adv(db, wf, **kw):
    return asyncio.run(advance(Store(db), object(), wf, NB, **kw))


def test_waits_for_approval_once_then_runs_everything(db):
    wf = Demo()
    out = _adv(db, wf)
    assert out["status"] == "waiting_approval" and out["proposal"]["plan"] and wf.calls == []
    approve(Store(db), wf, NB)
    out = _adv(db, wf)
    assert out["status"] == "completed"
    assert wf.calls == ["read", "cat:A", "cat:B", "close"]
    # La siguiente vez NO vuelve a pedir aprobación (misma versión) y crea ejecución nueva.
    wf2 = Demo(categories=("C",))
    assert _adv(db, wf2)["status"] == "completed" and wf2.calls == ["read", "cat:C", "close"]


def test_budget_splits_work_and_resumes_after_restart(db):
    clock = Clock()
    wf = Demo(categories=("A", "B", "C"), clock=clock)
    Store(db).approve(NB, "demo", 1)
    out = asyncio.run(advance(Store(db), object(), wf, NB, budget_seconds=15, clock=clock))
    assert out["status"] == "in_progress" and wf.calls == ["read", "cat:A"]
    # "reinicio del servidor": otro Store y otro objeto workflow sobre el mismo archivo
    wf_b = Demo(categories=("A", "B", "C"), clock=clock)
    out = asyncio.run(advance(Store(db), object(), wf_b, NB, budget_seconds=1000, clock=clock))
    assert out["status"] == "completed" and wf_b.calls == ["cat:B", "cat:C", "close"]


def test_unconfirmed_write_blocks_until_resume(db):
    wf = Demo(fail={"cat:A": [UnconfirmedWriteError("dudosa")]})
    Store(db).approve(NB, "demo", 1)
    out = _adv(db, wf)
    assert out["status"] == "blocked" and out["step"] == "cat:A"
    assert _adv(db, wf)["status"] == "blocked" and wf.calls.count("cat:A") == 1   # no reintenta
    assert resume(Store(db), wf, NB)["resumed"] is True
    assert _adv(db, wf)["status"] == "completed" and wf.calls.count("cat:A") == 2
    assert resume(Store(db), wf, NB)["resumed"] is False


def test_failed_verification_blocks(db):
    class V(Demo):
        def plan(self, ctx):
            async def bad(_ctx, _out):
                return False
            return [Step("w", "write", "Escribir", self._act("w"), verify=bad)]
    assert _adv(db, V())["status"] == "blocked"


def test_quota_and_not_ready_pause_without_spending_attempts(db):
    quota = RpcRefusedError("cuota", status=8, label="RESOURCE_EXHAUSTED")
    wf = Demo(fail={"read": [quota, NotReadyError("en curso"), quota, quota]})
    Store(db).approve(NB, "demo", 1)
    for _ in range(4):
        assert _adv(db, wf)["status"] == "in_progress"
    assert _adv(db, wf)["status"] == "completed"                    # 5º intento real: va
    run = Store(db).last_run(NB, "demo")
    assert Store(db).steps(run["run_id"])["read"]["attempts"] == 1


def test_transient_errors_retry_then_fail(db):
    boom = RuntimeError("fallo raro")
    wf = Demo(fail={"read": [boom, boom, boom]})
    Store(db).approve(NB, "demo", 1)
    assert _adv(db, wf)["status"] == "in_progress"
    assert _adv(db, wf)["status"] == "in_progress"
    out = _adv(db, wf)
    assert out["status"] == "failed" and "fallo raro" in out["error"]
    assert Store(db).active_run(NB, "demo") is None


def test_permanent_errors_fail_immediately(db):
    wf = Demo(fail={"read": [NotFoundError("no existe")]})
    Store(db).approve(NB, "demo", 1)
    out = _adv(db, wf)
    assert out["status"] == "failed" and out["error"].startswith("NOT_FOUND")


def test_new_workflow_version_cancels_old_run_and_needs_new_approval(db):
    Store(db).approve(NB, "demo", 1)
    clock = Clock()
    v1 = Demo(categories=("A", "B"), clock=clock)
    asyncio.run(advance(Store(db), object(), v1, NB, budget_seconds=5, clock=clock))
    v2 = Demo()
    v2.version = 2
    assert _adv(db, v2)["status"] == "waiting_approval"             # v1 no autoriza v2
    old = [r for r in sqlite3.connect(db).execute("SELECT status FROM runs ORDER BY created_at")]
    assert ("cancelled",) in old


def test_audit_log_explains_what_happened(db):
    wf = Demo(categories=("A",))
    Store(db).approve(NB, "demo", 1)
    _adv(db, wf)
    run = Store(db).last_run(NB, "demo")
    kinds = [e["kind"] for e in Store(db).events(run["run_id"])]
    assert kinds[0] == "created" and "approved" in kinds and kinds[-1] == "completed"


# ======================= notebook_state =======================
def test_notebook_state_first_visit_then_changes(db):
    nb = FakeNB(sources=_many(12))
    out = asyncio.run(notebook_state(nb, "Motores", store=Store(db)))
    assert out["first_visit"] is True and out["changes"] is None
    assert out["summary"]["original_sources"] == 12
    assert [r["recipe"] for r in out["recommendations"]] == ["metodo_3_notas", "configurar_chat"]
    nb.sources.append(("s99", "nuevo.pdf"))
    out2 = asyncio.run(notebook_state(nb, NB, store=Store(db)))
    assert out2["first_visit"] is False and out2["changes"]["added_sources"] == ["s99"]


def test_notebook_state_tool_registered_readonly():
    t = discover_tools()["notebook_state"]
    assert t.destructive is False
