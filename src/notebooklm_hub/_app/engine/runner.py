"""Ejecutor de workflows: hace avanzar una ejecución paso a paso, guardando cada resultado.

Contrato de un workflow:
  · `id`, `version`, `describe(ctx)` (qué propone, para pedir aprobación)
  · `plan(ctx)` → lista ordenada de `Step`. Se recalcula en cada avance a partir de los
    resultados ya guardados, así los pasos pueden depender de lo anterior (p. ej. un paso por
    cada etiqueta que creó el autoetiquetado) y el plan es reproducible tras un reinicio.
Contrato de un paso de ESCRITURA: debe ser idempotente ("comprobar y luego actuar"), porque tras
un corte puede volver a ejecutarse.

Reglas del motor (docs/design/motor-inteligente.md §3):
  · aprobación con alcance (cuaderno + workflow + versión), pedida UNA vez;
  · presupuesto de tiempo por llamada: si se agota, devuelve `in_progress` y la siguiente
    llamada continúa (los clientes MCP cortan las llamadas largas);
  · escritura sin confirmar → `blocked` (no se reintenta a ciegas; ver `resume`);
  · cuota agotada / algo aún en curso → se pausa sin gastar intentos;
  · fallo normal → reintento hasta `max_attempts`, luego `failed`.
"""
from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from ...core.transport.base import RpcRefusedError, UnconfirmedWriteError
from ..errors import NotReadyError, classify
from .store import Store

StepKind = Literal["read", "write", "approval"]


@dataclass
class Context:
    client: Any
    notebook_id: str
    run_id: str
    params: dict[str, Any]
    outputs: dict[str, Any] = field(default_factory=dict)   # step_key → resultado guardado


@dataclass(frozen=True)
class Step:
    key: str
    kind: StepKind
    description: str
    action: Callable[[Context], Awaitable[Any]] | None = None
    verify: Callable[[Context, Any], Awaitable[bool]] | None = None
    max_attempts: int = 3


class Workflow(Protocol):
    id: str
    version: int

    def plan(self, ctx: Context) -> list[Step]: ...

    def describe(self, ctx: Context) -> dict[str, Any]: ...


def _summary(store: Store, run: dict[str, Any], status: str, **extra: Any) -> dict[str, Any]:
    steps = store.steps(run["run_id"])
    return {"run_id": run["run_id"], "workflow": run["workflow"], "version": run["version"],
            "notebook_id": run["notebook_id"], "status": status,
            "steps_done": sorted(k for k, s in steps.items() if s["status"] == "done"),
            **extra}


