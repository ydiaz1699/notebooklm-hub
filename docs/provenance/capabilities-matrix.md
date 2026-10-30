# Matriz de capacidades — destilado de los proyectos NotebookLM existentes

**Propósito:** preservar *qué sabía hacer cada proyecto* y *qué tomamos de cada uno*, para poder
construir y mantener `notebooklm-hub` aunque los repos originales desaparezcan.

**Verificado contra la fuente real** (API de GitHub + READMEs/código) el **2026-10-04**.
Regla del proyecto: enlazar y destilar, **no** copiar código ni lógica de producto.

---

## 1. Los proyectos evaluados (hechos reales a 2026-10-04)

| Proyecto | Tipo | ⭐ | Lang | Transporte | Estado | Licencia |
|---|---|---|---|---|---|---|
| `teng-lin/notebooklm-py` | API+CLI+MCP (38 tools) + skill | ~19.6k | Python | gRPC Android + batchexecute + browser | 🟢 activo | MIT |
| `jacob-bd/gemini-notebook-mcp-cli` | CLI(`nlm`)+MCP+skills, en PyPI | ~6.2k | Python | web RPC + browser | 🟢 activo | MIT |
| `roomi-fields/notebooklm-mcp` | MCP + **REST 33 endpoints** | ~188 | TS | batchexecute + browser fallback (dual) | 🟢 activo | MIT |
| `ishandutta2007/notebooklm-api` (`open-notebooklm`) | API+CLI+skill | ~6 | Python | batchexecute + gRPC Android | 🟢 nuevo, sin tracción | MIT |
| `Zidong-LLC/notebooklm-skill` | Skill Claude Code | ~2 | Python | browser (basado en PleasePrompto) | 🟡 estancado | MIT |
| `PleasePrompto/notebooklm-mcp` | MCP (Patchright stealth) | ~3.4k | TS | solo browser | 🔴 **ARCHIVADO** | MIT |
| `PleasePrompto/notebooklm-skill` | Skill Claude Code | ~7.8k | Python | solo browser | 🔴 **ARCHIVADO** | MIT |

> **Nota de supervivencia:** los dos `PleasePrompto` están **archivados** (sin mantenimiento desde
> sep-2026). `Zidong` deriva de ellos y está estancado. La "familia Python viva" útil como
> referencia es **teng-lin**, **jacob-bd** e **ishandutta**; **roomi-fields** es la referencia
> para REST/n8n. Esto confirma la premisa del proyecto: **no depender de ninguno**.

---

## 2. Matriz de capacidades (🟢 fuerte · 🟡 parcial · ⚪ no)

| Capacidad | teng-lin | roomi | jacob-bd | ishandutta | → en notebooklm-hub |
|---|:---:|:---:|:---:|:---:|---|
| API Python importable | 🟢 | ⚪(TS) | 🟢 | 🟢 | **sí** (núcleo) |
| CLI | 🟢 | 🟡 | 🟢 | 🟢 | **sí** (`nlmhub`) |
| MCP server (stdio+http) | 🟢 | 🟢 | 🟢 | 🟢 | **sí** (fachada) |
| REST API HTTP | 🟡 | 🟢 **33 endpoints** | ⚪ | 🟡 | **sí** (fachada, para n8n) |
| En PyPI | 🟢 | 🟡(npm) | 🟢 | 🟢 | objetivo |
| Studio: audio | 🟢 | 🟢 | 🟢 | 🟢 | sí |
| Studio: vídeo | 🟢 | 🟢 | 🟡 | 🟢 (cinematic) | sí |
| Studio: infografía/report/slides | 🟢 | 🟢 | 🟡 | 🟢 | sí |
| Studio: flashcards/quiz/mind-map | ⚪ | ⚪ | ⚪ | 🟢 | sí (de ishandutta) |
| Deep Research | 🟢 | 🟡 | 🟢 | 🟡 | sí |
| Citas / source grounding | 🟢 | 🟢 (97%) | 🟢 | 🟢 | sí |
| Leer texto indexado de fuente | 🟢 `source_read` | 🟢 paginado | 🟡 | 🟡 | sí (paginado) |
| Multi-cuenta / perfiles | 🟢 | 🟢 rotación | 🟢 | 🟢 | sí |
| Auto-reauth desatendido | 🟢 master-token | 🟢 TOTP | 🟡 | 🟢 master-token | **sí** (clave headless) |
| Headless sin navegador | 🟢 (gRPC) | 🟡 | 🟡 | 🟢 (gRPC) | **sí** (gRPC preferido) |
| Confirmación en destructivas | 🟢 `confirm`+preview | 🟡 | ⚪ | ⚪ | **sí** (de teng-lin) |
| Errores estructurados/retriable | 🟢 CODE+retriable | 🟡 | ⚪ | ⚪ | **sí** (de teng-lin) |
| Instalador que cablea clientes | 🟡 | ⚪ | 🟢 12+ clientes | 🟡 | sí (de jacob-bd) |
| n8n/Zapier/Make listo | ⚪ | 🟢 (su razón de ser) | ⚪ | ⚪ | **sí** (REST) |
| Batch 1000+ preguntas | 🟡 | 🟢 patrón | 🟡 | ⚪ | sí |
| Vault / cache searchable | ⚪ | 🟢 `vault_batch` | ⚪ | ⚪ | sí (de roomi) |

