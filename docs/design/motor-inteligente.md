# Diseño: MCP inteligente (motor de decisiones + workflows)

**Estado:** propuesta, pendiente de aprobación. Nada de esto está implementado todavía.
**Fecha:** 2026-10-29.

## 1. Objetivo real

Que `notebooklm-hub` **no delegue cada paso al LLM del cliente** (Kiro, Claude, Cursor…).
El LLM conversa con el usuario; el MCP **sabe en qué estado está cada cuaderno, qué
procedimiento corresponde y qué sigue**, y lo ejecuta.

Ejemplo guía: *"Estamos en este cuaderno"* → el MCP ve que está sin organizar → propone
organizarlo → con un "sí", etiqueta las fuentes por tema **y** crea un mapa mental por cada
etiqueta, sin que el LLM tenga que decidir cada paso ni volver a preguntar al usuario.

## 2. Diagnóstico (lo comprobado, no supuesto)

| Pregunta | Respuesta | Evidencia |
|---|---|---|
| ¿Hace falta un SDK de Gemini para "pensar"? | **No, de momento.** NotebookLM ya trae la IA necesaria, anclada a las fuentes: autoetiquetado temático y mapas mentales por lista de fuentes | jacob-bd `core/labels.py:auto_label` (`agX4Bc`), `core/studio.py:generate_mind_map(notebook_id, source_ids)` (`yyryJe`); teng-lin `rpc/_identifiers.py` |
| ¿Hace falta un framework de agentes (Strands…)? | **No.** El agente ya es el cliente MCP; meter otro dentro crea dos "cerebros" compitiendo | coincide con tus notas "sdk" y "ch2" |
| ¿Qué falta de verdad? | Estado persistente + reglas + workflows reanudables + aprobación | `_app/` hoy solo tiene verbos de un paso (`ask`, `notebooks`) |
| ¿Faltan capacidades de NotebookLM? | **Sí:** etiquetas (leer / autoetiquetar) y mapas mentales (generar / guardar / listar) | no existen aún en `src/` |
| ¿El MCP puede ver la pestaña del navegador? | **No.** Solo lo que le pasen o lo que lea por la API | — |
| ¿Hay alguna señal de "cuaderno abierto"? | **Sí, aproximada:** `last_viewed_at` de `notebook_list` (la lista viene ordenada por último visto) | teng-lin `_web/notebooks.py:list` (live-observed). Es inferencia, no confirmación |
| ¿Cómo pedir permiso sin pasar por el LLM? | **MCP elicitation:** el servidor pregunta directamente al usuario (`ctx.elicit`) | FastMCP 4.1.4 instalado. Soporte en clientes: **sin verificar** (Kiro/Claude) → plan B obligatorio |

### Lo que aportan los 7 repos aquí

| Repo | Qué tiene | Veredicto |
|---|---|---|
| jacob-bd | Pipelines YAML lineales (`services/pipeline.py`, 3 plantillas: ingest-and-podcast…), `labels`, `smart_select` (tags locales por cuaderno) | **Idea útil** (plantillas declarativas). **No sirve de base:** sin estado, sin reanudar, sin aprobación. Además su `list_labels` **autoetiqueta si no hay etiquetas**: leer modifica → descartado para el detector |
| teng-lin | Lectura pura de etiquetas `LIST_LABELS = I3xc3c` (separada de crear `agX4Bc`), `_idempotency.py` ("commit evidence and replay decisions": no repetir a ciegas una escritura dudosa) | **Base** para leer estado sin efectos y para la política de reintentos |
| roomi / ishandutta / PleasePrompto / Zidong | Nada de workflows | — |

## 3. Arquitectura propuesta (mínima, encaja en lo que ya hay)

