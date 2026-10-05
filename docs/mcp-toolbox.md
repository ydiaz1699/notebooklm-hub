# MCP Toolbox — técnicas, librerías y herramientas para construir/mejorar un MCP

**Qué es:** una caja de herramientas reutilizable. Antes de construir o mejorar un MCP propio, mira
esta lista y toma lo que apliquen — así no empiezas de cero ni reinventas patrones ya resueltos.

**Destilado de lo aprendido construyendo `notebooklm-hub`** y montando MCPs en el entorno del autor
(rclone, nextdns, n8n, OpenWA). Verificado contra la fuente real, no de memoria.

> 🏠 **Hogar canónico pendiente:** este documento debería vivir en `Varios_tools/construir-mcp/`
> (junto a `PROYECTO-guia-construir-mcp.md`), que es el sitio del ecosistema para "cómo construir un
> MCP". Se creó aquí para no perder lo aprendido en el chat; **mover a `construir-mcp` cuando se
> abra una sesión con `Varios_tools`** y dejar en `notebooklm-hub` solo un enlace (regla:
> enlazar, no duplicar).

---

## 1. Anatomía de un MCP

- **Patrón de 2 capas** (clave para portabilidad y mantenibilidad):
  - **lógica pura `_impl`** → hace la acción (llamada HTTP/negocio) **sin** saber de MCP.
  - **envoltorio** → la expone como tool MCP (`@tool` / `mcp.tool()`).
  - Beneficio: la MISMA lógica sirve como MCP para un LLM **y** como import directo para scripts,
    REST, otro agente. (`notebooklm-hub` lo lleva más lejos: `_app/` neutral + fachadas finas.)
- **Qué expone un MCP:** `tools` (acciones), `resources` (datos leíbles), `prompts` (plantillas).
- **Transporte del protocolo MCP:** `stdio` (subproceso, lo normal para Kiro/Claude CLI) o
  `HTTP`/streamable (servidor remoto). No confundir con el transporte *hacia el servicio* (sección 2).

## 2. Cómo hablar con el servicio (los 3 orígenes de las tools)

| Origen | Cuándo | Cómo |
|---|---|---|
| **1. API oficial** | el servicio la publica | envolver llamadas documentadas (ideal: estable) |
| **2. Reverse-engineering** | **no hay API** | llamar los endpoints **internos** de la web/app (pestaña Network) |
| **3. Automatización de navegador** | ni API ni endpoints estables | conducir Chrome (Playwright/Patchright), leer DOM — frágil, último recurso |

### Técnicas de transporte aprendidas (caso NotebookLM)
- **Web RPC / `batchexecute`** — imitar las llamadas internas de la web (rápido, inmune a cambios
  de UI; pero los `rpcid` no están documentados y Google los rota).
- **Android gRPC + bearer** — usar el protocolo de la **app móvil** (HTTP/2, protobuf). Headless
  real, sin cookies de navegador. Lo más robusto para desatendido; lo más caro de reconstruir
  (requiere esquema protobuf recuperado del binario).
- **Browser fallback** — Chrome real como red de seguridad cuando 1 y 2 se rompen.
- **Dual / cascada transport** — tener varios y caer en cascada: `gRPC → batchexecute → browser`.
  La robustez NO viene de más tools, viene de **un transporte en cascada con fallback**.
  Regla: fallo *de transporte* → cae al siguiente; fallo *de dominio* → se propaga (no cae).

## 3. Autenticación

- **API key / token** → el caso fácil (va en env, nunca en el JSON del MCP).
- **Cookies de sesión** → cuando no hay API: tomar prestada la sesión del navegador logueado.
- **master-token** → acuña credenciales/cookies frescas **bajo demanda, sin navegador** →
  **auto-curativo** (self-healing). El patrón de oro para servidores/NAS/CI/cron.
- **auto-reauth** → renovar la sesión al expirar sin intervención (TOTP, master-token).
- **OAuth** → para conectores remotos (claude.ai/ChatGPT).
- **Regla:** secretos **fuera** del `mcp.json` (usar `${VAR}` + `--env-file` en el wrapper).
- **Bootstrap de tokens** (web RPC): extraer del HTML autenticado los tokens que el servicio exige
  por llamada (ej. NotebookLM: `SNlM0e` CSRF, `FdrFJe` sesión, `cfb2h` build).