---

## 3. Qué tomamos de cada proyecto (y por qué)

### teng-lin/notebooklm-py — base de diseño
- **Arquitectura `client → _app → fachadas`** (ADR-0021): núcleo neutral + MCP/REST/CLI finos.
  → **adoptada tal cual** como columna vertebral de la mantenibilidad.
- **Disciplina de tools:** name-or-ID en todo, IDs canónicos de vuelta, destructivas con
  `confirm`+preview, errores estructurados `CODE: msg (retriable=…)`, long-running no bloqueante
  (`*_generate → *_status → *_download`). → **adoptada** (va directo a permisos ask/allow).
- **Transporte Android gRPC + master-token** documentado con evidencias en `docs/android/`.
  → **destilado** en [`docs/transport/`](../transport/) (lo más difícil de reconstruir).

### roomi-fields/notebooklm-mcp — automatización
- **REST API de 33 endpoints** (NotebookLM como paso de n8n/cron/curl). → patrón de la fachada REST.
- **Transporte dual** batchexecute + **fallback navegador** → nivel 3 de nuestra cascada.
- `vault_batch` (cachear respuestas como vault searchable), batch 1000+, rotación multi-cuenta.

### jacob-bd/gemini-notebook-mcp-cli — experiencia de uso
- CLI `nlm` muy pulida (`doctor`, `doctor auth-replay`, `cross query`, `pipeline run`, `usage`).
- **Instalador que detecta y conecta 12+ clientes** y empaqueta skill en .zip. En PyPI.

### ishandutta2007/open-notebooklm — generadores Studio
- Más tipos de artefacto: `flashcards`, `quiz`, `mind-map`, `cinematic-video`, `data-table`.
- gRPC Android + master-token (misma familia que teng-lin). Sin tracción → solo referencia.

### PleasePrompto (×2) y Zidong — referencia histórica
- Enfoque **solo-navegador** (Patchright stealth) y estructura de **skill** de Claude Code.
  → útil como ejemplo de empaquetado de skill y de técnicas anti-detección del navegador
  (nivel 3). **No** como base: archivados / estancados.

---

## 4. Inventario de tools/endpoints reales (referencia para portar)

### teng-lin — 38 MCP tools (familias)
- **notebook_**: create, list, delete(confirm), rename/update, get
- **source_**: add (url/text/file/drive, `bytes_base64`), list, read (texto indexado), delete(confirm), wait
- **studio_**: generate (async: task_id), status, download, retry, delete(confirm)  → audio/vídeo/report/…
- **research_**: start, status, import
- **chat_**: start, status, ask, cancel  (async para generaciones lentas)
- **note_**: list, get
- **share_**: set_user(confirm), remove_user(confirm)
- **await_upload**, **get_health**
- Convenciones: name-or-ID, IDs canónicos de vuelta, `confirm` en destructivas, `STRICT_IDS` opt-in,
  errores `CODE: message (retriable=…)` con códigos `CONFIG/DEPENDENCY/NOTEBOOK_LIMIT/ARTIFACT_TIMEOUT/…`

