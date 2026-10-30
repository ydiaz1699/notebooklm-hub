"""Estado persistente del motor (SQLite, biblioteca estándar).

Guarda: ejecuciones de workflows, el resultado de cada paso, aprobaciones con alcance, la última
foto de cada cuaderno y un registro de decisiones (auditoría). Nunca cookies ni tokens.

Garantías:
  · Una sola ejecución ACTIVA por (perfil, cuaderno, workflow): índice único parcial + transacción
    BEGIN IMMEDIATE → dos llamadas simultáneas no crean dos ejecuciones.
  · Sobrevive a reinicios: cada paso se guarda en cuanto termina.
  · Una aprobación vale solo para su cuaderno + workflow + versión.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
ACTIVE = ("pending", "running", "waiting_approval", "blocked")
RUN_STATUSES = ACTIVE + ("completed", "failed", "cancelled")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    profile TEXT NOT NULL,
    notebook_id TEXT NOT NULL,
    workflow TEXT NOT NULL,
    version INTEGER NOT NULL,
    status TEXT NOT NULL,
    params_json TEXT NOT NULL DEFAULT '{}',
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_run
    ON runs(profile, notebook_id, workflow)
    WHERE status IN ('pending', 'running', 'waiting_approval', 'blocked');
CREATE TABLE IF NOT EXISTS steps (
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    step_key TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    output_json TEXT,
    error TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (run_id, step_key)
);
CREATE TABLE IF NOT EXISTS approvals (
    profile TEXT NOT NULL,
    notebook_id TEXT NOT NULL,
    workflow TEXT NOT NULL,
    version INTEGER NOT NULL,
    approved_at TEXT NOT NULL,
    PRIMARY KEY (profile, notebook_id, workflow, version)
);
CREATE TABLE IF NOT EXISTS snapshots (
    profile TEXT NOT NULL,
    notebook_id TEXT NOT NULL,
    taken_at TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    PRIMARY KEY (profile, notebook_id)
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    at TEXT NOT NULL,
    kind TEXT NOT NULL,
    message TEXT NOT NULL,
    data_json TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


class Store:
    def __init__(self, path: Path | str, *, profile: str = "default") -> None:
        self.path = Path(path)
        self.profile = profile
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError(f"La base de estado es de una versión más nueva ({version}); "
                                   "actualiza notebooklm-hub.")
            conn.executescript(_SCHEMA)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        # Una conexión por operación (nada compartido entre llamadas MCP concurrentes).
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise

    # ------------------------------------------------------------------ ejecuciones
    def active_run(self, notebook_id: str, workflow: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE profile=? AND notebook_id=? AND workflow=? "
                f"AND status IN ({','.join('?' * len(ACTIVE))})",
                (self.profile, notebook_id, workflow, *ACTIVE)).fetchone()
        return self._run(row)

    def get_or_create_run(self, notebook_id: str, workflow: str, version: int,
                          params: dict[str, Any] | None = None) -> tuple[dict[str, Any], bool]:
        """Devuelve (ejecución, creada). Atómico: no duplica aunque haya llamadas simultáneas."""
        with self._tx() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE profile=? AND notebook_id=? AND workflow=? "
                f"AND status IN ({','.join('?' * len(ACTIVE))})",
                (self.profile, notebook_id, workflow, *ACTIVE)).fetchone()
            if row is not None:
                return self._run(row), False
            now = _now()
            run_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO runs(run_id, profile, notebook_id, workflow, version, status, "
                "params_json, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (run_id, self.profile, notebook_id, workflow, version, "pending",
                 _dumps(params or {}), now, now))
            row = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return self._run(row), True

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            return self._run(conn.execute("SELECT * FROM runs WHERE run_id=?",
                                          (run_id,)).fetchone())

    def set_run_status(self, run_id: str, status: str, error: str | None = None) -> None:
        if status not in RUN_STATUSES:
            raise ValueError(f"estado de ejecución inválido: {status}")
        with self._tx() as conn:
            conn.execute("UPDATE runs SET status=?, error=?, updated_at=? WHERE run_id=?",
                         (status, error, _now(), run_id))

    def last_run(self, notebook_id: str, workflow: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE profile=? AND notebook_id=? AND workflow=? "
                "ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (self.profile, notebook_id, workflow)).fetchone()
        return self._run(row)

    @staticmethod
    def _run(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        out["params"] = json.loads(out.pop("params_json") or "{}")
        return out

    # ------------------------------------------------------------------ pasos
    def steps(self, run_id: str) -> dict[str, dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM steps WHERE run_id=?", (run_id,)).fetchall()
        out = {}
        for r in rows:
            d = dict(r)
            d["output"] = json.loads(d.pop("output_json")) if d["output_json"] else None
            out[d["step_key"]] = d
        return out

    def start_step(self, run_id: str, step_key: str) -> int:
        """Marca un intento y devuelve el número de intento (antes de ejecutar)."""
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO steps(run_id, step_key, status, attempts, updated_at) "
                "VALUES (?,?,?,1,?) ON CONFLICT(run_id, step_key) DO UPDATE SET "
                "attempts = attempts + 1, status='running', updated_at=excluded.updated_at",
                (run_id, step_key, "running", _now()))
            conn.execute("UPDATE runs SET status='running', updated_at=? WHERE run_id=? "
                         "AND status IN ('pending','running')", (_now(), run_id))
            return conn.execute("SELECT attempts FROM steps WHERE run_id=? AND step_key=?",
                                (run_id, step_key)).fetchone()[0]

    def finish_step(self, run_id: str, step_key: str, output: Any) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO steps(run_id, step_key, status, attempts, output_json, updated_at) "
                "VALUES (?,?,?,0,?,?) ON CONFLICT(run_id, step_key) DO UPDATE SET "
                "status='done', output_json=excluded.output_json, error=NULL, "
                "updated_at=excluded.updated_at",
                (run_id, step_key, "done", _dumps(output), _now()))

    def fail_step(self, run_id: str, step_key: str, error: str) -> None:
        with self._tx() as conn:
            conn.execute("UPDATE steps SET status='failed', error=?, updated_at=? "
                         "WHERE run_id=? AND step_key=?", (error, _now(), run_id, step_key))

    # ------------------------------------------------------------------ aprobaciones
    def approve(self, notebook_id: str, workflow: str, version: int) -> None:
        with self._tx() as conn:
            conn.execute("INSERT OR IGNORE INTO approvals VALUES (?,?,?,?,?)",
                         (self.profile, notebook_id, workflow, version, _now()))

    def revoke(self, notebook_id: str, workflow: str) -> None:
        with self._tx() as conn:
            conn.execute("DELETE FROM approvals WHERE profile=? AND notebook_id=? AND workflow=?",
                         (self.profile, notebook_id, workflow))

    def is_approved(self, notebook_id: str, workflow: str, version: int) -> bool:
        with self._conn() as conn:
            return conn.execute(
                "SELECT 1 FROM approvals WHERE profile=? AND notebook_id=? AND workflow=? "
                "AND version=?", (self.profile, notebook_id, workflow, version)).fetchone() is not None

    # ------------------------------------------------------------------ fotos
    def save_snapshot(self, notebook_id: str, snapshot: dict[str, Any]) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO snapshots VALUES (?,?,?,?) ON CONFLICT(profile, notebook_id) "
                "DO UPDATE SET taken_at=excluded.taken_at, snapshot_json=excluded.snapshot_json",
                (self.profile, notebook_id, _now(), _dumps(snapshot)))

    def last_snapshot(self, notebook_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT snapshot_json FROM snapshots WHERE profile=? AND "
                               "notebook_id=?", (self.profile, notebook_id)).fetchone()
        return json.loads(row[0]) if row else None

    # ------------------------------------------------------------------ auditoría
    def log(self, run_id: str | None, kind: str, message: str, data: Any = None) -> None:
        with self._tx() as conn:
            conn.execute("INSERT INTO events(run_id, at, kind, message, data_json) "
                         "VALUES (?,?,?,?,?)",
                         (run_id, _now(), kind, message, _dumps(data) if data is not None else None))

    def events(self, run_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT at, kind, message, data_json FROM events WHERE run_id=? "
                                "ORDER BY id", (run_id,)).fetchall()
        return [{"at": r["at"], "kind": r["kind"], "message": r["message"],
                 "data": json.loads(r["data_json"]) if r["data_json"] else None} for r in rows]
