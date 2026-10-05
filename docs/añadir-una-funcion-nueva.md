# Cómo añadir una función nueva de NotebookLM a notebooklm-hub

**Escenario:** Google saca una función nueva en NotebookLM (p. ej. "generar glosario") y **ningún
proyecto externo la ha añadido todavía** — o el proyecto de referencia (teng-lin, etc.) ya está
abandonado. Esta guía es el procedimiento para añadirla **tú mismo**, sin depender de nadie.

Es la habilidad central del repo: como NotebookLM no tiene API oficial, cada función se "captura"
del tráfico de la propia web y se copia en una tool. Proceso verificado contra la fuente real
(teng-lin `docs/rpc-development.md`, MIT), 2026-10-04.

> **Idea clave:** la función nueva **ya viaja por la red** en cuanto la usas en el navegador —
> aunque nadie la haya documentado. Tu trabajo es capturar esa llamada y replicarla. No esperas a
> teng-lin ni a Google: podrías tenerla **antes** que ellos.

---

## Antes de empezar: ¿y WebMCP no me ahorra esto?

**No para NotebookLM.** WebMCP (`navigator.modelContext`, estándar de Chrome/W3C) permite que **el
dueño de un sitio** exponga las funciones de *su* web a agentes IA, para que el agente **no tenga
que hacer reverse-engineering**. Pero solo funciona **si el sitio lo implementa**. NotebookLM es de
Google y **no lo implementa** (ni lo hará para que lo automaten terceros). Por tanto, para
NotebookLM **sigues necesitando capturar `batchexecute`** como se explica aquí. WebMCP solo serviría
si algún día Google lo adoptara — no es el caso. (Si construyeras *tu propia* web, ahí WebMCP sí
tendría sentido; no es nuestro escenario.)

---

## El flujo completo (4 pasos)

```
1. CAPTURAR la llamada real (DevTools o automático)
2. DECODIFICAR el f.req (saber rpcid + forma de los parámetros)
3. REGISTRAR el rpcid nuevo  → core/transport/batchexecute.py  (1 línea)
4. CREAR la tool             → tools/<nombre>.py                (1 archivo)
```

Los pasos 3-4 son pequeños **gracias a la arquitectura** (núcleo + tool en 1 archivo). El trabajo
real está en 1-2 (capturar), y hay dos modos.

---

## Paso 1 — Capturar la llamada

### Modo A — Manual con Chrome DevTools (siempre funciona, cero dependencias)

1. Abre Chrome → `https://notebooklm.google.com/` (logueado con tu **cuenta dedicada**).
2. Abre DevTools (`F12`) → pestaña **Network**.
3. Marca **Preserve log** y **Disable cache**.
4. Filtra por: `batchexecute` (o `GenerateFreeFormStreamed` si es algo de chat/respuesta).
5. **Haz UNA sola acción** en la web: pulsa el botón de la función nueva. (Una acción a la vez para
   aislar su llamada.)
6. Haz clic en la petición que apareció y mira:
   - **Headers → URL, parámetro `rpcids`** = el **ID de la función** (6 caracteres, p. ej. `wXbhsf`).
   - **Payload → `f.req`** = el cuerpo (URL-encoded).
   - **Response** = la respuesta (empieza con `)]}'`).

### Modo B — Asistido / automático (captura mientras navegas)

Para no leer a mano, hay herramientas que **capturan el tráfico por ti** mientras usas la web y lo
exportan (URL, método, body, respuesta). Útil si vas a capturar varias funciones:

- **Playwright** (lo que usa teng-lin para captura sistemática): un script abre el navegador,
  escucha las `request`/`response` que matchean `batchexecute` y las vuelca a JSON. Es "modo B
  casero" y entra como test de captura en el repo.
- **Extensiones / agentes de reverse-engineering de API** (tipo "reverse-api-engineer",
  "api-reverse-engineer", MCP de Chrome DevTools): instalas, pulsas *Start*, navegas normal, y al
  terminar te dan un JSON con todos los endpoints capturados. Un agente IA puede manejar un **MCP de
  Chrome DevTools** para hacer esta captura dentro de un flujo automatizado.

