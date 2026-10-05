# WinOLS — automatización vía plugin "External Control" (LUA) — destilado verificado

Destilado de la **documentación oficial de EVC** (`winols HelpEn.pdf`, "External Control for WinOLS",
43 págs), extraído y verificado el 2026-10-05. Sirve para diseñar un MCP de WinOLS **sin releer el
PDF** y sin inventar funciones.

> **NO es parte de notebooklm-hub.** Es conocimiento para un proyecto aparte (MCP de WinOLS). Su
> hogar natural es `Varios_tools/construir-mcp`. Se guarda aquí para no perder lo verificado.
> Regla: enlazar/destilar, no copiar el PDF.

---

## 1. Qué es (y por qué es el camino correcto)

WinOLS (editor binario de ECU, de EVC) **sí tiene automatización oficial**: el plugin **"External
Control"**, que integra el lenguaje **LUA** para controlar funciones de WinOLS por script. Cita
textual: *"allows you to control several of these functions via scripts... automate repetitive data
processing steps"*.

→ Es el **Camino 1 (scripting/API oficial)** del toolbox §8ter — robusto, NO hay que simular clics.
No confundir con los `*.winolsskript` internos: External Control "is a lot more powerful".

## 2. Requisitos (de la doc)

- WinOLS **registrado** (al menos v1.219).
- El plugin **"External Control" registrado** → es un **producto de pago aparte**, no viene con
  WinOLS. (El código de producto se gestiona con EVC.)
- Corre en **Windows** (GUI de escritorio). NO corre en el NAS Linux headless.

## 3. Cómo se arranca un script LUA (3 formas oficiales)

1. **Ruta del `.lua` como parámetro al arrancar WinOLS** (línea de comandos). Requiere que WinOLS
   no esté ya corriendo; si lo está, el script se ejecuta en la instancia activa.
2. Drag & drop del `.lua` sobre la ventana de WinOLS.
3. Drag & drop sobre una ventana de proyecto (fija ese proyecto como contexto por defecto).

## 4. ⭐ Modo servidor con "ticket files" (clave para un MCP)

De la doc: en modo servidor *"the script is running permanently since program start and reacts via
'ticket' files to requests from outside, perhaps from a webserver."*

→ **WinOLS se queda escuchando y reacciona a archivos "ticket" dejados desde fuera.** Este es el
mecanismo ideal para un MCP: el MCP deja un ticket (petición) y lee la respuesta, sin abrir/cerrar
WinOLS en cada llamada. Samples oficiales: https://www.evc.de/en/product/ols/lua.asp

## 5. Inventario de funciones LUA (del índice oficial — forma de referencia)

**Globales:** `NewProject`, `GetVersion`, `FindProjects` / `FindProjects2`, `DuplicateProject`,
`GetProjectVersions`, `OpenProjectVersion`, `DeleteProjectVersion`, `OpenAndExport`,
`ReactivateChecksums`, `SaveAll`, `CloseAll`, `Quit`, `Sleep`, `SetClient`/`GetClient`,
`ReadDirectory`, `CreateDirectory`, `GetLastError`, utilidades `fromhex/tohex`, `fromJSON/toJSON`,
`binaryor/xor/and`, HTTP (`HttpStart`, `HttpAddHeader`, `HttpAddParam`, `HttpAddFile`,
`HttpExecute`, `HttpResponseString/File/Error`), `Log`, `MessageBox`, `TextEntryDialog`.

**Contexto Project:** `projectGetProperty` / `projectSetProperty`, `projectClose`, `projectSave`,
`projectExport`, `projectExportMaps`, `projectImport`, `projectMail`, `projectSearchChecksums`,
`projectApplyChecksums`, `projectAddChecksum`, `projectStatChecksums`, `projectGetChecksumName`.

**Otros contextos (ver PDF para firmas exactas):** Map, Selection, Folder, Checksum, Version,
Window (`windowGetActive/SetActive`, `windowGetMapProperties`, `windowSetMapProperties`). Además un
capítulo **MAPCALC** (cálculo sobre mapas).

> ⚠️ Las **firmas exactas** (parámetros/retornos) de cada función están en el PDF por sección
> (p. ej. 2.2.x globales, 2.4.x project). Al implementar una tool, leer la firma real de esa función
> en el PDF — no asumirla.

## 6. Seguridad (de la propia doc)

- LUA incluye funciones de ficheros, **incluido borrar**. *"Do not run LUA scripts from untrusted
  sources."* En modo servidor, solo personas autorizadas deben poder introducir/modificar scripts.
- Para "solutions" el acceso a la librería `io` está deshabilitado.

## 7. Diseño propuesto del MCP (cuando se construya)

```
LLM → MCP (FastMCP, en Windows) → genera script LUA → WinOLS "External Control"
                                   ├─ modo servidor (preferido): dejar "ticket file" → leer respuesta
                                   └─ modo CLI: lanzar winols.exe con la ruta del .lua
```

Tools candidatas (cada una genera el LUA correspondiente, verificar firma en el PDF):
- `winols_find_projects`      → `FindProjects` / `FindProjects2`      (lectura → allow)
- `winols_open_version`       → `OpenProjectVersion`                  (lectura → allow)
- `winols_export`             → `projectExport` / `OpenAndExport`     (lectura → allow)
- `winols_export_maps`        → `projectExportMaps`                   (lectura → allow)
- `winols_search_checksums`   → `projectSearchChecksums`              (lectura → allow)
- `winols_apply_checksums`    → `projectApplyChecksums`               (**modifica → ask**)
- `winols_set_property`       → `projectSetProperty`                  (**modifica → ask**)
- `winols_duplicate_project`  → `DuplicateProject`                    (ask)
- `winols_delete_version`     → `DeleteProjectVersion`                (**destructivo → ask**)

> Cualquier operación que **escriba a la ECU** o borre datos → `ask` con confirmación, sin excepción
> (un error puede inutilizar una centralita). Patrón del MCP: FastMCP + permissions, como en
> `docs/mcp-toolbox.md` §8ter.

## 8. Qué falta para construirlo (realista)

1. Una **máquina Windows** con WinOLS registrado + el plugin **External Control** (de pago).
2. Leer en el PDF las **firmas exactas** de las funciones que se vayan a usar.
3. Decidir transporte LUA↔MCP: **modo servidor (ticket files)** recomendado vs CLI.
4. Construir con el patrón FastMCP del toolbox; destructivas en `ask`.

**Fuente:** EVC, `winols HelpEn.pdf` (plugin External Control / LUA). Samples:
https://www.evc.de/en/product/ols/lua.asp
