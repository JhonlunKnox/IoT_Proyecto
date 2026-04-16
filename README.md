# 🌱 PlantSense

**Equipo:** GreenLoop Dev  
**Integrantes:** Juan Pablo Luna · Gabriel Armando Sosa · Juan Daniel González  
**Curso:** Portafolio de Programación — Universidad de La Sabana · 2026-1

---

## Visión del Proyecto

### ¿Qué problema resuelve?

Millones de plantas mueren por descuido — riego excesivo, falta de luz, o simplemente porque el dueño no sabe cuándo actuar. PlantSense convierte cualquier planta en una planta "inteligente": un sistema embebido de bajo costo que monitorea en tiempo real la **humedad del suelo**, la **exposición solar** y el **estado visual** de la planta, y notifica al usuario si algo requiere atención.

### ¿Quiénes son los usuarios?

| Perfil | Descripción |
|--------|-------------|
| **Hogares** | Personas con plantas en interiores/exteriores que viajan frecuentemente o tienen poco tiempo |
| **Viveros pequeños** | Negocios que necesitan monitorear múltiples plantas sin personal dedicado |
| **Estudiantes/makers** | Comunidad interesada en IoT y automatización doméstica |

---

## Arquitectura y Restricciones

### Diagrama de bloques

```
┌─────────────────────────────────────────────────────────────────┐
│                        HARDWARE (Edge)                          │
│                                                                 │
│  [Sensor Humedad]──┐                                            │
│  [Sensor Luz LDR]──┼──► [Microcontrolador ESP32] ──► WiFi ──► │
│  [Cámara OV2640]───┘          │                                │
│                               ▼                                │
│                      [Lógica de alertas]                        │
└───────────────────────────────┬─────────────────────────────────┘
                                │ MQTT / HTTP
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        BACKEND (Cloud)                          │
│                                                                 │
│  [API REST / MQTT Broker] ──► [Base de datos] ──► [IA/CV Model]│
│                                                                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SOFTWARE (Ya existe)                        │
│                                                                 │
│  [Dashboard Web / App] ──► Visualización + Notificaciones       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Microcontrolador | ESP32 (WiFi integrado) |
| Sensor humedad | Sensor capacitivo de humedad de suelo (ej. v1.2) |
| Sensor luz | LDR o módulo BH1750 |
| Cámara | OV2640 (módulo ESP32-CAM) |
| Comunicación | MQTT o HTTP/REST |
| Backend | (definido por el software existente del equipo) |
| IA / Visión | Modelo de clasificación de estado visual de planta (TensorFlow Lite o API externa) |
| Frontend | Software existente del equipo |

### Restricciones de recursos (hardware seleccionado: ESP32)

| Recurso | Límite |
|---------|--------|
| RAM | 520 KB SRAM |
| Flash | 4 MB (típico) |
| Consumo energía | ~240 mA activo, ~10 µA deep sleep |
| Voltaje operación | 3.3 V |
| Conectividad | WiFi 802.11 b/g/n, Bluetooth 4.2 |
| Almacenamiento local | No — los datos se envían al backend en tiempo real |

**Restricción clave:** El análisis de imagen con IA **no puede correr en el ESP32** — el modelo debe estar en el backend o en una API externa. El ESP32 solo captura y transmite la imagen.

### Presupuesto estimado (prototipo)

| Componente | Precio estimado COP |
|-----------|-------------------|
| ESP32-CAM (incluye cámara OV2640) | $25.000 |
| Sensor humedad capacitivo | $8.000 |
| Módulo BH1750 (sensor luz) | $7.000 |
| Cables, protoboard, resistencias | $10.000 |
| **Total hardware** | **~$50.000 COP** |
| Hosting backend (si aplica) | $0 (tier gratuito) |

---

## Reporte del Spike

### Spike: Viabilidad de captura de imagen + clasificación de estado de planta

**Objetivo:** Determinar si el ESP32-CAM puede capturar imágenes utilizables y si existe un modelo/API capaz de clasificar el estado de salud de una planta (sana, con falta de agua, con exceso de luz, etc.) sin correr en el microcontrolador.

**Resultado:**

El ESP32-CAM es capaz de capturar imágenes JPEG y transmitirlas vía HTTP o MQTT. La resolución útil mínima es QVGA (320×240). La restricción principal es que el modelo de clasificación **debe ejecutarse fuera del ESP32**.

Se identificaron tres alternativas viables para la clasificación visual:

1. **TensorFlow Lite (TFLite)** — modelo liviano corriendo en el servidor/backend. Requiere entrenamiento con dataset de plantas (disponible en Kaggle: *PlantVillage*).
2. **API externa (Google Vision / Hugging Face)** — clasificación en la nube sin necesidad de entrenar. Más rápido de implementar, dependencia externa.
3. **Modelo propio simple (MVP)** — clasificar solo por color promedio de la imagen (planta amarilla/café = problema). Implementable en Python con OpenCV en pocas horas.

**Decisión para el MVP:** Se usará la opción 3 (clasificación por color con OpenCV) para el Release 1-2, dejando la integración de un modelo TFLite o API como mejora opcional (nice-to-have).

**Riesgo residual:** La calidad de imagen bajo condiciones de baja luz puede afectar la clasificación. Se mitigará con iluminación controlada en el prototipo.

---

## MVP (Minimum Viable Product)

El MVP entrega la funcionalidad mínima para demostrar el concepto completo de extremo a extremo:

- ✅ Lectura de humedad del suelo en tiempo real
- ✅ Lectura de nivel de luz en tiempo real
- ✅ Captura de imagen de la planta y transmisión al backend
- ✅ Clasificación básica del estado visual (sana / con problemas)
- ✅ Alerta/notificación al usuario cuando algún parámetro está fuera de rango
- ✅ Visualización en el software existente del equipo

---

## Cronograma tentativo

| Release | Semanas | Hito |
|---------|---------|------|
| **Release 1** | 1–2 | Spike resuelto. Hardware conectado. Sensor humedad enviando datos al backend. README + backlog. |
| **Release 2** | 3–4 | Sensor de luz integrado. Cámara transmitiendo imágenes. Clasificación básica por color funcionando. |
| **Release 3** | 5–6 | Sistema de alertas/notificaciones funcionando. Integración completa con el software existente. |
| **Release 4** | 7–8 + Finales | Feature freeze. Estabilización, demo preparado, documentación final. |

---

## Estado del proyecto

> **Release 1 — En progreso**  
> Spike arquitectónico completado. Hardware en adquisición. Backlog inicial definido.
