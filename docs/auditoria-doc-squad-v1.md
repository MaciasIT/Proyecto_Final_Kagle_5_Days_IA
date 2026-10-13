# Auditoría técnica y requisitos para Doc Squad v2

**Fecha:** 13-10-2026  
**Repositorio auditado:** `/home/m1txel/proyectos/Proyecto_Final_Kagle_5_Days_IA`  
**Rama/commit observado:** `main`, `dbc8b36` (`Chore: Limpieza de scripts de diagnóstico`); árbol de trabajo limpio al inicio.  
**Alcance:** inspección estática del código, documentación, notebooks y manifiesto; comprobación de sintaxis Python. No se ejecutó el flujo Gemini ni se enviaron archivos/credenciales a servicios remotos.

## Resumen ejecutivo

El repo contiene una demo/prototipo, no un pipeline fiable de documentación: la subida produce un URI como texto, pero no se pasa el contenido multimedia al Analyst como entrada multimodal; los tres runners mantienen ejecuciones/sesiones separadas; no hay validación del análisis ni revisión de la documentación. Además, los modelos Gemini 1.5 configurados están apagados desde el 29-09-2025 y el SDK `google-generativeai` está archivado y fuera de soporte desde el 30-11-2025. El camino feliz descrito en README/USAGE no está respaldado por pruebas automatizadas.

**Bloqueo de seguridad P0:** `kaggle.json` está versionado en Git. El notebook local también conserva salida de una celda que introdujo una API key; el visor la ha censurado, así que no se reproduce aquí ningún valor. Tratar ambos como posible exposición de credenciales: Michel debe revisar/revocar las credenciales afectadas y decidir la limpieza del historial antes de publicar o compartir el repo. No se inspeccionó el contenido de `kaggle.json`.

## Hechos verificados

- El manifiesto `requirements.txt` contiene dependencias sin versiones fijadas; README declara Python 3.8+ (README:3,50), mientras que el quickstart actual de ADK exige Python 3.10+ y el README actual del paquete ADK señala Python 3.11+.
- El código productivo, `verify_pipeline.py` y ambos notebooks usan `google.generativeai`; ADK define los modelos `gemini-1.5-pro-001` y `gemini-1.5-flash-001` (`src/doc_squad.py:4-7,46-101`; `verify_pipeline.py:4-7,42-74`).
- `src/doc_squad.py` hace polling bloqueante con `time.sleep(2)` en la herramienta de ingesta (`:17-40`) y envuelve el flujo asíncrono en `asyncio.run` (`:139-143`).
- `run_pipeline_async` crea tres `InMemoryRunner` independientes y concatena texto entre ellos (`:106-136`). El paso Analyst solo recibe texto que incluye la respuesta textual de ingesta y el contexto, no un objeto/parte multimodal con el vídeo (`:121-127`).
- `verify_pipeline.py` duplica agentes/código, apunta a una ruta local fija que no coincide con la ruta del repo auditado (`:80`), no transfiere el URI ni la salida real entre pasos (`:91-109`) y acaba imprimiendo `REAL PIPELINE TEST PASSED` sin aserciones (`:111`). Si falta API key, termina con código 0 (`:11-14`).
- El notebook local contiene un `pass` donde debería extraer eventos, envía prompts que asumen el resultado del paso anterior y devuelve un mensaje genérico en vez del documento final (`project_notebook_local.ipynb`, celdas de código 5 y salida asociada). Sus salidas almacenadas muestran un error 500 histórico, no una prueba reproducible del estado actual.
- En `app.py`, la API key introducida en Streamlit se copia a `os.environ` y se configura con el cliente global (`:50-61`); el `except` enseña el mensaje de excepción completo (`:132-133`).
- El chequeo `python -m compileall -q app.py src/doc_squad.py verify_pipeline.py` terminó con código 0. Esto solo verifica sintaxis, no compatibilidad de APIs, comportamiento, autenticación ni llamadas al modelo.

## Deuda técnica priorizada

