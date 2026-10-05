# notebooklm-hub

**Un acceso programático propio y duradero a Google NotebookLM, para cualquier LLM y para n8n.**

> NotebookLM **no tiene API oficial**. Este repo reúne —en una arquitectura limpia y propia— las
> capacidades de los mejores proyectos no oficiales existentes, para no depender de que ninguno de
> ellos siga vivo. El código es nuestro; los proyectos externos se usan como **referencia destilada**
> (ver [`docs/provenance/`](docs/provenance/)), nunca como código clonado.

---

## Qué es y para qué sirve

- **Para un LLM/agente** (Kiro, Claude, Cursor, Codex…): un **servidor MCP** con tools para
  consultar notebooks, gestionar fuentes, generar artefactos Studio y hacer deep research.
- **Para automatización sin agente** (n8n, Zapier, Make, cron, `curl`): una **REST API HTTP**
  con los mismos verbos.
- **Para scripts/terminal**: una **CLI** (`nlmhub`).

Las tres son **fachadas finas** sobre un único núcleo. Añadir o arreglar una capacidad se hace
en **un solo sitio** y aparece automáticamente en MCP, REST y CLI.

> ¿Cómo accede a NotebookLM si Google no da API? → [`docs/como-funciona-sin-api.md`](docs/como-funciona-sin-api.md)
> (resumen: imita las llamadas internas de la web con tus cookies; incluye apéndice sobre GHCR vs
> Docker Hub vs instalar desde git).

## Por qué existe (los 3 objetivos de diseño)

1. **Universal** — sirve a cualquier LLM **y** a n8n (MCP + REST, mismo núcleo).
2. **Mantenible** — para añadir una tool se crea **un archivo** en `tools/`; para arreglar el
   transporte cuando Google cambie algo, se toca **un archivo** en `core/transport/`. Nunca hay
   que buscar una línea perdida entre varios estilos de código.
3. **Duradero** — asumimos que los repos de referencia **desaparecerán**. Por eso el conocimiento
   crítico (endpoints, protocolo, estrategia de transporte) está **destilado en `docs/`** y el
   código es propio. Si mañana se borran todos los originales, este repo sigue siendo útil y
   reconstruible.

## Arquitectura (de un vistazo)

```
         ┌──────────── fachadas finas (adapters) ────────────┐
         │   facades/mcp_server   facades/rest_api   cli/     │
         └───────────────────────┬───────────────────────────┘
                                 │  (no duplican lógica)
                      ┌──────────▼───────────┐
                      │  _app/  lógica neutral │  ← validación, planes, orquestación
                      └──────────┬───────────┘
                      ┌──────────▼───────────┐
                      │  core/client.py       │  ← API pública, una sola vez
                      └──────────┬───────────┘
         ┌───────────────────────▼───────────────────────────┐
         │          core/transport/  (CASCADA, 1 solo sitio)   │
         │   1) android_grpc   2) batchexecute   3) browser     │
         │   cascade.py = "prueba 1 → si falla 2 → si falla 3"  │
         └─────────────────────────────────────────────────────┘
```

- **tools/** — una capacidad = un archivo. `registry.py` los auto-descubre y los expone a las 3 fachadas.
- **core/transport/** — los 3 transportes en cascada con fallback automático. El 90 % del
  mantenimiento real (Google mueve un endpoint) se arregla aquí, en un único lugar.
- **core/auth/** — multi-cuenta, master-token (headless auto-curativo), cookies.
- **_app/** — lógica de negocio neutral (no sabe de MCP/REST/CLI). Patrón adoptado de la mejor
  decisión de diseño que encontramos en el ecosistema (ver `docs/provenance/`).

Detalle completo: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Estado

🚧 **Fase 1 — vertical funcional mínima (`ask`).** Ya existe el código real de: transporte web
(`batchexecute`), auth por cookies, núcleo, la tool `notebook_ask` y las fachadas MCP + REST.
La lógica, el parseo del protocolo y el cableado de las fachadas están **probados** (suite 14/14 +
ambas fachadas levantan y exponen la tool).

> ⚠️ **Pendiente de verificación en entorno real.** El transporte habla con endpoints internos de
> Google que **no se han podido probar contra una cuenta real** desde el entorno de desarrollo
> (sin salida a Google ni credenciales). El protocolo está portado fielmente de implementaciones de
> referencia (MIT), pero el **primer run contra NotebookLM debe hacerse con una cuenta dedicada en
> tu máquina/NAS**. Ver "Primer uso real" abajo.

Siguientes fases (resto de tools, transportes Android gRPC + navegador, CLI, PyPI): ver
[`docs/ROADMAP.md`](docs/ROADMAP.md).

## Primer uso real (en tu máquina/NAS, con cuenta dedicada)

```bash
uv venv && uv pip install -e ".[mcp,rest]"

# Credenciales: cookies de una cuenta DEDICADA ya logueada en NotebookLM.
#  opción 1: exportar directamente el header Cookie
export NOTEBOOKLM_HUB_COOKIES="SID=...; HSID=...; SSID=...; ..."
#  opción 2: archivo JSON [{"name":...,"value":...}] exportado del navegador
export NOTEBOOKLM_HUB_COOKIE_FILE=~/nlm-cookies.json

# Probar por REST (para n8n/curl):
nlmhub-rest &            # levanta en 127.0.0.1:9420
curl -s localhost:9420/tools/notebook_ask \
  -H 'content-type: application/json' \
  -d '{"notebook":"<ID o nombre>","question":"¿qué dicen mis fuentes sobre X?"}'

# O por MCP (para Kiro/Claude/Cursor): registrar el comando `nlmhub-mcp` como servidor MCP stdio.
```
Si el transporte web falla por un cambio de Google (RPC drift), ver la tabla de mantenimiento en
[`docs/transport/README.md`](docs/transport/README.md) y el override `NOTEBOOKLM_HUB_RPC_OVERRIDES`.

## Instalación (prevista)

Gestión de entorno con [`uv`](https://docs.astral.sh/uv/) (CPython; **no** PyPy — ver
`docs/ARCHITECTURE.md` § "Por qué CPython + uv").

```bash
uv venv && uv pip install -e .
```

## Añadir una capacidad nueva

Ver [`CONTRIBUTING.md`](CONTRIBUTING.md): crear un archivo en `src/notebooklm_hub/tools/`,
nada más. Aparece solo en MCP, REST y CLI.

## Procedencia y licencias

Este proyecto es MIT. Las capacidades están **inspiradas** en proyectos de terceros, todos MIT,
destilados —no copiados— en [`docs/provenance/`](docs/provenance/). Agradecimiento a sus autores.

## Aviso

Automatizar una sesión de NotebookLM puede considerarse acceso automatizado bajo los Términos de
Google, con riesgo para la cuenta. Usa una **cuenta dedicada** y respeta los límites de uso. Este
proyecto no está afiliado a Google.