```
cliente MCP (LLM)                     ← conversa, no orquesta
   │  notebook_assist(notebook, mode)  ← UNA tool "inteligente" como puerta de entrada
   ▼
_app/engine/            NUEVO — sin FastMCP/FastAPI dentro
   snapshot.py     lee el estado REAL del cuaderno (solo lecturas, nunca escribe)
   rules.py        estado → hallazgos ("sin etiquetar", "etiqueta sin mapa", "fuentes nuevas")
   workflows/      procedimientos declarativos versionados (onboarding_v1…)
   runner.py       ejecuta el siguiente paso seguro, verifica, persiste, reanuda
   store.py        SQLite (biblioteca estándar): runs, steps, aprobaciones, snapshots
   │
   ▼
core/client.py → transporte        ← igual que ahora
```

Reglas de diseño:
- **El código decide las transiciones; la IA de NotebookLM genera el contenido.** El LLM del
  cliente solo interviene para hablar con el usuario.
- **Leer nunca modifica** (detector y `snapshot` solo usan RPCs de lectura).
- **Toda escritura se verifica** releyendo el estado; si el resultado es dudoso (timeout tras
  enviar), se comprueba antes de repetir (patrón teng-lin `_idempotency`).
- **Aprobación con alcance:** se guarda por *cuaderno + workflow + versión*. Un "sí" a organizar
  no autoriza a borrar nada.
- Las fachadas MCP/REST siguen finas; las tools nuevas se descubren solas (registry).

## 4. Cómo se ve para el usuario

```
Usuario:  "Vamos a trabajar en el cuaderno Motores"
LLM  →    notebook_assist(notebook="Motores")
MCP  →    { estado: "sin_organizar", fuentes: 12, etiquetas: 0, mapas: 0,
            recomendacion: "organizar", plan: ["etiquetar 12 fuentes por tema",
            "crear 1 mapa mental por etiqueta", "verificar"], requiere_aprobacion: true }
          (si el cliente soporta elicitation, el MCP pregunta él mismo: "¿Organizo el cuaderno?")
Usuario:  "sí"
LLM  →    notebook_assist(notebook="Motores", approve="onboarding_v1")
MCP  →    etiqueta → [Inyección, Turbo, Electrónica] → mapa por etiqueta → verifica
          { hecho: true, etiquetas: 3, mapas: 3, run_id: "…" }
```

Si se corta a mitad (o se recarga la página, o se reinicia el servidor), la siguiente llamada
a `notebook_assist` **continúa desde el paso pendiente**; no repite lo hecho.

Y en visitas posteriores, el mismo `notebook_assist` detecta cambios: *"hay 4 fuentes nuevas sin
etiquetar; ¿las clasifico y actualizo sus mapas?"*.

## 5. Workflow `onboarding_v1` (declarativo)

| # | Paso | Tipo | Hecho cuando… |
|---|---|---|---|
| 1 | `snapshot` | lectura | hay foto del cuaderno (fuentes, etiquetas, mapas) |
| 2 | `approval` | humano | aprobación guardada para este cuaderno + workflow |
| 3 | `auto_label` | escritura (IA de NotebookLM) | al releer, todas las fuentes tienen etiqueta |
| 4 | `mind_map_per_label` | escritura, 1 por etiqueta | al releer, cada etiqueta tiene su mapa |
| 5 | `verify` | lectura | snapshot final coincide con lo esperado |

