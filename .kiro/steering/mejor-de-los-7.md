---
inclusion: always
---

# Regla del proyecto: notebooklm-hub debe ser el mejor de los 7 repos

`notebooklm-hub` es **nuestro propio MCP** de NotebookLM. Reúne las mejores ideas de 7 proyectos
no oficiales para superarlos a todos, no para copiar a uno.

## `_drafts/notebooklm/` NO es la base

- Es una copia de `jacob-bd/gemini-notebook-mcp-cli` instalada **solo para probar la conexión**
  con NotebookLM al principio.
- No se toma como referencia por defecto solo porque esté a mano en el repo.
- No se edita ni se usa como dependencia. El código propio vive en `src/notebooklm_hub/`.

## Los 7 repos de referencia

| Repo | Para qué es la mejor referencia |
|---|---|
| `teng-lin/notebooklm-py` | **Base de diseño**: arquitectura, errores, notebooks/fuentes, gRPC Android, master-token |
| `roomi-fields/notebooklm-mcp` | REST para n8n, citas (~97 %), batch, vault, fallback navegador |
| `jacob-bd/gemini-notebook-mcp-cli` | Experiencia CLI, instalador de clientes MCP, skill .zip |
| `ishandutta2007/notebooklm-api` | Generadores Studio extra (flashcards, quiz, mind-map…) |
| `PleasePrompto/notebooklm-mcp`, `PleasePrompto/notebooklm-skill`, `Zidong-LLC/notebooklm-skill` | Solo histórico: navegador stealth y empaquetado de skill (archivados/estancados) |

Detalle completo: `docs/provenance/capabilities-matrix.md`.

## Procedimiento obligatorio antes de implementar una capacidad

1. **Leer todos los repos que la implementan**, en su versión actual: clonar con
   `git clone --depth 1` fuera del repo (p. ej. `/tmp/refs/`). No basarse en uno solo ni de memoria.
2. **Comparar detalle a detalle** en una tabla (estructura del protocolo, casos borde, errores,
   formas raras de respuesta) y elegir la mejor variante de cada detalle, aunque vengan de repos distintos.
3. **Si se contradicen**, gana la fuente con evidencia ("live-observed", test de regresión, issue
   enlazado), y se anota la discrepancia.
4. **Registrar la decisión** en `docs/provenance/capabilities-matrix.md` §4bis
   (detalle → elegido → de qué repo → descartado).
5. **Destilar, no copiar**: reimplementar limpio en nuestra arquitectura
   (`tools/` → `_app/` → `core/client` → `core/transport/`), con tests de los casos borde elegidos.

## Recordatorios

- Nada se ha probado contra Google real desde Kiro Web (sin salida a Google ni cookies). La
  verificación real la hace el usuario en el NAS: decirlo siempre al entregar.
- Los tests propios están en `tests/` (pytest limitado ahí; `_drafts/` tiene los suyos).
