# WinOLS — automatización vía plugin "External Control" (LUA) — destilado verificado

Destilado de la **documentación oficial de EVC** (`winols HelpEn.pdf`, "External Control for WinOLS",
43 págs), extraído y verificado el 2026-10-05. Sirve para diseñar un MCP de WinOLS **sin releer el
PDF** y sin inventar funciones.

> **NO es parte de notebooklm-hub.** Es conocimiento para un proyecto aparte (MCP de WinOLS). Su
> hogar natural es `Varios_tools/construir-mcp`. Se guarda aquí para no perder lo verificado.
> Regla: enlazar/destilar, no copiar el PDF.

---

## 1. Qué es (y por qué es el camino correcto)

WinOLS (editor binario de ECU, de EVC) **sí tiene automatización oficial**: el plugin **"External
Control"**, que integra el lenguaje **LUA** para controlar funciones de WinOLS por script. Cita
textual: *"allows you to control several of these functions via scripts... automate repetitive data
processing steps"*.

→ Es el **Camino 1 (scripting/API oficial)** del toolbox §8ter — robusto, NO hay que simular clics.
No confundir con los `*.winolsskript` internos: External Control "is a lot more powerful".

## 2. Requisitos (de la doc)

- WinOLS **registrado** (al menos v1.219).
- El plugin **"External Control" registrado** → es un **producto de pago aparte**, no viene con
  WinOLS. (El código de producto se gestiona con EVC.)
- Corre en **Windows** (GUI de escritorio). NO corre en el NAS Linux headless.

## 3. Cómo se arranca un script LUA (3 formas oficiales)

1. **Ruta del `.lua` como parámetro al arrancar WinOLS** (línea de comandos). Requiere que WinOLS
   no esté ya corriendo; si lo está, el script se ejecuta en la instancia activa.
2. Drag & drop del `.lua` sobre la ventana de WinOLS.
3. Drag & drop sobre una ventana de proyecto (fija ese proyecto como contexto por defecto).

## 4. ⭐ Modo servidor con "ticket files" (clave para un MCP)

De la doc: en modo servidor *"the script is running permanently since program start and reacts via
'ticket' files to requests from outside, perhaps from a webserver."*

→ **WinOLS se queda escuchando y reacciona a archivos "ticket" dejados desde fuera.** Este es el
mecanismo ideal para un MCP: el MCP deja un ticket (petición) y lee la respuesta, sin abrir/cerrar
WinOLS en cada llamada. Samples oficiales: https://www.evc.de/en/product/ols/lua.asp

## 5. Inventario de funciones LUA (del índice oficial — forma de referencia)

**Globales:** `NewProject`, `GetVersion`, `FindProjects` / `FindProjects2`, `DuplicateProject`,
`GetProjectVersions`, `OpenProjectVersion`, `DeleteProjectVersion`, `OpenAndExport`,
`ReactivateChecksums`, `SaveAll`, `CloseAll`, `Quit`, `Sleep`, `SetClient`/`GetClient`,
`ReadDirectory`, `CreateDirectory`, `GetLastError`, utilidades `fromhex/tohex`, `fromJSON/toJSON`,
`binaryor/xor/and`, HTTP (`HttpStart`, `HttpAddHeader`, `HttpAddParam`, `HttpAddFile`,
`HttpExecute`, `HttpResponseString/File/Error`), `Log`, `MessageBox`, `TextEntryDialog`.

**Contexto Project:** `projectGetProperty` / `projectSetProperty`, `projectClose`, `projectSave`,
`projectExport`, `projectExportMaps`, `projectImport`, `projectMail`, `projectSearchChecksums`,
`projectApplyChecksums`, `projectAddChecksum`, `projectStatChecksums`, `projectGetChecksumName`.

**Otros contextos (ver PDF para firmas exactas):** Map, Selection, Folder, Checksum, Version,
Window (`windowGetActive/SetActive`, `windowGetMapProperties`, `windowSetMapProperties`). Además un
capítulo **MAPCALC** (cálculo sobre mapas).

> ⚠️ Las **firmas exactas** (parámetros/retornos) de cada función están en el PDF por sección
> (p. ej. 2.2.x globales, 2.4.x project). Al implementar una tool, leer la firma real de esa función
> en el PDF — no asumirla.

## 6. Seguridad (de la propia doc)

- LUA incluye funciones de ficheros, **incluido borrar**. *"Do not run LUA scripts from untrusted
  sources."* En modo servidor, solo personas autorizadas deben poder introducir/modificar scripts.
- Para "solutions" el acceso a la librería `io` está deshabilitado.

