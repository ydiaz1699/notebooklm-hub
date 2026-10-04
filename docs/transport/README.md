# Transporte — cómo se habla con NotebookLM (sin API oficial)

Google **no publica API oficial** de NotebookLM. Todo acceso programático usa uno de tres
transportes. `notebooklm-hub` implementa **los tres en cascada** con fallback automático, aislados
en `src/notebooklm_hub/core/transport/`. **Este es el único sitio que hay que tocar cuando Google
cambia algo** — ese es el objetivo de mantenibilidad del proyecto.

Conocimiento destilado (no copiado) de los proyectos de referencia, verificado el 2026-10-04.
Preservado aquí porque es lo más caro de reconstruir si esos repos desaparecen.

---

## Los tres transportes

### 1) Android gRPC + master-token  — *preferido para headless / servidores*
- **Host:** `notebooklm-pa.googleapis.com:443`
- **Servicio:** `google.internal.labs.tailwind.orchestration.v1.LabsTailwindOrchestrationService`
- **Path:** `/<service>/<Method>` · **Transporte:** HTTP/2 `POST`, `content-type: application/grpc`
- **Framing:** un mensaje protobuf con prefijo de longitud por body (envelope gRPC de 5 bytes)
- **Auth:** header OAuth bearer (**master-token** → acuña cookies/tokens frescos bajo demanda,
  sin navegador → **auto-curativo**, ideal para cron/CI/NAS)
- **Éxito:** HTTP 200 + trailer `grpc-status: 0`
- **Superficie:** ~49 métodos en 4 servicios gRPC (muchos no cableados a la UI móvil). La mayoría
  unarios; `GenerateFreeFormStreamed` y `StreamLiveSession` son server-streaming.
- **Ventaja:** headless real, sin cookies de navegador, el más robusto para desatendido.
- **Coste:** requiere el esquema protobuf (nombres de campo recuperados por decompilación del
  binario Flutter). Ver [`android-grpc.md`](android-grpc.md).
- **Fuente destilada:** teng-lin `docs/android/` (endpoints, schema.proto, evidencias), ishandutta.

### 2) batchexecute (Web RPC)  — *rápido, el caballo de batalla*
- Llama los **mismos endpoints internos** que la web de NotebookLM (los `batchexecute` que se ven
  en la pestaña Network). 10–100× más rápido que raspar el DOM.
- **No documentados** → Google puede cambiar los `rpcids` sin aviso → punto principal de rotura.
- Se identifican por `rpcids`; el body va URL-encoded con arrays anidados.
- **Ventaja:** rápido, no abre navegador. **Coste:** frágil ante cambios de Google.
- **Fuente destilada:** roomi `src/rpc/*` (batchexecute, notebooks/sources/studio/sharing-rpc,
  `rpc-ids.ts`), teng-lin backend web.

### 3) Browser (Playwright/Patchright stealth)  — *fallback de último recurso*
- Conduce un **Chrome real**; inicia sesión una vez (cookies en perfil persistente) y simula al
  humano: escribe en el chat, lee el DOM, extrae citas del panel lateral.
- **Ventaja:** sobrevive a cambios de API/UI, "parece humano". **Coste:** lento, pesado, necesita
  display (`xvfb` en servidores sin pantalla).
- Usar **Chrome estable** (no Chromium) mejora el fingerprint/anti-detección.
- **Fuente destilada:** PleasePrompto (Patchright), roomi `src/session/browser-session.ts` (fallback).

---

## La cascada (corazón de la mantenibilidad)

```
pedir(operación, args)
  ├─ ¿backend forzado por config/env?  → úsalo y no caigas
  ├─ 1. android_grpc   → si OK, devuelve
  │        ↳ falla por auth/red/método no disponible
  ├─ 2. batchexecute   → si OK, devuelve
  │        ↳ falla (p.ej. Google movió el rpcid)   ← rotura típica
  └─ 3. browser        → fallback; más lento pero resiliente
```

Reglas:
- **Preferencia configurable** (`NOTEBOOKLM_HUB_BACKEND=android|web|browser|cascade`, default `cascade`).
- Un fallo **de transporte** (endpoint caído) cae al siguiente nivel; un fallo **de dominio**
  (notebook no existe, cuota agotada) **no** cae — se propaga como error estructurado.
- Cada transporte implementa el **mismo contrato** `Transport` (ver `core/transport/base.py`) para
  que `_app/` y las tools no sepan cuál se usó.
- **Un solo sitio de verdad** para el orden/fallback: `core/transport/cascade.py`.

## Mantenimiento: "Google rompió algo", ¿dónde toco?

| Síntoma | Causa probable | Archivo a tocar |
|---|---|---|
| Las respuestas web fallan de golpe | cambió un `rpcid` de batchexecute | `core/transport/batchexecute.py` (+ tabla de rpcids) |
| El login desatendido deja de renovar | cambió el flujo master-token | `core/auth/` |
| gRPC devuelve `grpc-status` != 0 nuevo | cambió el esquema/método Android | `core/transport/android_grpc.py` (+ `docs/transport/android-grpc.md`) |
| El fallback de navegador no encuentra un botón | cambió el DOM/UI | `core/transport/browser.py` (selectores) |
| Hay que cambiar el orden de preferencia | decisión operativa | `core/transport/cascade.py` |

> Nunca hay que buscar la lógica repartida: cada rotura tiene **un** archivo dueño.
