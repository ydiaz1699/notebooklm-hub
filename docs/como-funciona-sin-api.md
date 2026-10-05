# Cómo trabaja un MCP de NotebookLM "sin API oficial"

Google **no publica una API oficial** de NotebookLM. Aun así, varios MCP/clientes acceden a él.
Este documento explica el mecanismo real (no hay magia: por debajo siempre hay HTTP), para entender
qué hace `notebooklm-hub` y por qué está diseñado como está.

---

## "Sin API" no significa "sin HTTP"

Cuando usas NotebookLM en el navegador y preguntas algo, tu Chrome **sí** manda peticiones HTTP a
servidores de Google. "No hay API" quiere decir que Google no publica un endpoint **documentado y
soportado** para terceros — pero los endpoints **internos** que usa su propia web existen y
funcionan. Un MCP sin API **se hace pasar por tu navegador** y llama esos mismos endpoints.

## Los 3 orígenes de las tools de un MCP

| Origen | Cuándo se usa | Cómo funciona | Ejemplo |
|---|---|---|---|
| **1. API oficial** | el servicio la publica | el MCP envuelve llamadas documentadas | rclone (RC API), n8n (REST) |
| **2. Reverse-engineering** | **no hay API** | llama los endpoints **internos** de la web/app (los que ves en la pestaña *Network*) | **NotebookLM** (`batchexecute`) |
| **3. Automatización de navegador** | ni API ni endpoints estables | **conduce un Chrome** y simula clics / lee el DOM | fallback de último recurso |

NotebookLM está en el **caso 2** (rápido) con el **caso 3** como red de seguridad.

## El mecanismo exacto del caso 2 (lo que implementa `core/transport/batchexecute.py`)

1. **Toma prestada tu sesión (cookies).** No hay API key porque no hay API: la "llave" es la
   **cookie** de tu cuenta ya logueada. Por eso siempre hay un login inicial. → `core/auth/`.
2. **Arranca los tokens (bootstrap).** Descarga una vez la home autenticada y extrae del HTML los
   tokens que Google exige en cada llamada:
   - `SNlM0e` → token **CSRF** (anti-falsificación)
   - `FdrFJe` → id de **sesión**
   - `cfb2h` → **versión de build** de la web
   → método `_bootstrap()`.
3. **Imita la llamada.** `POST` a `/_/LabsTailwindUi/data/batchexecute` con el cuerpo `f.req` en el
   formato de Google (arrays anidados) y un `rpcid` que identifica la operación (p. ej. `wXbhsf` =
   listar notebooks). Para *preguntar* se usa el endpoint de streaming `GenerateFreeFormStreamed`.
4. **Descifra la respuesta.** Google antepone `)]}'` (prefijo anti-robo de datos) y devuelve
   "envelopes" `["wrb.fr", <rpcid>, "<json interno>", …]`. El parser quita el prefijo, localiza el
   envelope de tu `rpcid` y decodifica el JSON interno. → `parse_batchexecute()` /
   `parse_query_response()`.

```
tu navegador  ─(cookies + SNlM0e/FdrFJe/cfb2h)→  POST .../batchexecute?rpcids=wXbhsf
                                                   f.req=[[[id, "<params>", null, "generic"]]]
NotebookLM    ─(responde)→  )]}'\n[["wrb.fr","wXbhsf","<json>",…]]
el MCP        ─(parsea)→  resultado
```

El MCP hace **exactamente lo mismo**, sin abrir navegador.

## Por qué es frágil (y cómo lo mitiga este repo)

- Los endpoints/`rpcids` **no están documentados** → Google los puede **rotar sin aviso**. Cuando
  pasa, la llamada no trae envelope para ese id (lo detectamos como *drift*).
- **Mitigación:** parche en caliente con `NOTEBOOKLM_HUB_RPC_OVERRIDES='{"LIST_NOTEBOOKS":"<nuevo-id>"}'`
  y, si el formato cambia de verdad, se arregla en **un solo archivo** (`batchexecute.py`). Ver la
  tabla de mantenimiento en [`transport/README.md`](transport/README.md).
- **Red de seguridad:** la cascada cae al transporte navegador (caso 3) cuando los endpoints se
  mueven, porque un navegador sigue la UI real.

## Riesgo de Términos de Servicio

Usar tu sesión de forma automatizada **puede considerarse acceso automatizado** bajo los Términos de
Google, con riesgo para la cuenta. Usa una **cuenta dedicada** y respeta los límites de uso.

---

## Apéndice — cómo se *distribuye/obtiene* un MCP (código vs. imagen)

Duda frecuente: a veces instalas un MCP **clonando el repo**, y a veces te dicen "ya hay una imagen,
no clones nada". Son cosas distintas:

| Forma | Qué descargas | Cómo se usa | Dónde vive |
|---|---|---|---|
| **Clonar repo + build** | código fuente | tú haces `docker build` o `uv pip install` | `github.com/<u>/<repo>` |
| **Imagen en GHCR** | imagen **ya construida** | `docker pull ghcr.io/<u>/<img>:<tag>` | **GitHub** Container Registry (sección *Packages* del repo) |
| **Imagen en Docker Hub** | imagen **ya construida** | `docker pull <u>/<img>:<tag>` | hub.docker.com |
| **Instalar desde git** | el paquete, sin clonar a mano | `uv pip install "pkg @ git+https://github.com/<u>/<repo>"` | se resuelve desde GitHub |

**GHCR (`ghcr.io`) = el registro de imágenes de GitHub** — por eso una imagen puede estar "en
GitHub" y **no** en Docker Hub, y por eso no hace falta clonar el repo: bajas la imagen ya hecha.
La imagen aparece en la columna derecha del repo, en **"Packages"**.

Casos reales del ecosistema del autor (referencia):
- **OpenWA** → imagen ya construida en **GHCR**: `ghcr.io/rmyndharis/openwa:<tag>` (no se clonó el repo).
- **rclone** → imagen oficial en **Docker Hub**: `rclone/rclone:<tag>`.
- **NextDNS** → **sin** usar su imagen: se instaló desde `git+https://github.com/dmeiser/nextdns-mcp`
  dentro de la imagen local `kiro-cli-nas:local` (construida en el NAS, nunca subida a un registro).

> Para `notebooklm-hub`: hoy se instala desde el repo con `uv`. Si en el futuro se publica como
> imagen, iría a **GHCR** (`ghcr.io/ydiaz1699/notebooklm-hub`) para quedar junto al código.