## 7. Diseño propuesto del MCP (cuando se construya)

```
LLM → MCP (FastMCP, en Windows) → genera script LUA → WinOLS "External Control"
                                   ├─ modo servidor (preferido): dejar "ticket file" → leer respuesta
                                   └─ modo CLI: lanzar winols.exe con la ruta del .lua
```

Tools candidatas (cada una genera el LUA correspondiente, verificar firma en el PDF):
- `winols_find_projects`      → `FindProjects` / `FindProjects2`      (lectura → allow)
- `winols_open_version`       → `OpenProjectVersion`                  (lectura → allow)
- `winols_export`             → `projectExport` / `OpenAndExport`     (lectura → allow)
- `winols_export_maps`        → `projectExportMaps`                   (lectura → allow)
- `winols_search_checksums`   → `projectSearchChecksums`              (lectura → allow)
- `winols_apply_checksums`    → `projectApplyChecksums`               (**modifica → ask**)
- `winols_set_property`       → `projectSetProperty`                  (**modifica → ask**)
- `winols_duplicate_project`  → `DuplicateProject`                    (ask)
- `winols_delete_version`     → `DeleteProjectVersion`                (**destructivo → ask**)

> Cualquier operación que **escriba a la ECU** o borre datos → `ask` con confirmación, sin excepción
> (un error puede inutilizar una centralita). Patrón del MCP: FastMCP + permissions, como en
> `docs/mcp-toolbox.md` §8ter.

## 8. Qué falta para construirlo (realista)

1. Una **máquina Windows** con WinOLS registrado + el plugin **External Control** (de pago).
2. Leer en el PDF las **firmas exactas** de las funciones que se vayan a usar.
3. Decidir transporte LUA↔MCP: **modo servidor (ticket files)** recomendado vs CLI.
4. Construir con el patrón FastMCP del toolbox; destructivas en `ask`.

**Fuente:** EVC, `winols HelpEn.pdf` (plugin External Control / LUA). Samples:
https://www.evc.de/en/product/ols/lua.asp

---

## 9. Proyectos existentes (evaluados, verificados contra código 2026-10-05)

No hace falta construir desde cero: ya hay un MCP de WinOLS que implementa EXACTAMENTE este diseño,
y alternativas open source para no pagar el plugin.

### 🥇 PRINCIPAL — `NXT-Tronic/winols-mcp` (MIT, Python, ~3⭐)
Un MCP que controla WinOLS vía el plugin External Control. **Implementa el patrón ticket-file de la
sección 1.8 del manual** — valida que nuestro diseño era correcto. Punto de partida real.

Arquitectura verificada (leída del código, no del README):
```
MCP client (Claude) ─MCP/stdio→ server/winols_mcp_server.py (proceso Python, FUERA de WinOLS)
                                   │ escribe  WINOLS_BRIDGE_DIR/tickets/req-<uuid>.ticket.json
                                   │ (JSON {id, func, args})
                                   ▼ (polling con asyncio.sleep hasta timeout)
   lua/winols_mcp_bridge.lua (corre DENTRO de WinOLS, es lo único que llama a la API)
                                   │ lee el ticket con Sleep(ms,"*.ticket.json"), despacha,
                                   │ escribe RESPONSES_DIR/resp-<uuid>.json {id, ok, result|error}
                                   ▼
                                WinOLS (estado del proyecto, hexdump, checksums, export…)
```

Detalles clave reutilizables (patrones para TU MCP):
- **Hallazgo que confirma la doc:** WinOLS **no tiene socket/COM/RPC**; WinOLS es el *host* de LUA,
  no al revés → un script corre *dentro* ("como un grabador de macros"). El ticket-file es la ÚNICA
  vía oficial, no un workaround. Esto cierra la duda de si había un camino "más limpio": **no lo hay.**
- **3 capas de seguridad** (ninguna sustituye a otra): (1) *refusal gate* en Python — toda tool de
  riesgo exige `confirm: true` ANTES de escribir el ticket; (2) *allowlist LUA* — el puente solo
  llama a las ~78 funciones vetadas en `REQUIRED_LUA_FUNCTIONS` (un ticket malicioso no puede
  invocar un global arbitrario, ni `requirex`, ni `MessageBox`/`TextEntryDialog` que colgarían el
  loop); (3) la red de seguridad propia de WinOLS (árbol de versiones, original intacto).
- **`tool_specs.py` = fuente única de verdad:** cada tool es un `ToolSpec(name, lua_func, category,
  mutating, risk {low|medium|high}, requires_confirm, see_also[...])`. `risk=high` → refused local
  sin `confirm`. El campo `see_also` ayuda al LLM a descubrir la secuencia correcta sin leer las 81.
