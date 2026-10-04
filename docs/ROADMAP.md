# Roadmap de notebooklm-hub

Construcción por fases. Cada fase deja algo verificable; no se escribe el motor entero de golpe.

## ✅ Fase 0 — Fundación (conocimiento + esqueleto)  ← AQUÍ
- [x] Matriz de capacidades destilada de los 7 proyectos (`docs/provenance/capabilities-matrix.md`)
- [x] Conocimiento de transporte preservado (`docs/transport/`)
- [x] Arquitectura y reglas de frontera (`docs/ARCHITECTURE.md`)
- [x] Esqueleto de paquete + contrato `Transport` + `registry` de tools + guía de contribución
- [x] `pyproject.toml` (uv/CPython), licencia MIT, estructura de fachadas

**Valor:** aunque los repos originales desaparezcan mañana, el *qué* y el *cómo* están aquí.

## Fase 1 — Vertical funcional mínima (validar el patrón)
Objetivo: una operación de punta a punta por los tres canales.
- [ ] `core/transport/batchexecute.py` real (empezar por el más rápido) + 1 operación: *preguntar*
- [ ] `core/auth/` con un método de login (cookies o master-token)
- [ ] `_app/ask.py` (Request/Plan/Result + build/execute)
- [ ] `tools/notebook_ask.py` (auto-descubierta)
- [ ] fachada MCP + fachada REST exponiendo `ask`
- [ ] test e2e: misma pregunta vía MCP y vía `curl` → misma respuesta

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