| Prioridad | Deuda / evidencia | Impacto |
|---|---|---|
| P0 | `kaggle.json` versionado; salida del notebook local contiene una entrada de API key (credencial censurada en esta auditoría). | Exposición de credenciales, uso no autorizado y permanencia en historial aunque se borre el archivo actual. |
| P0 | Modelos `gemini-1.5-*` fijados en runtime y notebooks. Google marca Gemini 1.5 Pro/Flash apagados desde 29-09-2025. | Llamadas que fallan; no hay producto ejecutable sobre el proveedor actual. |
| P0 | SDK `google-generativeai` ya no soportado. Google recomienda migrar a `google-genai`; el repositorio legado fue archivado y el soporte terminó el 30-11-2025. | Riesgo de fallos y ausencia de correcciones/funcionalidad nueva; la ingesta depende directamente de ese SDK. |
| P1 | No se entrega el medio al Analyst como entrada multimodal; se le da un URI dentro de texto plano (`src/doc_squad.py:121-127`). No se garantiza que el modelo pueda abrirlo. | El análisis puede ser inventado, genérico o incapaz de corresponder al archivo seleccionado. |
| P1 | Tres runners independientes; no se establece una sesión compartida ni contratos estructurados de salida. | El flujo depende de texto libre generado por modelos y no de datos verificables. |
| P1 | Sin agente evaluador/critic, iteración de corrección, verificación de comandos ni gate humano. | Errores y contenido peligroso pueden alcanzar directamente el Markdown descargable. |
| P1 | Polling sin timeout/cancelación, llamadas síncronas dentro de ruta async, errores representados como texto y sin clasificación/reintentos (`src/doc_squad.py:17-40`). | Bloqueos, consumo indefinido y errores que pueden confundirse con resultados válidos. |
| P1 | Uso de `asyncio.run` en wrapper invocable desde Streamlit/notebook (`src/doc_squad.py:139-143`). | Falla si el llamador ya tiene un event loop en ejecución. |
| P1 | `verify_pipeline.py` no comprueba resultado, usa ruta absoluta y llama “passed” aunque solo haya terminado la secuencia (`:80-111`). | Falsa confianza de QA; el test no detecta regresiones de transferencia ni calidad. |
| P1 | API key de usuario en `os.environ` global y configuración global de cliente (`app.py:50-61`). | En despliegue multiusuario, riesgo de contaminación entre sesiones/usuarios y acoplamiento de estado. |
| P2 | Dependencias flotantes, sin lock/constraints ni contrato mínimo de Python; setup instala paquetes y abre Jupyter sin fijar entorno. | Instalaciones no reproducibles y cambios incompatibles entre máquinas/fechas. |
| P2 | Contradicción entre docs/notebooks/implementación: READMEs prometen pipeline real y descarga final, mientras que notebooks contienen simulaciones/retornos genéricos; `verify_pipeline.py` usa otra ruta y flujo. | Expectativas erróneas y dificultad para saber qué experiencia es canónica. |
| P2 | Sin política de tamaño/tipo, límites de duración/coste, retención/borrado explícito del archivo remoto ni observabilidad por etapa. | Riesgo de coste, privacidad, latencia y soporte de incidencias. |

## ADK: estado y decisión técnica

No es preciso describir hoy todo Google ADK como “experimental”: la documentación oficial publica releases estables de `google-adk`. Sí hay deuda de antigüedad e incertidumbre en este repo: no fija versión, su documentación de Python contradice requisitos, usa runners y un patrón de tres agentes separados, y la documentación actual de ADK 2.0 indica que los agentes workflow de plantilla han sido sustituidos por workflows basados en grafos/dinámicos. El `SequentialAgent` sigue documentado para compatibilidad/uso, pero no conviene asumir que es la arquitectura recomendada actual ni que cualquier tutorial antiguo coincide con la versión instalada. Requisito v2: fijar una versión estable concreta de ADK y Python; construir una prueba de compatibilidad mínima para API, workflows, eventos/estado y ejecución; decidir tras revisión técnica independiente si ADK aporta valor frente a orquestación explícita y simple.

## Catálogo de requisitos para v2 (propuesta para decisión de Michel)

### P0 — Seguridad y disponibilidad básica

1. **Rotación y saneamiento de credenciales:** inventariar credenciales en archivos y outputs/historial; revocar/rotar las posiblemente expuestas; quitar los archivos de credenciales del control de versiones e historia según decisión/alcance de Michel; añadir reglas y un secret scan a CI. Criterio: ningún secreto real en HEAD, notebooks, outputs o historial publicado; CI falla con un secreto de prueba.
2. **SDK/modelo soportado:** migrar todas las rutas y ejemplos de `google-generativeai` a `google-genai` y seleccionar un modelo de Gemini vigente según disponibilidad/coste acordados. Criterio: import/cliente explícito, subida/consulta/borrado de archivo y generación de contenido cubiertos por pruebas; no hay referencias ejecutables a modelos apagados.
3. **Entorno reproducible:** declarar versión mínima/objetivo de Python, fijar dependencias directas y transitivas o constraints/lockfile, y documentar comandos únicos de instalación/ejecución. Criterio: entorno limpio instala con los archivos del repo y pasa el suite sin depender de notebook ni del directorio personal.
4. **Privacidad de credenciales en UI:** no guardar credenciales de usuario en `os.environ` global compartido; manejar cliente/config por sesión o separar autenticación del usuario de credencial de servicio. Criterio: dos sesiones concurrentes de prueba no pueden leer ni reutilizar la credencial de la otra; logs/errores no imprimen secretos.

### P1 — Flujo fiel, trazable y verificable

