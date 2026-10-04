# Cómo contribuir a notebooklm-hub

El proyecto está diseñado para que **cada cambio tenga un único sitio evidente**. Si te encuentras
tocando varios archivos para una cosa, probablemente va en contra del diseño — revísalo.

## Añadir una capacidad (tool) nueva — **1 archivo**

1. Crea `src/notebooklm_hub/tools/<mi_tool>.py` copiando `tools/_template.py`.
2. Rellena: `NAME`, `DESCRIPTION`, el esquema de parámetros y la función `run(client, **params)`.
3. Si es **destructiva**, marca `DESTRUCTIVE = True` → el núcleo le exige `confirm` y devuelve
   preview automáticamente.
4. Listo. `registry.py` la auto-descubre y aparece sola en **MCP**, **REST** y **CLI**.

No tienes que tocar las fachadas, ni el router, ni registrar nada a mano.

## Arreglar el transporte (Google cambió algo) — **1 archivo**

Consulta la tabla de `docs/transport/README.md` § "Mantenimiento". Cada síntoma tiene un archivo
dueño:
- rpcid web caído → `core/transport/batchexecute.py`
- método/esquema gRPC → `core/transport/android_grpc.py` (+ `docs/transport/android-grpc.md`)
- selector del navegador → `core/transport/browser.py`
- orden/fallback → `core/transport/cascade.py`
- login desatendido → `core/auth/`

## Reglas que NO se rompen

- `_app/` y `tools/` **nunca** importan `fastmcp`, `fastapi`, `typer` ni los archivos de fachada.
- Las fachadas **no** llevan lógica de negocio.
- No se copia código de proyectos externos. Se destila el conocimiento en `docs/` y se cita la
  procedencia en `docs/provenance/`.
- Verifica contra la fuente real (API/código), no de memoria.

## Entorno

```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest
```
CPython (no PyPy — ver `docs/ARCHITECTURE.md`).
