# Roadmap de notebooklm-hub

Construcción por fases. Cada fase deja algo verificable; no se escribe el motor entero de golpe.

## ✅ Fase 0 — Fundación (conocimiento + esqueleto)  ← AQUÍ
- [x] Matriz de capacidades destilada de los 7 proyectos (`docs/provenance/capabilities-matrix.md`)
- [x] Conocimiento de transporte preservado (`docs/transport/`)
- [x] Arquitectura y reglas de frontera (`docs/ARCHITECTURE.md`)
- [x] Esqueleto de paquete + contrato `Transport` + `registry` de tools + guía de contribución
- [x] `pyproject.toml` (uv/CPython), licencia MIT, estructura de fachadas

**Valor:** aunque los repos originales desaparezcan mañana, el *qué* y el *cómo* están aquí.

## ✅ Fase 1 — Vertical funcional mínima (validar el patrón)  ← HECHA (código), pendiente run real
Objetivo: una operación de punta a punta por MCP y REST.
- [x] `core/transport/batchexecute.py` real (protocolo portado de roomi/jacob-bd, MIT) + op *ask*
- [x] `core/auth/` login por cookies (env var o archivo JSON) — apto para servidor/NAS
- [x] `_app/ask.py` (Request/Result + build/execute, patrón ADR-0021)
- [x] `tools/notebook_ask.py` (auto-descubierta por el registry)
- [x] fachada MCP + fachada REST exponiendo `notebook_ask` (ambas levantan y publican la tool)
- [x] suite 14/14: parsers del protocolo (drift/refusal/respuesta), verbo ask, errores
- [ ] **PENDIENTE: run real contra una cuenta de NotebookLM** (hacer en el NAS; no verificable
      desde el sandbox de desarrollo sin salida a Google)

## Fase 2 — Cascada de transporte completa
- [ ] `android_grpc.py` (nivel 1) + `browser.py` (nivel 3) tras el contrato `Transport`
- [ ] `cascade.py` con fallback y preferencia configurable
- [ ] matriz de "qué toco si Google rompe X" validada

## Fase 3 — Superficie de tools completa
- [ ] notebooks (create/list/delete+confirm/rename/get)
- [ ] sources (add url/text/file/drive, list, read paginado, delete+confirm, wait)
- [ ] studio (generate async → status → download; audio/vídeo/report/infografía/slides +
      flashcards/quiz/mind-map de ishandutta)
- [ ] research (start/status/import), chat (start/status/ask/cancel), notes, share
- [ ] errores estructurados + `confirm`/preview en todas las destructivas

## Fase 4 — Distribución y DX
- [ ] CLI `nlmhub` (Typer)
- [ ] publicar en PyPI (`uv`)
- [ ] instalador que cablea clientes MCP (patrón jacob-bd) + empaquetado skill .zip
- [ ] REST con los endpoints estilo roomi para n8n + ejemplos de workflow
- [ ] multi-cuenta/rotación + batch 1000+ + vault cache

## Fase 5 — Integración ecosistema del autor
- [ ] ficha en `Varios_tools/tool_catalog` + fila en `repo-index`
- [ ] guía de montaje en Kiro CLI del NAS (patrón nextdns/n8n: mcp_tools + permissions.yaml V3)
- [ ] opcional: tools nativas para el nas-agent (Strands)

---

## 📌 Pendientes de mantenimiento (requieren sesión con `Varios_tools` cargado)

Estos dos quedaron abiertos al construir el repo. No se pueden cerrar desde una sesión que solo
tenga `notebooklm-hub` cargado (el `select repository` de Kiro Web solo carga lo elegido).

1. **Mover el toolbox a su hogar canónico.** `docs/mcp-toolbox.md` debería vivir en
   `Varios_tools/construir-mcp/` (junto a `PROYECTO-guia-construir-mcp.md`). Al mover: dejar en
   `notebooklm-hub` solo un enlace (regla: enlazar, no duplicar).
2. **Cerrar el círculo en el índice maestro.** Añadir `notebooklm-hub` a `ydiaz1699/repo-index`
   (fila en INDEX + destilado en `repos/notebooklm-hub.md` + mención en `mcp-catalog`), para que un
   chat en frío sepa que existe y no proponga crear otro MCP de NotebookLM. Opcional: ficha en
   `Varios_tools/tool_catalog` reusando `docs/provenance/capabilities-matrix.md` (ya destilado).

3. **Catalogar y (opcional) montar `microsoft/playwright-mcp`.** Es el agente de navegador
   recomendado para la **captura asistida** de funciones nuevas (ver `docs/añadir-una-funcion-nueva.md`
   Modo B) y la referencia del transporte nivel 3. Pendiente:
   - **Catalogar:** ficha en `Varios_tools/tool_catalog/entries/playwright-mcp.md` + fila en
     `repo-index/mcp-catalog` (Apache-2.0, ~37.8k⭐, tools `browser_navigate/click/type/fill_form`
     para actuar y `browser_network_requests`/`browser_network_request` para capturar red).
   - **Montar en Kiro CLI** (patrón del ecosistema): `mcp_tools/playwright.json` + `mcp-build` +
     `permissions.yaml` V3 → tools de lectura (`browser_network_requests`, `browser_snapshot`) en
     `allow`; tools que actúan (`browser_click`, `browser_navigate`, `browser_type`) en `ask`.
   - Nota: para capturar funciones nuevas NO hace falta embeberlo; se usa como MCP aparte desde el
     LLM. Embeber Playwright como librería es solo para el transporte nivel 3 de notebooklm-hub.

---

## 💡 Idea anotada — MCP para automatizar programas de escritorio (p. ej. WinOLS)

**NO es parte de notebooklm-hub** (es otro programa, otro entorno Windows). Se anota aquí para no
perder el hilo; su hogar natural es `Varios_tools/construir-mcp` + el patrón de `docs/mcp-toolbox.md`
§8ter. Pendiente para un **chat/proyecto dedicado** cuando el usuario tenga máquina Windows + la doc.

Caso: WinOLS (editor binario de ECU, de EVC). El patrón genérico ya quedó en `mcp-toolbox.md` §8ter.

- **(B) Camino preferido — scripting oficial LUA. ✅ DOC VERIFICADA.** WinOLS tiene el plugin
  **"External Control"** (LUA). La doc oficial de EVC ya está **leída y destilada** en
  [`docs/winols-lua-notes.md`](winols-lua-notes.md): cómo arranca (CLI / drag&drop / **modo servidor
  con "ticket files"** — ideal para un MCP), el inventario real de funciones (`OpenProjectVersion`,
  `projectExport`, `projectApplyChecksums`, `projectExportMaps`, etc.) y el diseño de tools con
  destructivas en `ask`. El diseño del MCP está listo; **no hace falta reconseguir doc**.
- **(C) Camino de respaldo — automatización de UI** (solo si no se tiene el plugin External Control,
  que es de pago): evaluar **FlaUI-MCP** (UI Automation) como base. Alternativas: uia-x,
  pywinauto-mcp, AutoIt-mcp; visión+OCR como último recurso.
- **Avisos:** corre en Windows (no en el NAS); tools que **escriben a la ECU → `ask`** obligatorio
  (un error puede inutilizar la centralita); implicaciones legales de emisiones según país.
- **Qué falta para construirlo (realista):** (1) máquina Windows con WinOLS registrado + plugin
  External Control (de pago); (2) leer en el PDF las firmas exactas de las funciones a usar;
  (3) decidir transporte LUA↔MCP (modo servidor/ticket recomendado); (4) construir con FastMCP +
  permissions del toolbox. Hogar: `Varios_tools/construir-mcp`.