### roomi-fields — REST (33 endpoints, extracto real)
```
GET  /health
POST /ask
GET/POST/PUT/DELETE  /notebooks  /notebooks/:id  /notebooks/:id/activate
POST /notebooks/auto-discover   POST /notebooks/create   POST /notebooks/import-from-scrape
GET  /notebooks/scrape  /notebooks/search  /notebooks/stats
GET/POST/DELETE  /content  /content/sources  /content/sources/:id
POST /content/generate  /content/notes  /content/chat-to-note  /content/notes/:t/to-source
GET  /content/download
GET  /sessions   POST /sessions/:id/reset   DELETE /sessions/:id
POST /setup-auth  /re-auth  /de-auth  /cleanup-data
```
MCP namespaces: `notebook_ask/create`, `source_add/list/read`, `content_delete`, `note_list/get`,
`session_list`, `server_health`, `vault_batch`, `research_sources`, `share_notebook`.

### jacob-bd — CLI `nlm` (extracto real)
```
nlm login [--profile/--provider/--manual/switch/profile]   nlm auth refresh   nlm auth storage
nlm notebook create/list/query     nlm source add/sync      nlm studio create
nlm audio create   nlm download [all/audio]   nlm report get   nlm slides revise
nlm research start   nlm batch query   nlm cross query   nlm chats list   nlm tag add
nlm pipeline run   nlm usage   nlm doctor [auth-replay]   nlm share public
nlm setup [add/list/remove]   nlm skill install/package/update   nlm config set
```

### ishandutta — CLI `notebooklm` (generadores, extracto real)
```
notebooklm login [--browser/--browser-cookies/--master-token]   auth check/refresh
notebooklm ask [--prompt-file]   create   metadata --json   agent show
notebooklm generate  audio|video|cinematic-video|report|slide-deck|infographic|data-table|mind-map|flashcards|quiz
notebooklm download  audio|video|slide-deck|infographic|data-table|mind-map|flashcards|quiz
notebooklm --backend android      mcp --transport ...
```

---

## 4bis. Regla "el mejor de los 7" (cómo se implementa cada capacidad)

`_drafts/notebooklm/` (copia de jacob-bd) **solo sirvió para probar la conexión**. No es la base.
Antes de implementar una capacidad:

1. Leer cómo la resuelven **todos** los repos que la implementan (no solo el que esté a mano).
2. Comparar en una tabla y quedarse con la mejor variante de cada detalle (pueden venir de repos
   distintos). Registrar la decisión abajo con su procedencia.
3. Si dos fuentes se contradicen, gana la que dice "live-observed"/tiene test de regresión, y se
   anota la discrepancia.

### Decisiones registradas

**Notebooks: list / get / resolución nombre→ID** (Fase 3, bloque 1 — 2026-10-29).
Comparados: teng-lin (`_web/notebooks.py`, `_web/rows/notebooks.py`, `_web/rows/sources.py`),
jacob-bd (`core/notebooks.py`, `core/conversation.py`), roomi (no aplica: lo hace por navegador).

