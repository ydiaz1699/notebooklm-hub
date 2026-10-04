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

## 5. Decisiones que esto fija para notebooklm-hub

1. **Base de diseño = patrón de teng-lin** (`client → _app → fachadas`), reimplementado limpio.
2. **Transporte en cascada** = gRPC Android (preferido, headless) → batchexecute → browser (fallback).
3. **REST** = fachada propia inspirada en los 33 endpoints de roomi, para n8n.
4. **Tools** = un archivo por tool, auto-descubiertas; destructivas con `confirm`+preview.
5. **Generadores Studio** = superset (incluye flashcards/quiz/mind-map de ishandutta).
6. **Auth** = multi-cuenta + master-token (auto-curativo, para servidores/NAS).
