"""
PlantSense — Backend FastAPI v3
- Suscrito a MQTT (HiveMQ Cloud) para recibir datos de sensores
- Recibe imagen del ESP32-CAM por HTTP POST multipart
- Analiza imagen con OpenCV (HSV)
- Almacena en Supabase (DB + Storage fotos)

Endpoints:
  POST /api/lectura       → imagen + sensores (multipart)
  GET  /api/estado        → lectura más reciente
  GET  /api/lecturas      → historial
  GET  /health            → healthcheck
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import cv2
import numpy as np
import json
import threading
import ssl
import paho.mqtt.client as mqtt_client
from datetime import datetime
from supabase import create_client, Client

# ─── SUPABASE ─────────────────────────────────────────────────────────────────
SUPABASE_URL = "*******"
SUPABASE_KEY = "************************"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── MQTT CONFIG ──────────────────────────────────────────────────────────────
MQTT_HOST   = "********************"
MQTT_PORT   = ****
MQTT_USER   = "******"
MQTT_PASS   = "************"
MQTT_TOPIC  = "plantsense/sensores"

# Último estado recibido por MQTT (en memoria)
ultimo_mqtt: dict = {}

# ─── MQTT CLIENT ──────────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Conectado al broker — suscrito a {MQTT_TOPIC}")
        client.subscribe(MQTT_TOPIC, qos=1)
    else:
        print(f"[MQTT] Error de conexión rc={rc}")

def on_message(client, userdata, msg):
    global ultimo_mqtt
    try:
        payload = json.loads(msg.payload.decode())
        ultimo_mqtt = payload
        print(f"[MQTT] Recibido en memoria: {payload}")
        # Solo actualiza estado en memoria — la DB se actualiza con el POST /api/lectura (con foto)
    except Exception as e:
        print(f"[MQTT] Error procesando mensaje: {e}")

def iniciar_mqtt():
    client = mqtt_client.Client(client_id="plantsense-backend", protocol=mqtt_client.MQTTv311)
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(tls_version=ssl.PROTOCOL_TLS)
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        client.loop_forever()
    except Exception as e:
        print(f"[MQTT] No se pudo conectar: {e}")

# ─── LIFESPAN (arranca MQTT al iniciar FastAPI) ───────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    thread = threading.Thread(target=iniciar_mqtt, daemon=True)
    thread.start()
    print("[OK] Hilo MQTT iniciado")
    yield

app = FastAPI(title="PlantSense API v3", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── OPENCV ───────────────────────────────────────────────────────────────────
def clasificar_planta(imagen_bytes: bytes) -> dict:
    nparr = np.frombuffer(imagen_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return {"estado_visual": "sin_datos", "verde": 0, "amarillo": 0, "cafe": 0}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if gray.mean() < 30:
        return {"estado_visual": "sin_luz", "verde": 0, "amarillo": 0, "cafe": 0}

    hsv   = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    total = img.shape[0] * img.shape[1]

    # Rangos calibrados OV3660 QVGA:
    # S >= 60 para evitar grises, blancos y fondos sin color real
    # Techo blanco/gris tiene S < 30, planta verde tiene S > 80
    mask_verde1   = cv2.inRange(hsv, (35, 60, 30), (85, 255, 255))
    mask_verde2   = cv2.inRange(hsv, (85, 50, 30), (100, 255, 180))
    mask_verde    = cv2.bitwise_or(mask_verde1, mask_verde2)
    mask_amarillo = cv2.inRange(hsv, (20, 60, 80), (35, 255, 255))
    mask_cafe     = cv2.inRange(hsv, (8, 50, 30), (20, 200, 180))

    pct_verde    = round(cv2.countNonZero(mask_verde)    / total * 100, 1)
    pct_amarillo = round(cv2.countNonZero(mask_amarillo) / total * 100, 1)
    pct_cafe     = round(cv2.countNonZero(mask_cafe)     / total * 100, 1)

    if pct_verde >= 15:      estado = "sana"
    elif pct_amarillo >= 12: estado = "amarilla"
    elif pct_cafe >= 15:     estado = "cafe"
    else:                    estado = "indeterminado"

    return {"estado_visual": estado, "verde": pct_verde, "amarillo": pct_amarillo, "cafe": pct_cafe}

def generar_recomendaciones(datos: dict) -> list:
    recs = []
    if datos.get("alerta_humedad") == "seco":        recs.append("💧 Suelo superficial seco — revisar riego")
    if datos.get("alerta_humedad") == "exceso_agua": recs.append("🚿 Exceso de agua superficial")
    if datos.get("alerta_suelo") == "seco":          recs.append("🌱 Tierra seca — regar la planta")
    if datos.get("alerta_suelo") == "humedo":        recs.append("✅ Tierra bien hidratada")
    if datos.get("alerta_luz") == "poca_luz":        recs.append("☀️ Poca luz — mover a lugar más iluminado")
    if datos.get("alerta_luz") == "exceso_luz":      recs.append("🌤️ Demasiada luz directa")
    estado = datos.get("estado_visual", "")
    if estado == "amarilla": recs.append("🟡 Hojas amarillas detectadas")
    if estado == "cafe":     recs.append("🟫 Hojas marrones detectadas")
    if not recs:             recs.append("✅ Todo bien — planta en buen estado")
    return recs

# ─── ENDPOINTS ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "PlantSense API v3",
        "mqtt_conectado": True,
        "ultimo_mqtt": ultimo_mqtt.get("timestamp", "sin datos"),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/lectura")
async def recibir_lectura(
    datos: str = Form(...),
    imagen: UploadFile = File(...)
):
    try:
        sensor_data = json.loads(datos)
    except:
        raise HTTPException(status_code=400, detail="JSON inválido")

    img_bytes = await imagen.read()
    analisis  = clasificar_planta(img_bytes)
    datos_completos = {**sensor_data, **analisis}
    recomendaciones = generar_recomendaciones(datos_completos)

    # Subir foto a Supabase Storage
    timestamp   = datetime.utcnow().isoformat()
    foto_nombre = f"{timestamp.replace(':', '-')}.jpg"
    foto_url    = None
    try:
        supabase.storage.from_("fotos").upload(
            foto_nombre, img_bytes, {"content-type": "image/jpeg"}
        )
        foto_url = f"{SUPABASE_URL}/storage/v1/object/public/fotos/{foto_nombre}"
    except Exception as e:
        print(f"[ERROR] Storage: {e}")

    # Guardar en DB
    try:
        supabase.table("lecturas").insert({
            "humedad_pct":    sensor_data.get("humedad_pct"),
            "humedad_raw":    sensor_data.get("humedad_raw"),
            "suelo_pct":      sensor_data.get("suelo_pct"),
            "suelo_raw":      sensor_data.get("suelo_raw"),
            "lux":            sensor_data.get("lux"),
            "alerta_humedad": sensor_data.get("alerta_humedad"),
            "alerta_suelo":   sensor_data.get("alerta_suelo"),
            "alerta_luz":     sensor_data.get("alerta_luz"),
            "estado_visual":  analisis["estado_visual"],
            "color_verde":    analisis["verde"],
            "color_amarillo": analisis["amarillo"],
            "color_cafe":     analisis["cafe"],
            "recomendaciones": recomendaciones,
            "foto_url":       foto_url,
        }).execute()
    except Exception as e:
        print(f"[ERROR] DB: {e}")

    return {
        "ok": True,
        "timestamp": timestamp,
        "sensores": sensor_data,
        "vision": analisis,
        "recomendaciones": recomendaciones,
        "foto_url": foto_url,
    }

@app.get("/api/estado")
def obtener_estado():
    try:
        res = supabase.table("lecturas") \
            .select("*").order("created_at", desc=True).limit(1).execute()
        if not res.data:
            return {"estado": "sin_datos"}
        datos = res.data[0]
        recomendaciones = generar_recomendaciones(datos)
        hay_alerta = (
            datos.get("alerta_humedad") != "ok" or
            datos.get("alerta_luz") != "ok" or
            datos.get("estado_visual") in ("amarilla", "cafe")
        )
        return {
            "estado_general":  "alerta" if hay_alerta else "bien",
            "ultima_lectura":  datos.get("created_at"),
            "humedad_pct":     datos.get("humedad_pct"),
            "suelo_pct":       datos.get("suelo_pct"),
            "lux":             datos.get("lux"),
            "estado_visual":   datos.get("estado_visual"),
            "color_verde":     datos.get("color_verde"),
            "color_amarillo":  datos.get("color_amarillo"),
            "color_cafe":      datos.get("color_cafe"),
            "alerta_humedad":  datos.get("alerta_humedad"),
            "alerta_suelo":    datos.get("alerta_suelo"),
            "alerta_luz":      datos.get("alerta_luz"),
            "recomendaciones": recomendaciones,
            "foto_url":        datos.get("foto_url"),
        }
    except Exception as e:
        return {"estado": "error", "detalle": str(e)}

@app.get("/api/lecturas")
def obtener_lecturas(limite: int = 20):
    try:
        res = supabase.table("lecturas") \
            .select("*").order("created_at", desc=True).limit(limite).execute()
        return {"lecturas": res.data, "total": len(res.data)}
    except Exception as e:
        return {"lecturas": [], "error": str(e)}