## 4. Multi-cuenta y escala

- **Rotación multi-cuenta** → repartir carga entre varias cuentas (evita agotar cuotas por cuenta).
- **Perfiles aislados** → una carpeta/credencial por cuenta; no mezclar sesiones.
- **Batch** → patrón para lotes grandes (ej. 1000+ preguntas) con reauth y rotación automáticas.
- **Quotas** → tratar `RESOURCE_EXHAUSTED` como verdad (no reintentar en bucle).

## 5. Resiliencia y buen comportamiento de tools

- **RPC drift vs refusal** (reverse-eng): *drift* = el id rotó (no hay envelope) → parchear id;
  *refusal* = el servidor respondió y rechazó (status gRPC) → es un veredicto, no reintentar.
  **No confundirlos** (manda al usuario a cazar un id que no era el problema).
- **Override en caliente** de ids rotados por env var (sin release): `..._RPC_OVERRIDES={"X":"id"}`.
- **Errores estructurados** `CODE: mensaje (retriable=…)` con categorías neutrales
  (`CONFIG/NOT_FOUND/PERMISSION/QUOTA/TRANSPORT/…`); cada fachada los proyecta a su vocabulario.
- **Destructivas con `confirm` + preview** → la tool devuelve un preview y exige `confirm=true`.
  Mapea directo a permisos `ask` del cliente MCP.
- **Long-running no bloqueante** → `start/generate → status (poll) → download/import`.
- **Name-or-ID** → aceptar nombre humano o ID; devolver siempre el ID canónico; nombre ambiguo →
  rechazar, no adivinar.

## 6. Librerías y herramientas

| Necesidad | Herramienta | Nota |
|---|---|---|
| Framework MCP (Python) | **FastMCP** | el más usado; genera schema desde type hints (NO acepta `**kwargs`) |
| SDK MCP oficial | `modelcontextprotocol/python-sdk` | base del estándar |
| HTTP cliente | **httpx** | async, lo que usa el núcleo |
| Navegador (fallback) | **Playwright / Patchright** | Patchright = stealth/anti-detección |
| Agente de navegador por MCP | **microsoft/playwright-mcp** (Apache-2.0) | controlar Chrome desde un LLM; capturar red (`browser_network_requests`) |
| gRPC Android | **grpcio + protobuf** | requiere el `.proto` recuperado |
| REST (para n8n) | **FastAPI + uvicorn** | fachada HTTP sobre el mismo núcleo |
| CLI | **Typer** | subcomandos legibles |
| Gestor de entorno | **`uv`** ✅ | `uv venv`, `uv pip install`, `uv tool install`, `uv.lock` |
| Intérprete | **CPython** ✅ / **PyPy** ❌ | el trabajo es I/O-bound; PyPy no acelera y rompe extensiones C (gRPC/Playwright) |

## 7. Distribución (cómo obtener/publicar el MCP)

| Forma | Comando | Dónde vive |
|---|---|---|
| Clonar + build | `git clone` + `docker build` / `uv pip install -e .` | repo GitHub |
| **Imagen en GHCR** | `docker pull ghcr.io/<u>/<img>:<tag>` | **GitHub Container Registry** (sección *Packages* del repo) |
| Imagen en Docker Hub | `docker pull <u>/<img>:<tag>` | hub.docker.com |
| Instalar desde git | `uv pip install "pkg @ git+https://github.com/<u>/<repo>"` | se resuelve de GitHub |
| PyPI | `uv tool install <pkg>` | pypi.org |

- **GHCR (`ghcr.io`) = registro de imágenes de GitHub** → una imagen puede estar "en GitHub" y NO
  en Docker Hub, y no hace falta clonar el repo. (Ej.: OpenWA = `ghcr.io/rmyndharis/openwa`.)
- **Verificar que el paquete existe** antes de usarlo: `curl https://pypi.org/pypi/<pkg>/json`
  (404 = no está). Leer `pyproject.toml`/`package.json`: sin `[project.scripts]` es **módulo**
  (`python -m x`), no comando — `uv tool install` falla con "No executables are provided".

## 8. Integración a Kiro CLI (entorno del autor)

