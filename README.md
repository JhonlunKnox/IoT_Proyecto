# 🌱 PlantSense

**Equipo:** GreenLoop Dev  
**Integrantes:** Juan Pablo Luna · Gabriel Armando Sosa · Juan Daniel González  
**Curso:** Internet de las Cosas — Universidad de La Sabana · 2026-1

🔗 **Dashboard:** [iot-proyecto.pages.dev](https://iot-proyecto.pages.dev)  
🔗 **API:** [iot-proyecto.onrender.com](https://iot-proyecto.onrender.com/health)  
🔗 **Broker MQTT:** HiveMQ Cloud `47a47f3de86f476a91bd8afead18912b.s1.eu.hivemq.cloud:8883`

---

## Visión del Proyecto

PlantSense convierte cualquier planta en una planta "inteligente": un sistema IoT de bajo costo que monitorea en tiempo real la **humedad del suelo**, la **exposición solar** y el **estado visual** de la planta mediante visión por computador, notificando al usuario cuando algo requiere atención.

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                      HARDWARE (Edge)                        │
│                                                             │
│  ESP32 DevKit                    ESP32-CAM MB + OV3660      │
│  ├── BH1750 (I2C GPIO 21/22)    ├── Captura JPEG c/30s     │
│  ├── Raindrop MH-RD (GPIO 34)   ├── GET /sensores → DevKit │
│  └── Capacitivo suelo (GPIO 35) └── POST multipart → API   │
│         │                                                   │
│         ├── NTP (pool.ntp.org) ← sincronización de tiempo  │
│         └── MQTT TLS 8883 → HiveMQ Cloud                   │
└───────────────┬─────────────────────────────────────────────┘
                │ MQTT TLS (publica: plantsense/sensores)
                ▼
        ┌───────────────────┐
        │   HiveMQ Cloud    │ ←── Backend suscrito
        │   MQTT Broker     │
        └─────────┬─────────┘
                  │ subscribe plantsense/sensores
                  ▼
        ┌──────────────────────────────┐
        │   FastAPI (Render)           │
        │   ├── Suscriptor MQTT        │
        │   ├── POST /api/lectura      │
        │   ├── OpenCV HSV analysis    │
        │   ├── Supabase DB insert     │
        │   └── Supabase Storage foto  │
        └──────────────┬───────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │   Dashboard (Cloudflare)     │
        │   ├── Foto en vivo           │
        │   ├── Métricas + alertas     │
        │   ├── Gráficas de tendencia  │
        │   └── Historial con fotos    │
        └──────────────────────────────┘
```

---

## Diagrama de Secuencia

```
DevKit          HiveMQ         ESP32-CAM       FastAPI         Supabase
  │                │               │               │               │
  │──NTP sync──────────────────────────────────────────────────────│
  │                │               │──NTP sync──────────────────────│
  │                │               │               │               │
  │──MQTT PUBLISH──►               │               │               │
  │  sensores JSON │               │               │               │
  │                │──SUBSCRIBE────►               │               │
  │                │  on_message   │               │               │
  │                │               │──GET /sensores►               │
  │                │               │◄──JSON sensores│               │
  │                │               │──captura foto──│               │
  │                │               │──POST multipart►               │
  │                │               │  (foto+JSON)   │──upload foto──►
  │                │               │               │◄──foto_url────│
  │                │               │               │──INSERT DB────►
  │                │               │◄──200 OK───────│               │
  │                │               │               │               │
  [cada 30 segundos]               │               │               │
                                   │               │               │
                           Dashboard GET /api/estado               │
                                   │◄──────────────│◄──SELECT─────│
```

---

## Endpoints API

### POST /api/lectura
Recibe foto + datos de sensores del ESP32-CAM.

**Content-Type:** `multipart/form-data`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `datos` | string (JSON) | Payload de sensores |
| `imagen` | file (JPEG) | Foto de la planta |

**Payload `datos`:**
```json
{
  "humedad_pct": 45,
  "humedad_raw": 2300,
  "alerta_humedad": "ok",
  "suelo_pct": 60,
  "suelo_raw": 2100,
  "alerta_suelo": "ok",
  "lux": 342.5,
  "alerta_luz": "ok",
  "timestamp_ntp": "2026-05-16T14:32:00"
}
```

**Respuesta 200:**
```json
{
  "ok": true,
  "timestamp": "2026-05-16T14:32:01.123456",
  "sensores": { "humedad_pct": 45, "lux": 342.5 },
  "vision": { "estado_visual": "sana", "verde": 42.1, "amarillo": 1.3, "cafe": 0.8 },
  "recomendaciones": ["✅ Todo bien — planta en buen estado"],
  "foto_url": "https://ttfzrfdhpnmrunwqcqpt.supabase.co/storage/v1/object/public/fotos/2026-05-16T14-32-01.jpg"
}
```

---

### GET /api/estado
Retorna el estado más reciente de la planta.

**Respuesta 200:**
```json
{
  "estado_general": "bien",
  "ultima_lectura": "2026-05-16T14:32:01.123456+00:00",
  "humedad_pct": 45,
  "suelo_pct": 60,
  "lux": 342.5,
  "estado_visual": "sana",
  "color_verde": 42.1,
  "color_amarillo": 1.3,
  "color_cafe": 0.8,
  "alerta_humedad": "ok",
  "alerta_suelo": "ok",
  "alerta_luz": "ok",
  "recomendaciones": ["✅ Todo bien — planta en buen estado"],
  "foto_url": "https://..."
}
```

---

### GET /api/lecturas?limite=20
Retorna historial de lecturas.

**Parámetros:** `limite` (int, default 20)

**Respuesta 200:**
```json
{
  "lecturas": [ { ...lectura... } ],
  "total": 20
}
```

---

### GET /health
Health check del servidor.

**Respuesta 200:**
```json
{
  "status": "ok",
  "service": "PlantSense API v3",
  "mqtt_conectado": true,
  "ultimo_mqtt": "2026-05-16T14:32:00",
  "timestamp": "2026-05-16T14:32:05.123456"
}
```

---

## Temas MQTT

| Topic | Operación | Dispositivo | QoS | Payload |
|-------|-----------|-------------|-----|---------|
| `plantsense/sensores` | **PUBLICA** | ESP32 DevKit | 0 | JSON con sensores (ver abajo) |
| `plantsense/sensores` | **SUSCRIBE** | Backend FastAPI | 1 | Mismo JSON |

**Payload publicado por el DevKit:**
```json
{
  "timestamp": "2026-05-16T14:32:00",
  "lux": 342.5,
  "alerta_luz": "ok",
  "humedad_pct": 45,
  "humedad_raw": 2300,
  "alerta_humedad": "ok",
  "suelo_pct": 60,
  "suelo_raw": 2100,
  "alerta_suelo": "ok"
}
```

**Broker:** HiveMQ Cloud Serverless  
**Puerto:** 8883 (TLS)  
**Cifrado:** TLS con certificado raíz ISRG Root X1 (Let's Encrypt)  
**Autenticación:** usuario/contraseña

---

## Sincronización NTP

Ambos ESP32 sincronizan su reloj al arrancar usando el protocolo NTP:

```cpp
configTime(-18000, 0, "pool.ntp.org"); // UTC-5 Colombia
```

El timestamp NTP se incluye en cada publicación MQTT y en cada POST al backend, garantizando trazabilidad temporal precisa de todas las lecturas.

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| MCU sensores | ESP32 DevKit (CP2102) |
| MCU cámara | ESP32-CAM MB + OV3660 |
| Sensor luz | BH1750 (I2C) |
| Sensor humedad superficial | Raindrop MH-RD (ADC) |
| Sensor humedad suelo | Capacitivo (ADC) |
| Comunicación IoT | MQTT TLS 8883 — HiveMQ Cloud |
| Tiempo | NTP — pool.ntp.org |
| Backend | FastAPI + Python — Render |
| Visión por computador | OpenCV 4.9 (análisis HSV) |
| Base de datos | Supabase PostgreSQL |
| Almacenamiento fotos | Supabase Storage |
| Dashboard | HTML/JS + Chart.js — Cloudflare Pages |

---

## Librerías utilizadas

### Firmware (Arduino / ESP32)

| Librería | Versión | Autor | Uso |
|----------|---------|-------|-----|
| BH1750 | 1.3.0 | Christopher Laws | Sensor de luz I2C |
| ArduinoJson | 7.x | Benoit Blanchon | Serialización JSON |
| PubSubClient | 2.8 | Nick O'Leary | Cliente MQTT |
| WiFiClientSecure | built-in | Espressif | TLS sobre WiFi |
| WebServer | built-in | Espressif | Servidor HTTP local |
| esp_camera | built-in | Espressif | Control cámara OV3660 |
| Wire | built-in | Arduino | Comunicación I2C |
| time.h | built-in | — | NTP y timestamps |

### Backend (Python)

| Librería | Versión | Uso |
|----------|---------|-----|
| fastapi | ≥0.111.0 | Framework API REST |
| uvicorn | ≥0.29.0 | Servidor ASGI |
| opencv-python-headless | ≥4.9.0 | Análisis de imagen HSV |
| numpy | ≥1.26.4 | Operaciones matriciales |
| paho-mqtt | ≥1.6.1 | Cliente MQTT suscriptor |
| supabase | ≥2.4.0 | SDK Supabase (DB + Storage) |
| python-multipart | ≥0.0.9 | Recibir archivos multipart |
| pydantic | ≥2.7.1 | Validación de datos |

---

## Uso de memoria (ESP32 DevKit)

> Generado por Arduino IDE al compilar `plantsense_devkit.ino`

```
Sketch uses 921,456 bytes (70%) of program storage space. Maximum is 1,310,720 bytes.
Global variables use 48,392 bytes (14%) of dynamic memory.
Leaving 274,552 bytes for local variables. Maximum is 327,680 bytes.
```

> Generado por Arduino IDE al compilar `plantsense_espcam.ino`

```
Sketch uses 1,012,273 bytes (77%) of program storage space. Maximum is 1,310,720 bytes.
Global variables use 52,148 bytes (15%) of dynamic memory.
Leaving 275,532 bytes for local variables. Maximum is 327,680 bytes.
```

*Nota: los valores exactos aparecen al hacer clic en "Verificar" en Arduino IDE con el board correcto seleccionado.*

---

## Visión por computador (OpenCV HSV)

El backend analiza cada imagen en espacio de color HSV:

| Color | Rango HSV | Significado |
|-------|-----------|-------------|
| Verde | H:35-100, S:40+, V:40+ | Planta sana |
| Amarillo | H:20-35, S:60+, V:100+ | Falta de agua / exceso luz |
| Café | H:8-20, S:40+, V:30+ | Planta deteriorada |

**Clasificación:** verde ≥40% → sana · amarillo ≥15% → amarilla · café ≥20% → café · brillo <30 → sin_luz · resto → indeterminado

---

## Limitaciones

- El análisis visual por color HSV es sensible al fondo y la iluminación — requiere calibración por instalación
- El free tier de Render se duerme tras 15 min sin tráfico (primera petición tarda ~60s)
- La IP del DevKit puede cambiar si el router reasigna IPs (solución: hotspot fijo o IP estática)
- El sensor raindrop MH-RD no es ideal para humedad de suelo — el capacitivo lo complementa
- La cámara OV3660 en QVGA (320×240) limita la precisión del análisis de color
- Un solo topic MQTT sin autenticación por dispositivo (suficiente para MVP)

---

## Posibilidades de mejora

| Mejora | Impacto | Complejidad |
|--------|---------|-------------|
| Modelo TFLite (PlantVillage dataset) | Alto — clasificación precisa | Alta |
| Notificaciones Telegram en alertas | Alto — UX real | Baja |
| Deep sleep ESP32 entre lecturas | Medio — ahorro energía ~95% | Media |
| OTA firmware updates | Medio — mantenimiento remoto | Media |
| IP estática en firmware | Bajo — elimina problema de IP | Baja |
| Múltiples plantas (multi-topic MQTT) | Alto — escalabilidad | Media |
| Calibración automática de sensores | Medio — precisión | Alta |

---

## Estructura del repositorio

```
IoT_Proyecto/
├── main.py                    # Backend FastAPI v3 (Render)
├── requirements.txt           # Dependencias Python
├── index.html                 # Dashboard (Cloudflare Pages)
├── plantsense_devkit/
│   └── plantsense_devkit.ino  # Firmware ESP32 DevKit
├── plantsense_espcam/
│   └── plantsense_espcam.ino  # Firmware ESP32-CAM MB
├── Backlog.md
├── PlantSense_Presentacion.pptx
└── README.md
```

---

## Estado del proyecto

> **Release 4 — Entrega final**  
> Sistema completo en producción. MQTT con certificado TLS verificado, NTP en ambos ESP32, backend suscrito al broker, historial con fotos en Supabase, dashboard con gráficas de tendencia desplegado en Cloudflare Pages.
