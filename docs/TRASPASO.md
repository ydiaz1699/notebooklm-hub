# Traspaso de sesión — leer PRIMERO en un chat nuevo

**Última actualización:** 2026-10-29 · **Estado de `main`:** 165/165 tests, 15 tools, PRs #1–#13
fusionados, ninguno abierto.

Este documento es **autocontenido**: un chat sin contexto previo debe poder continuar el trabajo
leyendo solo esto (y los archivos que enlaza cuando necesite detalle).

---

## 1. Qué es el proyecto (en 5 líneas)

- `notebooklm-hub` = **MCP propio** de Google NotebookLM (que no tiene API oficial) + REST para
  n8n. Código propio en `src/notebooklm_hub/`.
- Objetivo 1: ser **el mejor de 7 proyectos no oficiales** (ideas destiladas, no copiadas).
- Objetivo 2 (en curso): un **MCP inteligente** que sabe en qué estado está cada cuaderno, qué
  conviene hacer y lo ejecuta solo, sin que el LLM decida cada paso ni el usuario tenga que
  acordarse de los métodos o pegar prompts.
- La IA que organiza y genera contenido es **la de NotebookLM** (autoetiquetado, chat). El MCP
  orquesta con código. **No** se usa SDK de Gemini ni framework de agentes (decidido, ver
  `docs/design/motor-inteligente.md` §2).

## 2. Reglas que NO se rompen

| Regla | Dónde está |
|---|---|
| Antes de implementar algo, **comparar los 7 repos** y elegir la mejor variante de cada detalle; registrar la decisión | `.kiro/steering/mejor-de-los-7.md`, `docs/provenance/capabilities-matrix.md` §4bis |
| `_drafts/notebooklm/` (copia de jacob-bd) era **solo para probar la conexión**: no es la base | steering |
| **Créditos solo en `CREDITS.md`**; ningún archivo lleva cabecera de autor/atribución | `CREDITS.md`, `CONTRIBUTING.md` |
| **Portable**: nada depende del framework del NAS (`$dkco`, etc.). Estado en `NOTEBOOKLM_HUB_STATE_DIR` o carpeta estándar del SO | `_app/engine/paths.py` |
| Leer **nunca** modifica NotebookLM; toda escritura se **verifica releyendo**; escritura dudosa → `UnconfirmedWriteError` (no se reintenta a ciegas ni por otro transporte) | `core/transport/base.py` |
| Una tool = un archivo en `tools/`; las fachadas MCP/REST no tienen lógica | `CONTRIBUTING.md` |
| Los prompts de IA MASIVA se pueden redistribuir (colaboración) | `CREDITS.md`, `docs/design/recetas.md` §7 |

## 3. Limitaciones del entorno (Kiro Web)

- **Sin salida a Google ni cookies:** nada se ha probado contra NotebookLM real. Todo está
  probado con un servidor HTTP simulado (`httpx.MockTransport`) y clientes falsos. La prueba
  real la hace el usuario en el NAS (ver §8). Decirlo siempre al entregar.
- PRs: con `gh api repos/ydiaz1699/notebooklm-hub/pulls` (REST; `gh pr create` falla). Antes de
  empujar, comprobar si el PR está fusionado; si lo está, rama nueva desde `main`. Si un trabajo
  depende de un PR abierto, **apilar** la rama encima y avisar del orden de fusión.
- `/tmp` a veces no es visible entre llamadas del sandbox: para archivos que haya que releer
  (imágenes, extractos), usar una carpeta dentro de `/projects/sandbox/`.
- Repos de referencia para comparar:
  `git clone --depth 1 https://github.com/teng-lin/notebooklm-py.git /tmp/refs/notebooklm-py`
  (ídem `roomi-fields/notebooklm-mcp`, `ishandutta2007/notebooklm-api`). jacob-bd está en
  `_drafts/notebooklm/`.

## 4. Mapa del código