| Detalle | Elegido | De | Descartado |
|---|---|---|---|
| Notebook inexistente | gRPC status 5 **o** payload vacío → `NOT_FOUND` + aviso "puede ser de otra cuenta" | teng-lin (#2132) | jacob-bd: error genérico |
| Negativa del backend (5/7/8) | Error de **dominio**: la cascada NO cae a otro transporte (daría lo mismo) | teng-lin | — |
| UNAUTHENTICATED / UNIMPLEMENTED (16/12) | Error de **transporte**: la cascada sí prueba otro | propio | — |
| ID de fuente | 3 formas: plano, `[id]`, Drive `[None, True, [id]]` | teng-lin `SourceRow.id` | jacob-bd: perdía las de Drive |
| `meta[0]` | Rol `owner/editor/viewer` (+ `is_owned`) | teng-lin enums | jacob-bd: 1=mío/2=compartido |
| `meta[1]` | `is_shared` | jacob-bd (observación) | — |
| `meta[5]` | `last_viewed_at` (lista ordenada por último visto) | teng-lin (live-observed) | jacob-bd: "modificado" |
| Título | Quitar prefijo `thought\n` | teng-lin | — |
| Forma desconocida | **Drift** explícito, no `[]` silencioso | teng-lin | jacob-bd: `[]` |
| `ask` sin fuentes | `GET_NOTEBOOK` → todas las fuentes | jacob-bd = teng-lin | (nuestra Fase 1: lista vacía) |
| Nombre ambiguo | No adivinar → `AMBIGUOUS` con candidatos | teng-lin (convención name-or-ID) | — |

**Chat: `ask` (respuesta, citas, conversación)** (Fase 3 — 2026-10-29).
Comparados: teng-lin (`_chat.py`, `_web/params/chat_stream.py`, `_web/rows/chat_stream.py`,
`_web/rows/chat.py`, `_web/rows/documents.py`), jacob-bd (`core/conversation.py`), roomi
(`src/rpc/query-rpc.ts`). Resultado: roomi es una variante de jacob-bd; teng-lin gana en todo.
Implementado en `core/transport/web_chat.py` (funciones puras).

| Detalle | Elegido | De | Descartado |
|---|---|---|---|
| Campos de la petición | 9: `[fuentes, pregunta, historial, [2,None,[1],[1]], conv_id, None, None, notebook_id, 1]` | teng-lin | jacob-bd/roomi: 5 campos, sin notebook_id |
| Conversación nueva | `conv_id=None` → el servidor continúa la del notebook (visible en la web); id **real** con `hPTbtc` después | teng-lin (#659, live) | jacob-bd/roomi: UUID inventado → turnos fantasma |
| Sin id tras responder | Devolver respuesta + `warning`, sin inventar id | propio (teng-lin lanza error; aquí se prioriza no perder la respuesta) | — |
| Seguimiento explícito | `conv_id` + historial de turnos del proceso | teng-lin `ConversationCache` | — |
| Qué fragmento es la respuesta | Final del servidor (`inner[4]`) > respuesta más larga > texto sin marcar | teng-lin (#2122) | jacob-bd/roomi: solo "la más larga" |
| Marca de respuesta | `first[4][4] == 1` | teng-lin | roomi/jacob-bd: último elemento de `[4]` |
| ID de fuente en cita | Primer UUID dentro de `detalle[5]` | teng-lin | ruta fija `[5][0][0][0]` |
| Texto citado | Elementos en `detalle[4][0]` → párrafo → `[inicio, fin, [texto]]`; tablas "[tabla]" | teng-lin (#2120: antes 37 de 556 chars) | — |
| Numeración de citas | Posición 1-based con huecos si una cita está rota | teng-lin = jacob-bd | — |
| Score | 0–1, descartando bool/NaN/fuera de rango | teng-lin | — |
| Cuota agotada | `UserDisplayableError` o stream cortado sin payload → `NOTEBOOK_LIMIT` (429, reintentable) | teng-lin | roomi: código numérico suelto |
| Pregunta demasiado larga | status 3 → mensaje "acórtala" | teng-lin (#1472) | — |
| Marco `er` / forma desconocida | Error explícito / drift, nunca respuesta vacía silenciosa | teng-lin | — |
| CSRF renovado | Reconstruir el cuerpo con el token nuevo al reintentar | propio (bug de nuestra Fase 1) | — |

**Etiquetas + fuente de texto** (Fase A del motor inteligente — 2026-10-29).
Comparados: teng-lin (`_web/params/labels.py`, `_web/rows/labels.py`, `_web/labels.py`,
`_web/sources/add.py`, `_web/params/sources.py`, `_web/rows/sources.py`), jacob-bd
(`core/labels.py`, `core/sources.py:add_text_source`). roomi/ishandutta no tienen etiquetas.

| Detalle | Elegido | De | Descartado |
|---|---|---|---|
| Leer etiquetas | `LIST_LABELS` (`I3xc3c`), **solo lectura** | teng-lin | jacob-bd `list_labels` → autoetiqueta si no hay (leer modifica) |
| Envoltorio de opciones | `[2, None, None, [1, …, [1]]]` | teng-lin | jacob-bd `[2]` |
| Autoetiquetar | `[False]` = solo fuentes sin etiqueta (incremental, por defecto) | teng-lin | jacob-bd `[]`/`[0]` |
| Rehacer todas | `[True]`, tool aparte **destructiva** (`label_reorganize`, pide `confirm`) | teng-lin (la CLI lo protege con `--yes`) | — |
| Forma de la etiqueta | `[nombre, [[id]…] \| None, id, emoji]`; vacía = legítimo; rara = drift | ambos coinciden; teng-lin estricto | jacob-bd: ignora filas raras en silencio |
| Asignar fuente | `UPDATE_LABEL` `[opts, nb, label, [[None, [[src]]]]]`, un id por llamada; idempotente (si ya está, no llama) | teng-lin + propio | — |
| Fuente de texto: campos | 11 `[None, [título, texto], None, 2, None×6, 1]` | ambos coinciden | — |
| Fuente de texto: opciones | Anidado `[2, None, None, [1,…]]` | teng-lin #1546 (live: la forma plana se rechaza con 3/5/9) | jacob-bd: plano `[2], [1,…]` |
| Respuesta de ADD_SOURCE | 3 formas (profunda/media/plana) | teng-lin `from_unknown_shape` | jacob-bd: solo una |
| Escritura dudosa (status 3/9, corte de conexión, formato raro) | Releer el cuaderno y buscar **una** fuente con ese título → `reconciled=true` | jacob-bd `_reconcile_source` | — |
| Dudosa y no encontrada | `UnconfirmedWriteError`: la cascada **no** la reenvía por otro transporte | teng-lin `call_unconfirmed_on_transport_loss` | — |

**Personalización del chat + renombrar fuente** (Fase A — 2026-10-29).
Comparados: teng-lin (`_web/chat.py:_send_configure/_read_settings`, `_web/rows/chat.py:unwrap_chat_settings`,
`_chat.py:configure`, `_web/params/sources.py:build_rename_source_params`, `_web/sources/__init__.py:rename`),
jacob-bd (`core/notebooks.py:configure_chat`, `core/sources.py:rename_source`).

| Detalle | Elegido | De | Descartado |
|---|---|---|---|
| Escribir ajustes | `RENAME_NOTEBOOK` (`s0tc2d`) con `[[objetivo, prompt?], [longitud]]` en `params[1][0][7]` | ambos coinciden | — |
| Leer ajustes | `GET_NOTEBOOK` fila `[7]`; `[[], []]` y `null` = por defecto; forma rara = drift | teng-lin (#1751, live) | jacob-bd: no tiene lectura |
| Cambiar solo una parte | Leer → mezclar → escribir (la escritura reemplaza todo) | teng-lin `_app.chat.execute_configure` | jacob-bd: escribe directo y resetea lo no indicado |
| Solo `custom_prompt` | Implica objetivo `custom`, conserva la longitud | propio | — |
| Verificación | Releer tras escribir; si no coincide → `UnconfirmedWriteError`; devolver `previous` para deshacer | propio | — |
| Códigos | objetivo 1/2/3, longitud 1/4/5, prompt ≤ 10 000 | teng-lin = jacob-bd | — |
| Renombrar fuente | `UPDATE_SOURCE` (`b7Wfje`) `[None, [id], [[[título]]]]` | ambos coinciden | — |
| Fuente inexistente al renombrar | Comprobar antes y releer después (el servidor no da error) | teng-lin (miss-detection por relectura) | jacob-bd: confía en el eco |

**Pendiente (no implementado aún):** `authuser` para multi-cuenta (teng-lin), sugerencias de
siguiente pregunta (`inner[5]`), número de turno vía `khqZz`, forzar conversación nueva
(teng-lin: borrar la conversación; nunca inventar id), anclas de cita dentro del texto.

## 5. Decisiones que esto fija para notebooklm-hub

1. **Base de diseño = patrón de teng-lin** (`client → _app → fachadas`), reimplementado limpio.
2. **Transporte en cascada** = gRPC Android (preferido, headless) → batchexecute → browser (fallback).
3. **REST** = fachada propia inspirada en los 33 endpoints de roomi, para n8n.
4. **Tools** = un archivo por tool, auto-descubiertas; destructivas con `confirm`+preview.
5. **Generadores Studio** = superset (incluye flashcards/quiz/mind-map de ishandutta).
6. **Auth** = multi-cuenta + master-token (auto-curativo, para servidores/NAS).
