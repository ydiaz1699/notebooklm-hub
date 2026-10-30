# Recetas del MCP inteligente (prompts que el MCP aplica solo)

**Estado:** propuesta, complementa [`motor-inteligente.md`](motor-inteligente.md). Sin código aún.
**Fecha:** 2026-10-29.

## 1. La idea

Hoy, para sacarle todo el partido a NotebookLM hay que **acordarse** de aplicar ciertos métodos y
**pegar los prompts a mano** en cada cuaderno (vídeo + prompts de `_drafts/prompt/`; créditos en [`CREDITS.md`](../../CREDITS.md)). Es
agotador y fácil de olvidar.

Con el motor inteligente:
- los **prompts viven en el MCP** como recetas versionadas (no se pegan nunca más);
- las **reglas** miran el estado del cuaderno y deciden **qué receta toca** (el usuario no
  tiene que acordarse);
- el **motor** ejecuta todos los pasos de la receta (seleccionar fuentes, preguntar, seguir si la
  respuesta se corta, guardar como fuente, nombrar, mover a su etiqueta) **sin volver al LLM**.

## 2. Las 4 recetas

Origen: vídeo "3 cosas de Gemini Notebook" + `_drafts/prompt/1` y `_drafts/prompt/2`
(créditos en [`CREDITS.md`](../../CREDITS.md)).

### R1 · `configurar_chat` (vídeo, punto 1)
- **Qué hace:** pone la personalización del chat del cuaderno (objetivo, tono y formato,
  prohibiciones) en *Configurar → Personalizar*.
- **Datos que necesita:** objetivo del cuaderno, tono/formato, lo que nunca debe hacer. Se piden
  al usuario **una vez** (elicitation o una pregunta del LLM), o se proponen a partir de las fuentes
  con `notebook_ask` y el usuario solo confirma.
- **Capacidad:** `configure_chat(goal="custom", custom_prompt=…)`, máx. **10 000 caracteres**
  (jacob-bd `core/notebooks.py:218`; teng-lin `_chat.py:_send_configure`).

### R2 · `buscar_fuentes` (vídeo, punto 2)
- **Qué hace:** lanza la búsqueda de fuentes con un prompt de investigación "por intención" en
  modo **Deep Research** y las importa.
- **Capacidad:** `start_research(mode="deep")` (~5 min, ~40 fuentes, solo web) → estado → importar
  (jacob-bd `core/research.py`; teng-lin `_research.py`). Es asíncrono: el motor guarda el
  `task_id` y sigue en la siguiente llamada.
- **Pendiente:** el prompt de investigación del vídeo no está en `_drafts/prompt/` (solo se
  menciona). Habría que añadirlo.

### R3 · `metodo_3_notas` (vídeo punto 3 + `_drafts/prompt/2`)
Por **cada etiqueta (categoría)** del cuaderno:

| # | Paso | Fuentes que se usan | Resultado |
|---|---|---|---|
| 1 | Autoetiquetar (si no hay etiquetas) | todas | categorías por tema |
| 2 | Prompt **1 · Puntos clave por fuente** | solo las de la categoría | nota 1 |
| 3 | Prompt **2 · Índice de preguntas y problemas** | solo las de la categoría | nota 2 |
| 4 | Prompt **3 · Síntesis y conclusiones** | originales de la categoría **+ notas 1 y 2** (el propio prompt lo exige) | nota 3 |
| 5 | Guardar cada nota como **fuente** con nombre fijo `1. Puntos clave – <categoría>`, `2. Índice de preguntas – <categoría>`, `3. Síntesis – <categoría>` y moverla a su etiqueta | — | 3 fuentes por categoría |
| 6 | "Apagar el ruido" | — | ver §4 |

### R4 · `mapa_de_cobertura` (`_drafts/prompt/1`)
Para cuadernos con **un documento muy largo**:

| # | Paso | Resultado |
|---|---|---|
| 1 | Prompt **mapa de cobertura** sobre el documento | índice navegable en Markdown |
| 2 | Guardarlo como fuente con nombre exacto **`MAPA`** (la instrucción lo busca así) | fuente `MAPA` |
| 3 | Poner la **instrucción "consulta primero el MAPA"** en la personalización del chat (R1) | el chat navega con el mapa |

El paso de la guía "convierte el PDF a Markdown con MarkItDown" queda **fuera** del MCP por ahora
(es antes de subir la fuente). Se podría añadir como paso opcional de `source_add` en el futuro.

## 3. Reglas: cuándo propone cada receta el MCP

El motor mira el estado real del cuaderno (solo lecturas) y propone **una** cosa clara:

| Si el cuaderno… | Propone | Por qué |
|---|---|---|
| no tiene personalización de chat | R1 | es el primer paso del vídeo; mejora todo lo demás |
| tiene 0–2 fuentes | R2 | no hay material con el que trabajar |
| tiene **1 documento muy largo** y no tiene fuente `MAPA` | R4 | el caso del "archivo gigante" |
| tiene **muchas fuentes mezcladas** (≥ umbral, p. ej. 10) sin etiquetas | R3 completo | "no trabajes con 50 fuentes mezcladas" |
| tiene una etiqueta **sin sus 3 notas** | R3 solo para esa etiqueta | trabajo pendiente o interrumpido |
| tiene **fuentes nuevas** desde la última vez en una etiqueta ya procesada | rehacer las notas de esa etiqueta | las notas quedaron desactualizadas |
| tiene todo lo anterior hecho | nada; solo informa | no repetir trabajo |