- **`SERVER_INSTRUCTIONS`** = primer catálogo-wide (modelo de seguridad, checklist pre-export)
  servido una vez en el `initialize` del MCP, no repetido en cada tool.
- **Resolución de constantes:** el ticket manda `{"__const":"eByte"}` y el LUA lo resuelve a `_G`;
  `{"__constor":[...]}` combina flags con `binaryor`. Útil para pasar enums de WinOLS por JSON.
- **Honestidad (como la nuestra):** *"built from EVC's official manual, NOT yet run against a live
  WinOLS instance — reference implementation, not validated."* → **le falta la prueba en WinOLS
  real**, igual que a nuestro diseño. `SETUP.md` trae un rollout por fases (read-only primero, en
  proyecto desechable).

→ **Plan recomendado:** forkear/evaluar winols-mcp, probarlo en una Windows real con WinOLS +
plugin (fase read-only primero), y adaptarlo a tu patrón (permissions.yaml V3, wrapper --env-file,
mcp_tools/*.json). NO reconstruir desde cero.

### 🆓 ALTERNATIVAS SIN PAGAR el plugin External Control

- **`LeZed97/ZedSuite`** (GPL-3.0, ~151⭐, activo; motor de detección en **Rust**, multiplataforma
  Win/mac/Linux). Editor de mapas ECU **open source**, 100% local. Detección automática de VAG Bosch
  **EDC15/EDC16**; cualquier binario abre trayéndole las definiciones. **Lee proyectos WinOLS `.ols`,
  TunerPro `.xdf` y JSON mappacks**; edita en tabla/2D/3D/hexdump, versiones, compare, fix checksum,
  **exporta binario o mappack de WinOLS**. → la alternativa libre más seria; un MCP sobre ZedSuite
  evitaría el coste de EVC (habría que ver su superficie de automatización).
- **`2CRPerformance/LinOLS`** (GPL-3.0, ~38⭐) — chiptuning open source "similar a WinOLS", pero
  **sin commits desde 2024** (menos vivo que ZedSuite).
- **`TheFlashBold/py-ols`** (GPL-3.0, Python) — 🔑 **librería que lee archivos `.ols` y `.kp` SIN
  WinOLS**: extrae parámetros, offsets CAL, factores, ejes y binarios embebidos (soporta v100–v804+
  WinOLS 5). `read_ols("file.ols")` → `ols.parameters`, `reader.extract_binary(v)`. Pieza
  reutilizable para inspeccionar/convertir proyectos WinOLS en Python puro (p. ej. tools de solo
  lectura de un MCP, o un pipeline sin GUI).
- **`dongliqianxian/shengjia`** (~2⭐, Python) — **47 "skills" de calibración ECU/TCU para agentes
  IA** (estándar Agent Skills, carpetas `<skill>/SKILL.md` + `references/`): A2L/DAMOS/WinOLS parse,
  bin-to-a2l, blind-map-finder, checksum-crc-engine, bosch-conti/denso-bin-engine, closed-loop,
  stage1, dtc-locator, EDC17/MD1/MG1/DCM, TCU… → **NO es un MCP: es conocimiento de dominio** que
  complementa cualquier MCP (le enseña al LLM *cómo* calibrar, no *cómo* manejar WinOLS). Encaja con
  el patrón de skills del usuario.

### Herramientas de apoyo
- **`reproteq/DiffPatchTool`** (C#/.NET, activo) — comparar/parchear binarios con hex editor
  integrado + cloud. **`reproteq/DiffPatchWpf`** (ARCHIVADO) — versión simple anterior.
- **`mrc-tuner-rom.github.io`** — web/manual de un workstation ECU; **código fuente privado** → solo
  referencia, no reutilizable.

### Dos estrategias resultantes
1. **Con WinOLS de pago** → base = `NXT-Tronic/winols-mcp` (ticket files + 81 tools + seguridad);
   falta probar en Windows real.
2. **Sin pagar** → `ZedSuite` (editor libre que lee `.ols`) + `py-ols` (parsear `.ols` en Python) +
   `shengjia` (skills de dominio para el LLM). Habría que construir el MCP sobre ZedSuite/py-ols.

> PENDIENTE (requiere sesión con `Varios_tools`): fichar estos 8 en `tool_catalog` + `repo-index`
> (mcp-catalog), destacando winols-mcp como base y la vía libre ZedSuite+py-ols. Verificado contra
> el código real el 2026-10-05.
