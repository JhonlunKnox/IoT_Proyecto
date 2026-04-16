# PlantSense — Backlog Inicial (Release 1)

## Cómo usar este backlog en GitHub Projects
1. Crear un nuevo Project en el repo → tipo "Board"
2. Crear columnas: `Backlog`, `Sprint Actual`, `En Progreso`, `Hecho`
3. Crear cada ítem como una **Issue** con el label correspondiente (`must-have` o `nice-to-have`)
4. Asignar las issues del Sprint 1 a la columna `Sprint Actual`

---

## Labels a crear en el repo
- `must-have` (color verde)
- `nice-to-have` (color azul)
- `spike` (color naranja)
- `hardware` (color amarillo)
- `backend` (color morado)
- `frontend` (color celeste)
- `docs` (color gris)

---

## RELEASE 1 — Fundamentos y Viabilidad (Semanas 1–2)

### Sprint 1 (Semana 1)

| # | Issue | Label | Asignado a | Descripción |
|---|-------|-------|-----------|-------------|
| 1 | **[SPIKE] Validar ESP32-CAM + clasificación visual** | `spike` `must-have` | Juan Pablo | Conectar ESP32-CAM, capturar imagen, enviar al backend, clasificar por color con OpenCV. Documentar resultado. |
| 2 | Configurar repositorio y estructura de carpetas | `must-have` `docs` | Juan Daniel | Crear repo, rama `main` y `develop`, carpetas `/firmware`, `/backend`, `/docs`. Subir README. |
| 3 | Conectar sensor de humedad al ESP32 | `must-have` `hardware` | Gabriel | Cablear sensor capacitivo, leer valor analógico, imprimir por Serial Monitor. |
| 4 | Enviar dato de humedad al backend vía HTTP | `must-have` `backend` | Juan Pablo | ESP32 hace POST con el valor de humedad. Backend lo recibe y guarda. |

### Sprint 2 (Semana 2)

| # | Issue | Label | Asignado a | Descripción |
|---|-------|-------|-----------|-------------|
| 5 | Conectar sensor de luz (BH1750 o LDR) | `must-have` `hardware` | Gabriel | Cablear sensor, leer valor de luminosidad, incluirlo en el payload HTTP. |
| 6 | Visualizar datos en el software existente | `must-have` `frontend` | Juan Daniel | Conectar el endpoint del backend al dashboard. Mostrar humedad y luz en tiempo real. |
| 7 | Definir umbrales de alerta | `must-have` `backend` | Juan Pablo | Configurar: humedad < X% → alerta "regar", luz < Y lux → alerta "más luz". |
| 8 | Crear GitHub Project board y pasar todas las issues | `must-have` `docs` | Juan Daniel | Organizar el backlog completo en el tablero de GitHub Projects. |

---

## RELEASE 2 — Integración visual (Semanas 3–4)

| # | Issue | Label | Descripción |
|---|-------|-------|-------------|
| 9 | Integrar ESP32-CAM al sistema | `must-have` `hardware` | Capturar imagen cada N minutos y enviarla al backend. |
| 10 | Endpoint backend para recibir imagen | `must-have` `backend` | Recibir imagen JPEG, guardar, ejecutar clasificación por color. |
| 11 | Clasificación básica de estado visual (OpenCV) | `must-have` `backend` | Analizar color promedio → clasificar como sana/con problemas. Retornar resultado. |
| 12 | Mostrar imagen + estado en dashboard | `must-have` `frontend` | El software muestra la última imagen capturada y el estado clasificado. |
| 13 | Integrar modelo TFLite para clasificación avanzada | `nice-to-have` `backend` | Reemplazar clasificación por color con modelo de ML entrenado en PlantVillage. |

---

## RELEASE 3 — Alertas y pulido (Semanas 5–6)

| # | Issue | Label | Descripción |
|---|-------|-------|-------------|
| 14 | Sistema de notificaciones (push/email/SMS) | `must-have` `backend` | Enviar alerta cuando humedad, luz o estado visual estén fuera de rango. |
| 15 | Historial de lecturas | `must-have` `backend` | Guardar todas las lecturas con timestamp. Mostrar gráfica histórica en dashboard. |
| 16 | Soporte multi-planta | `nice-to-have` `backend` | Identificar cada sensor con un ID de planta. Monitorear N plantas simultáneamente. |
| 17 | Modo deep sleep en ESP32 (ahorro energía) | `nice-to-have` `hardware` | ESP32 duerme entre lecturas para reducir consumo a ~10µA. |
| 18 | App móvil o PWA | `nice-to-have` `frontend` | Versión mobile del dashboard. |

---

## RELEASE 4 — Entrega final (Semanas 7–8)

| # | Issue | Label | Descripción |
|---|-------|-------|-------------|
| 19 | Feature freeze + corrección de bugs | `must-have` | No nuevas features. Solo estabilización. |
| 20 | Preparar demo funcional | `must-have` | Script del demo de 5 min. Checklist de hardware. |
| 21 | Documentación final (README + comentarios código) | `must-have` `docs` | README actualizado, código comentado, instrucciones de instalación. |
| 22 | Retrospectiva final | `must-have` `docs` | Qué salió bien, qué cambiaríamos, lecciones aprendidas. |