Los umbrales (cuántas fuentes son "muchas", qué tamaño es "muy largo") son configurables, no
números mágicos en el código.

## 4. Lo que el MCP resuelve con código (sin LLM)

| Problema de hacerlo a mano | Cómo lo resuelve el motor |
|---|---|
| Hay que **seleccionar** solo las fuentes de la categoría | `notebook_ask(source_ids=…)` con las fuentes de la etiqueta, leídas del estado |
| La respuesta se corta y termina en `CONTINUAR: faltan …` | Detecta la línea, pide "continúa" en la **misma conversación** (`conversation_id`) y junta las partes; máximo N vueltas |
| Hay que "Guardar en nota" y luego "convertir en fuente" | Añade el texto directamente como **fuente de texto** con su nombre (la guía lo admite: "copia el texto y agrégalo como fuente nueva"). Menos pasos y menos RPCs |
| El nombre importa (`MAPA`, `1. Puntos clave – …`) | Nombres fijos definidos en la receta, nunca inventados |
| Dejar activas solo las 3 notas | Al **preguntar desde el MCP**, el motor manda solo las 3 notas de la categoría correspondiente. Ver limitación abajo |
| Saber qué categorías ya están hechas | Estado en SQLite + verificación releyendo el cuaderno |

**Limitación de "apagar el ruido":** marcar/desmarcar fuentes en la web es **estado de la página**,
no del cuaderno (por lo que se sabe: el chat recibe la lista de fuentes en cada pregunta, ver
`web_chat.build_query_params`). El MCP puede hacerlo al preguntar **por el MCP**; si el usuario
chatea en la web, tendrá que desmarcarlas allí. Pendiente de confirmar en real.

**Mejora posible (no en la guía):** que `notebook_ask` enrute solo: con la nota 2 (índice de
preguntas) de cada categoría, el motor elige la categoría y pregunta a sus 3 notas. Se deja para
después de tener R3 funcionando.

## 5. Cómo se guardan las recetas en el repo

```
src/notebooklm_hub/_app/recipes/
  configurar_chat_v1.yaml
  metodo_3_notas_v1.yaml
  mapa_de_cobertura_v1.yaml
  prompts/
    puntos_clave_v1.md          ← texto del prompt, versionado
    indice_preguntas_v1.md
    sintesis_conclusiones_v1.md
    mapa_cobertura_v1.md
    instruccion_navegar_mapa_v1.md
```

Cada receta declara: cuándo aplica (regla), pasos, qué fuentes usa cada paso, prompt, nombre de
la fuente resultante, verificación y si necesita aprobación. **Cambiar un prompt = editar un
`.md` y subir la versión**; el motor no se toca. Las recetas se exponen también como **MCP
prompts** para quien quiera usarlas a mano.

## 6. Capacidades de NotebookLM que hacen falta

| Capacidad | Hay en | En notebooklm-hub |
|---|---|---|
| Preguntar con fuentes concretas + seguir conversación | — | ✅ `notebook_ask` (PR #6) |
| Leer etiquetas (sin modificar) | teng-lin `LIST_LABELS = I3xc3c` | ✅ `label_list` |
| Autoetiquetar | jacob-bd/teng-lin `agX4Bc` | ✅ `label_auto` (incremental) · `label_reorganize` (destructiva) |
| Mover fuente a etiqueta | jacob-bd `core/labels.py:move_source_to_label`, teng-lin `le8sX` | ✅ `label_add_source` |
| Añadir fuente de texto con título | jacob-bd `core/sources.py:add_text_source` | ✅ `source_add_text` (con reconciliación) |
| Renombrar fuente | jacob-bd `core/sources.py:rename_source` | ✅ `source_rename` |
| Personalizar chat (≤ 10 000 chars) **y leerla** | jacob-bd `configure_chat`, teng-lin `_send_configure`/`_read_settings` | ✅ `chat_configure` · `chat_settings_get` |
| Deep Research | jacob-bd `core/research.py`, teng-lin `_research.py` | ✅ `research_start` · `research_status` · `research_import` |

Todas existen en los repos de referencia; antes de implementarlas se compararán los 7
(regla del repo, `.kiro/steering/mejor-de-los-7.md`).

## 7. Procedencia y licencia de los prompts

Los prompts se pueden redistribuir (colaboración del autor con quien los creó; decisión del
2026-10-29). **Los archivos de prompt no llevan cabecera de atribución**: los créditos de todos
los contribuyentes están en un único archivo, [`CREDITS.md`](../../CREDITS.md).

## 8. Orden de trabajo propuesto

1. **Fase A ampliada:** capacidades de la tabla §6, comparando los 7.
2. **Fase B:** motor (estado SQLite, snapshot, reglas, runner).
3. **Fase C:** primero **R3** (es la más pedida y la que más pasos ahorra), luego R4, R1 y R2.
4. Tool de entrada única `notebook_assist` (ver `motor-inteligente.md` §4).