Cada paso declara: precondición, acción, verificación, si necesita aprobación y si es seguro
reintentarlo. Añadir otro procedimiento (p. ej. "fuentes nuevas → reclasificar → regenerar mapas
afectados") es añadir un archivo en `workflows/`, sin tocar el motor.

### Recetas concretas

Los procedimientos reales (configurar chat, Deep Research, **método de las 3 notas**, **mapa de
cobertura**) y las reglas que deciden cuál toca están en [`recetas.md`](recetas.md).

## 6. Plan B si el cliente no soporta elicitation

`notebook_assist` devuelve `requiere_aprobacion: true` + el plan, y el LLM se lo pregunta al
usuario y vuelve a llamar con `approve=...`. Es **una** pregunta, no una por paso.

## 7. ¿Cuándo sí entraría un SDK de modelo?

Solo si aparece un paso que NotebookLM no sepa hacer, p. ej. "escribir un prompt de mapa
personalizado por etiqueta con reglas propias". Aun así, primera opción: **pedírselo al propio
cuaderno con `notebook_ask`** (gratis y anclado a las fuentes). Si no basta, se añadiría detrás
de una interfaz `InternalLLM` como **extra opcional** (`.[llm]`), proveedor intercambiable
(Gemini / Ollama en el NAS). No se instala nada especulativamente.

## 8. Fases

| Fase | Entrega | Depende de |
|---|---|---|
| **A. Capacidades** | Tools `label_list` (lectura pura), `label_auto`, `mind_map_generate`, `mind_map_list` — comparando los 7 antes (regla del repo) | PRs #4/#6 fusionados |
| **B. Motor** | `store.py` (SQLite) + `snapshot` + `rules` + `runner`, probado con cliente falso: reanudar, no duplicar, aprobación persistente, escritura dudosa | A (solo interfaces) |
| **C. Primer workflow** | `onboarding_v1` + tool `notebook_assist` (+ `elicitation` con plan B) | A + B |
| **D. Cambios posteriores** | reglas "fuentes nuevas", "etiqueta sin mapa" + workflow de actualización | C |
| **E. Prueba real** | en el NAS con cuenta dedicada | todo |

## 9. Incertidumbres (a verificar, no asumidas)

- Forma exacta de las respuestas de etiquetas y mapas (se comparará jacob-bd vs teng-lin en A).
- Si generar un mapa mental lo **guarda** solo o hace falta el segundo RPC (`CYK0Xb`) — jacob-bd
  sugiere dos pasos.
- Soporte de **elicitation** en Kiro CLI / Kiro Web / Claude Desktop.
- Límite de etiquetas o de mapas por cuaderno y la cuota de NotebookLM.
- Dónde guardar el SQLite en el NAS (fuera del repo; ruta configurable por variable de entorno).

## 10. Tus notas, clasificadas (regla "no se borra, se fusiona")

| Idea (tus notas) | Estado | Motivo |
|---|---|---|
| "1"/"2"/"a": tools con Gemini dentro (`analizar_incidencia`, `notebook_summarize_smart`, `smart_patch`, `log_analyser`, `to_json`) | **FUERA DE ALCANCE por ahora** | Son tools de otro dominio o que duplican lo que NotebookLM ya hace con sus fuentes; quedan como ideas para §7 si surge la necesidad |
| "sdk": Google GenAI mejor que Strands | **INTEGRADO, matizado** | No a Strands; Gemini SDK tampoco hace falta aún (§2, §7) |
| "protmp"/"2": meta-prompt con matriz de SDKs | **PENDIENTE** | Útil como plantilla genérica; su hogar es `Varios_tools/construir-mcp`, no este repo |
| "mcp int"/"ch"/"ch2": motor de decisión propio + estado + workflows | **INTEGRADO** | Es el núcleo de este diseño (§3–§5) |
| "2" (propuesta concreta): `workflow_engine`, SQLite 3 tablas, `run_id`, aprobación persistente, reconciliar sin reiniciar | **INTEGRADO, ajustado** | Nombres adaptados; una sola tool de entrada (`notebook_assist`) en vez de 5 para que el LLM no tenga que orquestar |
| Detectar pestaña con extensión de navegador | **PENDIENTE (opcional)** | Primero `last_viewed_at` + modo explícito; extensión solo si hace falta inmediatez |
| "pr"/"pr 2": especificación genérica + §11 diagnóstico adaptativo | **INTEGRADO como método** | Es lo que se aplicó para escribir este documento; la plantilla genérica va a `Varios_tools/construir-mcp` |
| Elicitation (no estaba en tus notas) | **NUEVO** | Resuelve "si el usuario dice sí, el MCP lo hace" sin otra vuelta por el LLM |
