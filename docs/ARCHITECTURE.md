# Arquitectura de notebooklm-hub

Objetivo rector: **mantenibilidad**. Añadir una capacidad = un archivo. Arreglar el transporte
cuando Google cambie algo = un archivo. Nunca buscar lógica dispersa.

## Capas

```
facades/  ─ adaptadores finos, uno por canal
  ├─ mcp_server.py   (FastMCP)   → Kiro / Claude / Cursor / Codex …
  ├─ rest_api.py     (FastAPI)   → n8n / Zapier / Make / curl / cron
  └─ (cli: nlmhub)   (Typer)     → terminal
        │  las fachadas NO contienen lógica de negocio: parsean su entrada,
        │  llaman al núcleo neutral y renderizan su propia salida
        ▼
_app/     ─ lógica de negocio NEUTRAL (no importa fastmcp/fastapi/typer)
  por verbo: Request/Plan/Result (dataclasses) + build_<verb>_plan() + execute_<verb>()
  errores clasificados en un único sitio: _app/errors.py
        ▼
core/
  ├─ client.py       ─ API pública única (lo que de verdad "hace cosas")
  ├─ transport/      ─ los 3 transportes en cascada (ver docs/transport/)
  │    ├─ base.py        contrato Transport (interfaz común)
  │    ├─ android_grpc.py
  │    ├─ batchexecute.py
  │    ├─ browser.py
  │    └─ cascade.py      ÚNICO sitio del orden/fallback
  └─ auth/           ─ master-token, cookies, multi-cuenta
        ▲
tools/    ─ una capacidad = un archivo (notebook_ask.py, source_add.py, studio_generate.py…)
  └─ registry.py     ─ auto-descubre los archivos y los publica a las 3 fachadas
```

**Patrón adoptado de teng-lin (ADR-0021), reimplementado limpio:** `client → _app → fachadas`.
Es la mejor decisión de diseño del ecosistema NotebookLM para servir MCP+REST+CLI sin duplicar.

## Reglas de frontera (lo que mantiene el orden)

1. `_app/` **no** importa `fastmcp`, `fastapi`, `typer`, ni los archivos de fachada, ni `transport`
   directamente (habla con `core/client`). Esto permite tests sin levantar servidores.
2. Las fachadas **no** tienen lógica de negocio: solo traducen entrada/salida.
3. Las **tools** describen *qué* se hace; el *cómo* (transporte) lo resuelve `core`.
4. Las **destructivas** (`*_delete`, `share_remove`) exigen `confirm` y devuelven un *preview*
   antes de ejecutar (patrón de teng-lin). Esto mapea directo a permisos `ask` del cliente MCP.
5. Los **errores** se clasifican en `_app/errors.py` con categorías neutrales
   (`CONFIG/DEPENDENCY/NOTEBOOK_LIMIT/ARTIFACT_TIMEOUT/SOURCE_*`…); cada fachada las proyecta a su
   vocabulario (MCP code / HTTP status / exit code).

## Operaciones largas (no bloquear)

Generación de Studio, research y chat lento siguen el patrón **async de 3 pasos**:
`*_generate|start` → `*_status` (poll) → `*_download|import`. Nunca se bloquea la fachada.

## Por qué CPython + uv (y no PyPy)

- **`uv`** (gestor de paquetes/entornos): sí. Rápido, `uv.lock` reproducible, `uv tool install`
  para distribuir. Es el estándar del ecosistema del autor.
- **PyPy** (intérprete JIT alternativo): **no**. El proyecto es **I/O-bound** (espera HTTP de
  Google), no CPU-bound → PyPy no aporta velocidad. Y rompe compatibilidad con extensiones C
  (gRPC, Playwright, cripto) que son justo las que usan los transportes. Usar PyPy añadiría
  mantenimiento, en contra del objetivo. → **CPython + uv.**

## Multi-cuenta y auth

- Perfiles por cuenta (aislados). **master-token** acuña credenciales frescas sin navegador →
  auto-curativo para servidores/NAS/cron. Cookies de navegador importables como alternativa.
- Rotación multi-cuenta para lotes grandes (patrón de roomi).
