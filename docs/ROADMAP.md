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
