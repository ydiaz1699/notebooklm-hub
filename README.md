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

🚧 **Fase 0 — fundación.** Ahora mismo el repo contiene el conocimiento destilado, la matriz de
capacidades y el esqueleto de arquitectura. El motor se construye por fases (ver
[`docs/ROADMAP.md`](docs/ROADMAP.md)). No es funcional todavía.

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