> ⚠️ Verifica cualquier herramienta externa contra su fuente antes de usarla (checklist de
> `docs/mcp-toolbox.md`). El modo A manual es el que **siempre** funciona y no añade dependencias.

---

## Paso 2 — Decodificar el `f.req`

El `f.req` es JSON URL-encoded con la forma `[[[rpc_id, "<params-json>", null, "generic"]]]`.
Para ver los parámetros reales:

**En la consola del navegador:**
```javascript
const encoded = "...";                 // pega aquí el valor de f.req
const outer = JSON.parse(decodeURIComponent(encoded));
console.log("RPC ID:", outer[0][0][0]);
console.log("Params:", JSON.parse(outer[0][0][1]));
```

**En Python:**
```python
import json
from urllib.parse import unquote

def decode_f_req(encoded: str) -> dict:
    outer = json.loads(unquote(encoded))
    inner = outer[0][0]
    return {"rpc_id": inner[0],
            "params": json.loads(inner[1]) if inner[1] else None}
```

Apunta: el **rpc_id** y la **forma de params** (qué valores van y en qué orden).

---

## Paso 3 — Registrar el rpcid nuevo (1 línea)

En `src/notebooklm_hub/core/transport/batchexecute.py`, añade el id al diccionario `_RPC_IDS`:

```python
_RPC_IDS = {
    "LIST_NOTEBOOKS": "wXbhsf",
    # ...
    "GENERATE_GLOSSARY": "AbCdEf",   # ← el rpcid que capturaste
}
```

> **Modo rápido sin editar código** (para probar o parchear un id que Google rotó):
> ```bash
> export NOTEBOOKLM_HUB_RPC_OVERRIDES='{"GENERATE_GLOSSARY":"AbCdEf"}'
> ```
> Para una función permanente, mejor añádelo al diccionario.

Si la operación necesita construir un `f.req` con forma propia, añade su builder junto al transporte
(sección de params), replicando la forma que viste en el Paso 2.

---

## Paso 4 — Crear la tool (1 archivo)

Copia `src/notebooklm_hub/tools/_template.py` a `tools/notebook_glossary.py`:

```python
from typing import Any
from .registry import ToolSpec

NAME = "notebook_glossary"
DESCRIPTION = "Genera un glosario de los documentos de un notebook."
PARAMS = {"notebook": {"type": "string", "required": True, "desc": "Nombre o ID del notebook."}}

async def run(client: Any, **params: Any) -> dict:
    res = await client.call("generate_glossary", notebook_id=params["notebook"])
    return res.data

TOOL = ToolSpec(name=NAME, description=DESCRIPTION, params=PARAMS, run=run, destructive=False)
```

- Si la función **borra o modifica** algo → pon `destructive=True` (el núcleo exigirá `confirm`).
- No tocas las fachadas ni el registry: la tool **aparece sola** en MCP y REST.

---

## Paso 5 — Probar y cerrar

1. Prueba por REST: `curl -s localhost:9420/tools/notebook_glossary -d '{"notebook":"<ID>"}'`.
2. Si responde bien → añade un test de parseo en `tests/` (como los de `notebook_ask`).
3. Si falla con "drift" (no hay envelope para el id) → el rpcid cambió: recaptura (Paso 1).
4. Si falla con refusal (status gRPC, p. ej. PERMISSION_DENIED) → no es un bug tuyo: es un
   veredicto de NotebookLM (cuenta sin permiso, cuota, etc.).

---

## Resumen: por qué no dependes de nadie

- La función nueva está en **tu navegador** desde el día 1 → la capturas tú.
- Añadirla son **2 toques** (1 línea + 1 archivo) gracias a la arquitectura.
- El **método está escrito aquí** → aunque teng-lin/roomi/PleasePrompto desaparezcan, tú sabes
  hacerlo. Ese era el objetivo de todo el repo.
- **WebMCP no aplica** a NotebookLM (requiere que Google lo implemente). Para sitios de terceros sin
  API, el camino es siempre: capturar → decodificar → replicar.