5. **Contrato de ingestión:** validar existencia, extensión/MIME real, tamaño y duración antes de subir; crear URI/file handle explícito; espera asíncrona con timeout, cancelación, estados terminales y errores tipados; borrar el objeto remoto cuando deje de ser necesario, de acuerdo con la política de privacidad. Criterio: pruebas para inválido, processing, ready, failed, timeout y cancelación, con cero bucles infinitos.
6. **Entrada multimodal efectiva:** entregar a Analyst un objeto/parte multimodal soportado por el SDK, no solo el URI escrito como texto. Criterio: fixture multimedia corta contiene un dato observable que aparece correctamente en la extracción con referencia al origen.
7. **Orquestación determinista:** documentar una arquitectura única; pasar artefactos entre etapas como esquemas tipados/JSON validado, con IDs de job y estados; si se conserva ADK, usar APIs soportadas y una estrategia explícita de estado/sesión. Criterio: cada paso consume la salida validada del anterior; fallos no se convierten en éxito ni continúan silenciosamente.
8. **Analyst con evidencia:** extraer hechos con citas de timestamp/fragmento, confianza/incertidumbre y separación entre observado e inferido; no completar comandos/valores ilegibles. Criterio: los hechos críticos se rastrean a evidencia del archivo o aparecen marcados como no verificables.
9. **Critic/verificación y revisión:** añadir critic que contrasta borrador con extracción, detecta hechos no sustentados, comandos peligrosos y lagunas; bucle con máximo de iteraciones y parada explícita; revisión humana antes de presentar/publicar acciones de riesgo. Criterio: caso de afirmación inventada es rechazado/corregido y el loop siempre termina.
10. **Salida contractual:** Markdown con estructura versionada, títulos, pasos, avisos y referencias a evidencia; resultado vacío/incorrecto produce error, no documento vacío. Criterio: validación del esquema/estructura y tests de regresión de golden outputs.
11. **Pruebas reales, offline por defecto:** unitarias con cliente simulado, integración opcional bajo credencial explícita, e2e corta no destructiva cuando se habilite; eliminar rutas personales y el mensaje “PASSED” sin aserciones. Criterio: CI demuestra transferencia correcta, errores, output no vacío y límites; tests unitarios no llaman servicios externos.
12. **Resiliencia y observabilidad:** timeout por etapa, reintentos acotados solo para errores transitorios, límites de concurrencia/coste/tamaño, estado de progreso y logs estructurados con redacción de secretos/PII. Criterio: cada job deja estado final consultable y causa de fallo sin filtrar datos sensibles.

### P2 — Experiencia y mantenimiento

13. **Un solo camino canónico:** alinear README, USAGE, Streamlit, CLI y notebooks; o marcar notebooks como material histórico/didáctico sin presentarlos como implementación mantenida. Criterio: comandos copiados desde la guía funcionan en entorno limpio.
14. **Recursos temporales y límites de uso:** límites de tamaño/formatos soportados, limpieza garantizada de temporales locales/remotos y feedback de tiempo estimado/etapa. Criterio: tests demuestran limpieza tanto en éxito como en excepción.
15. **Calidad operativa:** manejar errores con mensajes seguros para usuario y diagnósticos internos; controles de coste/cuotas y consentimiento explícito para enviar multimedia. Criterio: errores internos no muestran stack/credenciales; el usuario conoce qué se enviará y por cuánto tiempo se retiene.

## Recomendación de secuencia (sin aprobación de decisiones de producto)

1. Resolver incidente potencial de credenciales y definir política de datos (P0 seguridad).  
2. Probar compatibilidad vigente y fijar stack/modelo/sdk (P0 dependencias).  
3. Implementar un vertical slice sin UI: archivo → análisis multimodal con evidencia → critic → Markdown, con tests simulados.  
4. Añadir límites, observabilidad y pruebas de integración controladas.  
5. Alinear Streamlit, CLI, notebooks y documentación al flujo verificado.

La selección de proveedor/modelo, política de retención, nivel de revisión humana y alcance de despliegue siguen siendo decisiones de Michel; esta auditoría no las da por aprobadas.

## Fuentes externas consultadas

- Migración oficial a Google GenAI SDK: https://ai.google.dev/gemini-api/docs/migrate — anuncia GA y recomienda migrar desde SDKs legacy; ejemplos Python usan `google-genai` y `genai.Client`.
- Repositorio oficial archivado del SDK antiguo: https://github.com/google-gemini/deprecated-generative-ai-python — soporte finalizado el 30-11-2025, repositorio archivado el 16-12-2025.
- Changelog oficial Gemini API: https://ai.google.dev/gemini-api/docs/changelog — Gemini 1.5 Pro/Flash apagados el 29-09-2025.
- Quickstart oficial ADK Python: https://adk.dev/get-started/python/ — instalación `google-adk`, requisitos documentados y patrón de agente actual.
- Workflows secuenciales ADK: https://adk.dev/agents/workflow-agents/sequential-agents/ — patrón determinista de agentes en serie y nota de transición a graph-based workflows desde ADK 2.0 para Python.
- README/release oficial ADK Python: https://github.com/google/adk-python — releases estables actuales y requisitos publicados por el proyecto.