```
src/notebooklm_hub/
  tools/            15 tools (una por archivo; registry.py las descubre solas)
  _app/             lógica neutral (no sabe de MCP/REST)
    notebooks.py    list/get + resolver "nombre o ID" (ambiguo → AMBIGUOUS, no adivina)
    ask.py          preguntar con citas + conversación real
    labels.py       etiquetas (leer / autoetiquetar / meter fuente)
    sources.py      añadir texto como fuente / renombrar
    chat_settings.py personalizar chat (leer → mezclar → escribir → verificar)
    research.py     Fast/Deep Research (start → status → import)
    errors.py       categorías de error (CONFIG, NOT_FOUND, AMBIGUOUS, NOT_READY…)
    engine/         MOTOR INTELIGENTE (fase B)
      paths.py      carpeta de estado portable + perfil
      store.py      SQLite: runs, steps, approvals, snapshots, events
      conventions.py nombres fijos: "1. Puntos clave – <cat>", "2. Índice de preguntas – <cat>",
                    "3. Síntesis – <cat>", "MAPA"
      snapshot.py   foto del cuaderno (solo lectura)
      rules.py      foto(+anterior) → recomendaciones con motivo (pura)
      runner.py     ejecutor de workflows (advance / approve / resume)
      state.py      notebook_state (foto + reglas + cambios desde la última visita)
  core/client.py    API única hacia los transportes
  core/transport/   batchexecute.py (+ web_chat, web_labels, web_sources, web_settings,
                    web_research: funciones puras del protocolo), cascade.py, base.py
  facades/          mcp_server.py, rest_api.py (finas)
tests/              test_phase1, test_phase3_*, test_fase_a_*, test_fase_b_motor
```

### Tools actuales (15) — `*` = destructiva, pide `confirm`

`notebook_list`, `notebook_get`, `notebook_ask`, `notebook_state`, `label_list`, `label_auto`,
`label_reorganize*`, `label_add_source`, `source_add_text`, `source_rename`, `chat_settings_get`,
`chat_configure`, `research_start`, `research_status`, `research_import`.

## 5. Contrato del motor (lo que hay que respetar en la fase C)

- **Workflow** = objeto con `id`, `version`, `describe(ctx)` (propuesta para aprobar) y
  `plan(ctx) -> list[Step]`. `plan` se recalcula en cada avance con los resultados guardados en
  `ctx.outputs` (por eso puede generar un paso por etiqueta tras autoetiquetar).
- **Step** = `key` estable (p. ej. `label:<label_id>:nota1`), `kind` (`read` / `write` /
  `approval`), `action(ctx)`, `verify(ctx, out)` opcional, `max_attempts`.
- **Los pasos de escritura deben ser idempotentes** ("comprobar y luego actuar"): tras un
  bloqueo y `resume` se repiten. Ej.: antes de crear la nota 1, buscar si ya existe una fuente
  con ese título.
- `advance(store, client, workflow, notebook_id, budget_seconds=45)` devuelve `status`:
  `waiting_approval` (con `proposal`), `in_progress` (volver a llamar), `blocked` (necesita
  revisión + `resume`), `failed`, `completed`.
- Aprobación con alcance: cuaderno + workflow + **versión** (subir la versión pide aprobar otra
  vez). Cuota (status 8) / `NotReadyError` → pausa sin gastar intentos.

## 6. Siguiente: FASE C (por hacer)

### 6.1 Receta R3 · método de las 3 notas → `_app/engine/workflows/metodo_3_notas.py`
Prompts: copiar `_drafts/prompt/2/{1-Puntos clave por fuente.md, 2- Índice de preguntas y
problemas.md, 3- Síntesis y conclusiones accionables.md}` a
`src/notebooklm_hub/_app/recipes/prompts/` **sin cabecera** (créditos ya en `CREDITS.md`).
Cargar con `importlib.resources` (que se empaqueten en el wheel).

Pasos (`plan`):
1. `approval`.
2. `labels` (write): si no hay etiquetas o hay fuentes originales sin etiqueta →
   `generate_labels(scope="unlabeled")`; guarda el conjunto de etiquetas.
3. Por cada etiqueta con fuentes originales y sin sus 3 notas (o desactualizada si
   `params.refresh`):
   - `label:<id>:nota1` → `client.ask(nb, prompt1, source_ids=originales_de_la_etiqueta)`;
     **seguir mientras la respuesta termine en `CONTINUAR: faltan …`** pidiendo "continúa" en la
     misma `conversation_id` y concatenar (límite de vueltas: **pendiente de decidir**, propuesta
     5) → `add_text_source(title=note_title(1, cat))` → `assign_source_to_label`.
     Idempotente: si ya existe una fuente con ese título, reutilizarla.
   - `nota2` igual con prompt 2; `nota3` con prompt 3 y `source_ids = originales + nota1 + nota2`
     (el prompt 3 lo exige).
