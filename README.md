# 🌱 PlantSense

**Equipo:** GreenLoop Dev
**Integrantes:** Juan Pablo Luna · Gabriel Armando Sosa · Juan Daniel González y David Daniel Gabriel
**Curso:** Portafolio de Programación — Universidad de La Sabana · 2026-1

🔗 **Dashboard en vivo:** [iot-proyecto.pages.dev](https://iot-proyecto.pages.dev)
🔗 **API:** [iot-proyecto.onrender.com](https://iot-proyecto.onrender.com/health)

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

## Arquitectura real implementada

### Diagrama de bloques

```
┌──────────────────────────────────────────────────────────────────────┐
│                         HARDWARE (Edge)                              │
│                                                                      │
│  ┌─────────────────────────────────┐   ┌────────────────────────┐   │
│  │       ESP32 DevKit              │   │     ESP32-CAM MB       │   │
│  │                                 │   │                        │   │
│  │  [BH1750 I2C]──► GPIO 21/22    │   │  [OV3660] ──► captura  │   │
│  │  [Raindrop AO]──► GPIO 34      │   │  consulta DevKit HTTP  │   │
│  │  [Capacitivo]──► GPIO 35       │   │  POST imagen+sensores  │   │
│  │                                 │   │  al backend cada 30s   │   │
│  │  Publica MQTT cada 30s ────────┼───┼──────────────────────► │   │
│  │  Sirve HTTP /sensores ─────────┼───┘                        │   │
│  └─────────────────────────────────┘                            │   │
└──────────────────────────────────┬───────────────────────────────┘
                                   │ HTTP POST multipart + MQTT TLS
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
        ┌───────────────────┐         ┌──────────────────┐
        │  HiveMQ Cloud     │         │  FastAPI (Render) │
        │  MQTT Broker      │         │                  │
        │  plantsense/      │         │  OpenCV → HSV    │
        │  sensores         │         │  análisis color  │
        └───────────────────┘         │  Supabase DB     │
                                      │  Supabase Storage│
                                      └────────┬─────────┘
                                               │
                                               ▼
                              ┌─────────────────────────────┐
                              │  Dashboard (Cloudflare Pages)│
                              │  Foto en vivo · Historial   │
                              │  Métricas · Alertas         │
                              │  Gráficas de tendencia      │
                              └─────────────────────────────┘
```

### Stack tecnológico implementado

| Capa | Tecnología | Detalle |
|------|-----------|---------|
| MCU sensores | ESP32 DevKit | BH1750 (I2C), Raindrop MH-RD, Sensor capacitivo |
| MCU cámara | ESP32-CAM MB + OV3660 | QVGA JPEG cada 30s |
| Comunicación | MQTT TLS + HTTP REST | HiveMQ Cloud (8883) + HTTP local entre ESPs |
| Backend | FastAPI (Python) | Render free tier, uvicorn |
| Visión por computador | OpenCV 4.9 | Análisis HSV, clasificación por color |
| Base de datos | Supabase PostgreSQL | Historial de lecturas con metadatos |
| Almacenamiento fotos | Supabase Storage | Bucket público `fotos` |
| Dashboard | HTML/CSS/JS vanilla | Cloudflare Pages, polling 30s |
| Broker MQTT | HiveMQ Cloud Serverless | Topic: `plantsense/sensores` |

### Restricciones de recursos (ESP32)

| Recurso | Límite |
|---------|--------|
| RAM | 520 KB SRAM |
| Flash | 4 MB |
| Consumo activo | ~240 mA |
| Voltaje | 3.3 V |
| Conectividad | WiFi 802.11 b/g/n |
| Procesamiento IA | ❌ No posible en edge — corre en backend |

### Presupuesto real del prototipo

| Componente | Precio COP |
|-----------|-----------|
| ESP32-CAM MB + OV3660 | $25.000 |
| ESP32 DevKit | $18.000 |
| Sensor humedad capacitivo | $8.000 |
| Sensor raindrop MH-RD | $5.000 |
| Módulo BH1750 | $7.000 |
| Cables, protoboard | $10.000 |
| **Total hardware** | **~$73.000 COP** |
| Hosting (Render + Cloudflare + HiveMQ + Supabase) | $0 (tiers gratuitos) |

---

## Flujo de datos completo

### Ciclo de 30 segundos

```
1. ESP32 DevKit lee sensores
   ├── BH1750 → lux (I2C GPIO 21/22)
   ├── Raindrop → humedad superficial raw (ADC GPIO 34)
   └── Capacitivo → humedad suelo raw (ADC GPIO 35)

2. DevKit publica JSON por MQTT a HiveMQ Cloud
   └── topic: plantsense/sensores

3. ESP32-CAM consulta GET http://[devkit-ip]/sensores
   └── obtiene JSON con todos los valores

4. ESP32-CAM captura foto JPEG (QVGA, flash breve)

5. ESP32-CAM hace POST multipart a FastAPI en Render
   ├── campo "datos": JSON sensores
   └── campo "imagen": JPEG

6. FastAPI procesa:
   ├── OpenCV → convierte a HSV → mide % verde/amarillo/café
   ├── Clasifica estado visual (sana/amarilla/café/indeterminado)
   ├── Genera recomendaciones textuales
   ├── Sube foto a Supabase Storage → obtiene URL pública
   └── Inserta fila en Supabase DB (sensores + análisis + foto_url)

7. Dashboard (cada 30s):
   ├── GET /api/estado → estado actual + foto más reciente
   └── GET /api/lecturas → historial con fotos
```

---

## Visión por computador (OpenCV)

El backend analiza cada imagen en espacio de color **HSV** para separar colores de forma robusta ante cambios de iluminación:

| Color | Rango HSV | Significado |
|-------|-----------|-------------|
| Verde | H: 35-100, S: 40+, V: 40+ | Planta sana |
| Amarillo | H: 20-35, S: 60+, V: 100+ | Falta de agua / exceso luz |
| Café/marrón | H: 8-20, S: 40+, V: 30+ | Planta deteriorada |

**Lógica de clasificación:**
- `% verde ≥ 40%` → **sana**
- `% amarillo ≥ 15%` → **amarilla** (alerta)
- `% café ≥ 20%` → **café** (crítica)
- `brillo < 30` → **sin_luz** (imagen inutilizable)
- resto → **indeterminado**

**Limitación conocida:** La clasificación por color HSV es sensible al fondo. Para entornos con fondos verdes o iluminación variable, los umbrales deben calibrarse por instalación. Una mejora futura es reemplazar esto con un modelo TFLite entrenado con el dataset PlantVillage (54.000+ imágenes).

---

## Reporte del Spike

### Spike: Viabilidad de captura y clasificación visual en arquitectura distribuida

**Objetivo:** Determinar si el ESP32-CAM puede capturar imágenes utilizables, si dos ESP32 pueden comunicarse de forma confiable por WiFi, y si OpenCV puede clasificar el estado de una planta en tiempo real desde el backend.

**Resultado:** ✅ Viable y funcionando en producción.

El ESP32-CAM captura JPEG en QVGA (320×240) con calidad suficiente para análisis de color. La arquitectura de dos microcontroladores (DevKit para sensores + CAM para imagen) funciona de forma estable — el CAM consulta al DevKit por HTTP y agrega los datos antes de enviar al backend.

**Alternativas evaluadas para visión:**

| Opción | Estado | Decisión |
|--------|--------|----------|
| TensorFlow Lite (PlantVillage) | Evaluada | Roadmap — requiere entrenamiento |
| Google Vision API | Evaluada | Descartada — costo y dependencia externa |
| OpenCV HSV (color) | **Implementada** | MVP — funcional, calibrable |

**Riesgo residual:** Falsos positivos con fondos similares al color de planta. Mitigado con umbral de brillo mínimo y umbral de verde elevado (40%).

---

## MVP — Estado actual

✅ Lectura de humedad superficial en tiempo real (raindrop MH-RD)
✅ Lectura de humedad del suelo en tiempo real (capacitivo)
✅ Lectura de luz en tiempo real (BH1750, lux reales)
✅ Captura de imagen JPEG y transmisión al backend
✅ Clasificación visual por OpenCV (sana / amarilla / café / indeterminado)
✅ Alertas y recomendaciones textuales automáticas
✅ Publicación MQTT a broker en la nube (HiveMQ)
✅ Historial persistente con fotos en Supabase
✅ Dashboard en producción con foto en vivo e historial visual
✅ Gráficas de tendencia de humedad y luz

---

## Roadmap

| Feature | Prioridad | Estado |
|---------|-----------|--------|
| Calibración OpenCV con planta real | Alta | 🔄 En progreso |
| Gráficas de tendencia en dashboard | Alta | 🔄 En progreso |
| Notificaciones Telegram en alertas críticas | Media | 📋 Pendiente |
| Deep sleep ESP32 (ahorro energía) | Media | 📋 Pendiente |
| Modelo TFLite con dataset PlantVillage | Baja | 📋 Pendiente |
| OTA firmware updates | Baja | 📋 Pendiente |

---

## Cronograma

| Release | Semanas | Hito | Estado |
|---------|---------|------|--------|
| **Release 1** | 1–2 | Spike resuelto. Hardware conectado. Sensor humedad enviando datos. README + backlog. | ✅ Completo |
| **Release 2** | 3–4 | BH1750 integrado. Cámara transmitiendo. Clasificación por color funcionando. | ✅ Completo |
| **Release 3** | 5–6 | MQTT, Supabase, historial con fotos, dashboard en producción. | ✅ Completo |
| **Release 4** | 7–8 | Calibración, gráficas, notificaciones, estabilización, demo. | 🔄 En progreso |

---

## Estructura del repositorio

```
IoT_Proyecto/
├── main.py               # Backend FastAPI (Render)
├── requirements.txt      # Dependencias Python
├── index.html            # Dashboard (Cloudflare Pages)
├── plantsense_devkit/    # Firmware ESP32 DevKit (sensores + MQTT)
├── plantsense_espcam/    # Firmware ESP32-CAM (cámara + HTTP)
├── Backlog.md            # Backlog del proyecto
└── README.md
```

---

## Estado del proyecto

> **Release 3 completado — Release 4 en progreso**
> Sistema completo funcionando en producción. MQTT, visión por computador, historial con fotos y dashboard desplegados. En curso: calibración OpenCV, gráficas de tendencia y notificaciones.