async def advance(store: Store, client: Any, workflow: Workflow, notebook_id: str, *,
                  params: dict[str, Any] | None = None, budget_seconds: float = 45.0,
                  clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    """Avanza la ejecución activa (o crea una) tanto como permita el presupuesto."""
    run, created = store.get_or_create_run(notebook_id, workflow.id, workflow.version, params)
    if created:
        store.log(run["run_id"], "created", f"Nueva ejecución de {workflow.id} v{workflow.version}")
    if run["version"] != workflow.version:
        store.set_run_status(run["run_id"], "cancelled",
                             f"El workflow cambió de v{run['version']} a v{workflow.version}")
        store.log(run["run_id"], "cancelled", "Versión obsoleta; se crea una nueva ejecución")
        return await advance(store, client, workflow, notebook_id, params=params,
                             budget_seconds=budget_seconds, clock=clock)
    if run["status"] == "blocked":
        return _summary(store, run, "blocked", error=run["error"],
                        next="Revisa el cuaderno y llama a resume para continuar.")

    started = clock()
    while True:
        saved = store.steps(run["run_id"])
        ctx = Context(client, notebook_id, run["run_id"], run["params"],
                      {k: s["output"] for k, s in saved.items() if s["status"] == "done"})
        pending = [s for s in workflow.plan(ctx) if saved.get(s.key, {}).get("status") != "done"]
        if not pending:
            store.set_run_status(run["run_id"], "completed")
            store.log(run["run_id"], "completed", "Workflow terminado")
            return _summary(store, run, "completed", outputs=ctx.outputs)
        step = pending[0]

        if step.kind == "approval":
            if store.is_approved(notebook_id, workflow.id, workflow.version):
                store.finish_step(run["run_id"], step.key, {"approved": True})
                store.log(run["run_id"], "approved", "Aprobación encontrada; se continúa")
                continue
            store.set_run_status(run["run_id"], "waiting_approval")
            return _summary(store, run, "waiting_approval", proposal=workflow.describe(ctx),
                            next=f"Pide confirmación al usuario y llama a approve "
                                 f"({workflow.id} v{workflow.version}).")

        if clock() - started > budget_seconds:
            store.set_run_status(run["run_id"], "running")
            return _summary(store, run, "in_progress", next_step=step.key,
                            next="Vuelve a llamar para continuar.")

        attempt = store.start_step(run["run_id"], step.key)
        try:
            output = await step.action(ctx) if step.action else None
            if step.verify and not await step.verify(ctx, output):
                raise UnconfirmedWriteError(f"El paso '{step.key}' no se pudo verificar.")
        except UnconfirmedWriteError as exc:
            store.fail_step(run["run_id"], step.key, str(exc))
            store.set_run_status(run["run_id"], "blocked", str(exc))
            store.log(run["run_id"], "blocked", str(exc), {"step": step.key})
            return _summary(store, run, "blocked", error=str(exc), step=step.key,
                            next="Revisa el cuaderno y llama a resume para continuar.")
        except (NotReadyError, RpcRefusedError) as exc:
            if isinstance(exc, RpcRefusedError) and exc.status != 8:
                return _fail(store, run, step, attempt, exc)      # negativa real (404/403…)
            # Cuota agotada (status 8) o algo aún en curso: pausa sin consumir el intento.
            store.fail_step(run["run_id"], step.key, str(exc))
            _refund_attempt(store, run["run_id"], step.key)
            store.set_run_status(run["run_id"], "running")
            return _summary(store, run, "in_progress", next_step=step.key, waiting=str(exc),
                            next="Espera un poco y vuelve a llamar.")
        except Exception as exc:  # noqa: BLE001 — se clasifica y se registra
            return _fail(store, run, step, attempt, exc)
        store.finish_step(run["run_id"], step.key, output)
        store.log(run["run_id"], "step_done", step.description, {"step": step.key})


def _refund_attempt(store: Store, run_id: str, step_key: str) -> None:
    with store._tx() as conn:
        conn.execute("UPDATE steps SET attempts = MAX(attempts - 1, 0) WHERE run_id=? "
                     "AND step_key=?", (run_id, step_key))


def _fail(store: Store, run: dict[str, Any], step: Step, attempt: int,
          exc: Exception) -> dict[str, Any]:
    ce = classify(exc)
    msg = f"{ce.category.value}: {ce.message}"
    store.fail_step(run["run_id"], step.key, msg)
    # Sin sentido reintentar: no existe, sin permiso o parámetros inválidos.
    permanent = ce.category.value in ("NOT_FOUND", "PERMISSION_DENIED", "CONFIG", "AMBIGUOUS")
    if attempt >= step.max_attempts or permanent:
        store.set_run_status(run["run_id"], "failed", msg)
        store.log(run["run_id"], "failed", msg, {"step": step.key, "attempt": attempt})
        return _summary(store, run, "failed", error=msg, step=step.key)
    store.set_run_status(run["run_id"], "running")
    store.log(run["run_id"], "step_error", msg, {"step": step.key, "attempt": attempt})
    return _summary(store, run, "in_progress", error=msg, step=step.key, attempt=attempt,
                    next="Error recuperable; vuelve a llamar para reintentar.")


def approve(store: Store, workflow: Workflow, notebook_id: str) -> dict[str, Any]:
    store.approve(notebook_id, workflow.id, workflow.version)
    run = store.active_run(notebook_id, workflow.id)
    if run and run["status"] == "waiting_approval":
        store.set_run_status(run["run_id"], "running")
    if run:
        store.log(run["run_id"], "approved", "Aprobado por el usuario")
    return {"approved": True, "workflow": workflow.id, "version": workflow.version,
            "notebook_id": notebook_id}


def resume(store: Store, workflow: Workflow, notebook_id: str) -> dict[str, Any]:
    """Desbloquea una ejecución `blocked`. El paso se repetirá: por eso los pasos de escritura
    deben comprobar primero si su efecto ya existe (idempotencia)."""
    run = store.active_run(notebook_id, workflow.id)
    if not run or run["status"] != "blocked":
        return {"resumed": False, "reason": "No hay ninguna ejecución bloqueada."}
    store.set_run_status(run["run_id"], "running")
    store.log(run["run_id"], "resumed", "Desbloqueada por el usuario")
    return {"resumed": True, "run_id": run["run_id"]}