- `mcp_tools/<mcp>.json` por MCP + script `mcp-build` (jq) que ensambla `settings/mcp.json`.
- **Obligatorio** en MCPs stdio en Node: `MCP_MODE=stdio` + `DISABLE_CONSOLE_OUTPUT=true` (los logs
  contaminan el canal JSON-RPC y rompen el MCP).
- **Kiro CLI V3** usa `settings/permissions.yaml` (reglas `capability:mcp` allow/ask/deny), **NO**
  el `autoApprove` del `mcp.json` (eso es V2 y se ignora). Lectura → `allow`; destructivas → `ask`.
- Secretos en `.env` (chmod 600) + wrapper `kiro` que inyecta `--env-file`; `mcp.json` usa `${VAR}`.
- **Gotcha de red:** `network_mode: host` NO resuelve nombres de servicio Docker → usar IP privada
  del host, no el nombre del contenedor.
- **Guard anti-SSRF:** varios MCPs bloquean IPs privadas por defecto → activar modo permissive para
  LAN (verificar el NOMBRE REAL de la variable en el código, no inventarla).

## 8bis. Capturar endpoints internos (cuando no hay API) + WebMCP

- **Captura manual (siempre funciona):** Chrome `F12` → Network → *Preserve log* → filtrar por el
  endpoint → hacer UNA acción → leer URL (`rpcids`/ruta), Payload (`f.req`/body) y Response.
- **Captura asistida/automática:** un **agente de navegador** manejado por un LLM. Recomendado:
  **`microsoft/playwright-mcp`** (Apache-2.0) con `browser_navigate`/`browser_click`/`browser_type`
  para actuar y `browser_network_requests` + `browser_network_request` para listar/leer las
  peticiones de red (rpcid + body + respuesta). Alternativas: reverse-api-engineer, MCP de Chrome
  DevTools, o Playwright embebido como librería.

- **Distinción que NO hay que confundir (dos conceptos opuestos con nombre parecido):**
  - **WebMCP** (`webmachinelearning/webmcp`, `navigator.modelContext`, Chrome/W3C) = **el dueño del
    SITIO** declara tools en su propia página para que un agente las invoque **sin reverse-eng**.
    Solo funciona **si el sitio lo implementa**. Útil si construyes TU web; **NO** sirve para
    automatizar sitios de terceros que no lo adoptaron (NotebookLM no lo hace).
  - **Agente de navegador** (playwright-mcp, Chrome DevTools MCP, Playwright/Patchright) = **controla
    el Chrome real aunque el sitio NO colabore** (clic, teclear, leer DOM/red). Es la técnica que
    WebMCP busca sustituir, y la ÚNICA que funciona contra sitios cerrados. En notebooklm-hub cumple
    DOS papeles: (1) **capturar** funciones nuevas (asistido), (2) **ejecutar** como transporte
    nivel 3 (fallback) cuando `batchexecute` se rompe.
  - Regla mnemotécnica: **WebMCP = el sitio colabora. Agente de navegador = el sitio no colabora.**
  Guía aplicada: `docs/añadir-una-funcion-nueva.md`.

## 9. Checklist "verificar antes de entregar"

- [ ] ¿El paquete/imagen existe donde asumo? (PyPI 404 / `gh api` / GHCR) — verificar, no de memoria.
- [ ] ¿Es comando o módulo? (leer `pyproject.toml`/`package.json` completo).
- [ ] ¿Algún volumen/mount tapa la ruta de instalación? (binario en `$HOME` + volumen = oculto).
- [ ] ¿Permisos/UID? (uid no-root vs carpeta root = Permission denied).
- [ ] ¿Las variables de seguridad (SSRF/CORS/CSP) aplican a MI escenario real? (no solo leer la doc).
- [ ] Verificar nombres de variables/tools/endpoints contra el **código real** del MCP.

---

## Ejemplo que aplica muchas de estas técnicas

**`notebooklm-hub`** (este repo): transporte en cascada (gRPC/web/browser), auth cookies +
master-token (previsto), núcleo único + fachadas MCP/REST, errores estructurados, destructivas con
confirm, `uv`/CPython, override de rpcids en caliente. Ver `docs/ARCHITECTURE.md` y
`docs/transport/`.
