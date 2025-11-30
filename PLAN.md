# Plan de Trabajo - Proyecto Kaggle Agents

Este es el plan de trabajo para adaptar el proyecto a los requerimientos de la competición de Kaggle en 3 días.

## Día 1: Requisitos Fundamentales

- [x] **1. Implementar Memoria (Sessions & Memory):**
  - [x] Modificar `src/doc_squad.py` para que los agentes recuerden interacciones pasadas.
  - [x] Asegurar que el historial de la sesión se pasa en cada llamada al agente.

- [x] **2. Añadir Observabilidad (Observability):**
  - [x] Reemplazar los `print()` por un sistema de `logging` profesional en `src/doc_squad.py`.
  - [x] Configurar el logger para que escriba en `doc_squad.log` y en la consola.

## Día 2: Evaluación y Presentación

- [x] **3. Crear un Script de Evaluación (Agent Evaluation):**
  - [x] Crear el fichero `evaluate_agent.py`.
  - [x] Implementar un "agente evaluador" que compare la documentación generada con una versión "ideal".
  - [x] Definir métricas de puntuación (ej. completitud, precisión, formato).

- [x] **4. Mejorar el README (Pitch & Write-up):**
  - [x] Reestructurar `README.md` para enfocarlo como un "pitch" de problema/solución.
  - [x] Añadir secciones claras sobre el problema, la solución y el impacto del proyecto.

## Día 3: Bonus y Entrega

- [x] **5. Grabar Video de Demostración (Bonus):**
  - [x] Grabar un video corto (< 2 min) mostrando la aplicación Streamlit en acción.
  - [ ] Subir el video a una plataforma pública (ej. YouTube, Google Drive).

- [ ] **6. Revisión Final:**
  - [ ] Limpiar el código y añadir comentarios donde sea necesario.
  - [ ] Actualizar `requirements.txt` si hay nuevas dependencias.
  - [ ] Realizar un commit final y preparar el repositorio para la entrega.