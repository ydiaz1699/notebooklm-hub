Haz que Gemini lea archivos gigantes sin perderse
El problema no es el modelo, es que nadie le dio un mapa. Con este método la IA primero consulta un índice inteligente de tu documento y después valida la respuesta en el archivo real.

La ruta completa en una línea:
PDF → Markdown → NotebookLM construye el MAPA DE COBERTURA → guardas el mapa como fuente → configuras el cuaderno de Gemini para que navegue con él.

1
Convierte tu PDF a Markdown
Los modelos leen mejor el texto plano que los PDF pesados. Entra a MarkitDown, sube tu archivo y descarga la versión en Markdown (.md). Es gratis y tarda segundos.

Tip: si tu documento ya es texto (Word, Google Docs), puedes saltarte este paso y subirlo directo.

2
Súbelo a NotebookLM
Abre un cuaderno en NotebookLM y agrega el archivo Markdown como fuente. Este será tu documento principal.

3
Genera el MAPA DE COBERTURA
Pega este prompt en el chat del cuaderno. No le pide un resumen: le pide un sistema de navegación completo del documento.

prompt-mapa-de-cobertura.txt
Copiar
Analiza exhaustivamente todo el documento y construye un MAPA DE COBERTURA completo. Tu objetivo no es resumir el contenido sino crear un sistema de navegación que permita localizar con precisión cualquier tema dentro del documento. Recorre el documento de principio a fin e identifica todos los capítulos, secciones, subsecciones y temas relevantes. Para cada elemento incluye el título exacto, su ubicación aproximada dentro del documento (páginas o rango equivalente), los temas principales tratados, los conceptos clave y las palabras clave más importantes para búsquedas futuras. Conserva la estructura jerárquica completa del documento y no omitas ninguna sección relevante. Si una sección es muy extensa, divídela en subsecciones más específicas para mejorar la localización de la información. Entrega el resultado en formato Markdown bajo el título "MAPA DE COBERTURA", organizando cada nivel de contenido de manera clara y consistente. Prioriza la cobertura total del documento y la capacidad de encontrar información rápidamente sobre los resúmenes o explicaciones detalladas. El resultado final debe funcionar como un índice inteligente que permita a otro modelo identificar exactamente dónde buscar información dentro del documento original.
4
Guarda el mapa como fuente "MAPA"
Cuando NotebookLM te entregue el mapa de cobertura, guárdalo como una nueva fuente del cuaderno con el nombre exacto MAPA. Ese nombre importa: la instrucción del siguiente paso lo busca así.

Cómo: en la respuesta usa "Guardar en nota" y luego conviértela en fuente, o copia el texto y agrégalo como fuente nueva pegándolo.

5
Configura el cuaderno para que navegue con el mapa
Pega esta instrucción en la configuración del cuaderno (o al inicio de tu conversación). Desde ese momento, Gemini consulta primero el MAPA y después valida en el documento largo.

instruccion-cuaderno-gemini.txt
Copiar
Antes de responder cualquier pregunta, consulta primero la fuente llamada "MAPA". Utiliza el mapa de cobertura para identificar las secciones, subsecciones y ubicaciones más relevantes para la consulta. Una vez identificadas, revisa únicamente las partes correspondientes del documento principal para validar la información. No asumas que una respuesta está completa hasta haber comprobado en el MAPA que has revisado todas las secciones potencialmente relacionadas con la pregunta. Si la consulta puede involucrar múltiples temas, busca y valida cada uno por separado utilizando el MAPA como guía de navegación. Siempre que sea posible, indica qué secciones del documento respaldan tu respuesta. Si el MAPA no contiene información suficiente para localizar una respuesta con confianza, indícalo explícitamente. Tu prioridad es la cobertura completa y la precisión de la búsqueda dentro del documento, no la velocidad de respuesta. Considera el MAPA como la fuente principal de navegación y el documento largo como la fuente principal de validación.
6
Pregunta lo que quieras
Ya está montado el sistema. Ahora pregunta como siempre, con una diferencia: las respuestas vienen ubicadas (qué sección del documento las respalda) y completas (revisó todas las secciones relacionadas antes de responder).

"¿Qué dice el contrato sobre penalidades por retraso?"
"Compara lo que el informe dice de X en el capítulo 2 y en el 7."
"¿En qué secciones se habla del presupuesto?"
La clave del truco

Gemini primero consulta el mapa y después busca en el archivo largo con más precisión. Guárdalo: te puede ahorrar horas revisando PDFs gigantes.