4. `verify` (read): nueva foto; todas las categorías procesadas `complete`.

Avisos de diseño ya registrados (`docs/design/recetas.md` §4): "apagar el ruido" (dejar solo
las 3 notas activas) **solo** se puede hacer al preguntar por el MCP (las fuentes marcadas en la
web son estado de la página); el usuario lo hace a mano si chatea en la web. Pendiente de
confirmar en real.

### 6.2 Tool `notebook_assist` (puerta de entrada única)
- `notebook_assist(notebook)` → `notebook_state` + si hay una ejecución activa, la avanza; si
  no, devuelve la recomendación principal con su plan (`describe`).
- `notebook_assist(notebook, approve="metodo_3_notas")` → `runner.approve` + `advance`.
- `notebook_assist(notebook, resume=True)` → `runner.resume` + `advance`.
- **Elicitation MCP** (`ctx.elicit` en FastMCP 4.1.4) para pedir el "sí" directamente al
  usuario; **plan B obligatorio** (devolver `waiting_approval` y que el LLM pregunte) porque el
  soporte en Kiro/Claude no está verificado. Requiere que la fachada MCP pase el `Context` de
  FastMCP a la tool sin meter lógica en la fachada (diseñarlo con cuidado).
- Store por defecto: `engine.state.default_store()`.

### 6.3 Tests a escribir (con cliente falso)
Un cuaderno de 12 fuentes y 2 categorías completa R3 en varias llamadas; `CONTINUAR` se
encadena; reintento tras bloqueo no duplica notas; fuentes nuevas → solo esa categoría; las
notas quedan con el título y la etiqueta correctos; la nota 3 recibe nota1+nota2.

### 6.4 Después de R3
R4 mapa de cobertura (`_drafts/prompt/1`: prompt → fuente `MAPA` → `chat_configure` con la
instrucción de navegar el MAPA, **mezclando** con la personalización existente), R1 configurar
chat (pedir objetivo/tono/prohibiciones una vez o proponerlos con `notebook_ask`), R2 buscar
fuentes (falta el **prompt de investigación** del vídeo: pedírselo al usuario).

## 7. Decisiones pendientes del usuario

1. **Límite de continuaciones** cuando la respuesta acaba en `CONTINUAR: faltan…` (propuesta: 5
   por nota; al superarlo, parar y avisar).
2. **Prompt de investigación** para R2 (el vídeo lo menciona; no está en `_drafts/prompt/`).

## 8. Primera prueba real (la hace el usuario en el NAS)

```bash
uv venv && uv pip install -e ".[mcp,rest]"
export NOTEBOOKLM_HUB_COOKIES="SID=...; HSID=...; ..."     # cuenta DEDICADA
nlmhub-rest &                                               # 127.0.0.1:9420
curl -s localhost:9420/tools/notebook_list  -H 'content-type: application/json' -d '{}'
curl -s localhost:9420/tools/notebook_state -H 'content-type: application/json' -d '{"notebook":"<NOMBRE>"}'
```
Empezar por las de **solo lectura** (`notebook_list`, `notebook_get`, `label_list`,
`chat_settings_get`, `notebook_state`). Si algo falla por formato, los parsers lanzan "drift";
anotar la respuesta cruda y corregir en el `web_*.py` correspondiente (ver
`docs/transport/README.md`, override `NOTEBOOKLM_HUB_RPC_OVERRIDES`).

## 9. Pendientes de mantenimiento (otros repos)

Ver `docs/ROADMAP.md` §"Pendientes de mantenimiento": mover `docs/mcp-toolbox.md` a
`Varios_tools/construir-mcp`, añadir `notebooklm-hub` a `ydiaz1699/repo-index`, catalogar
`playwright-mcp`, y las fichas de los proyectos WinOLS. Requieren una sesión con esos repos.

## 10. Cómo verificar

```bash
uv venv && uv pip install -e ".[mcp,rest,dev]"
.venv/bin/python -m pytest -q          # 165 en verde (solo tests/; _drafts tiene los suyos)
.venv/bin/ruff check src tests         # 3 avisos antiguos conocidos (cascade.py, test_skeleton.py)
```
