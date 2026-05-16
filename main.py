"""
PlantSense — Backend FastAPI v2
MQTT + Supabase + Fotos + Historial

Endpoints:
  POST /api/lectura     → recibe sensores + imagen (multipart)
  GET  /api/estado      → estado actual
  GET  /api/lecturas    → historial con fotos
  GET  /health          → health check
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import cv2
import numpy as np
import json
import os
from datetime import datetime
from supabase import create_client, Client

app = FastAPI(title="PlantSense API v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── SUPABASE ─────────────────────────────────────────────────────────────────
SUPABASE_URL = "https://ttfzrfdhpnmrunwqcqpt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InR0ZnpyZmRocG5tcnVud3FjcXB0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3ODg4NDgxOCwiZXhwIjoyMDk0NDYwODE4fQ.VxYRtgShmlHqTxMrza3uHVZct6VzqSF5TDjvwmFBkT4"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── OPENCV ───────────────────────────────────────────────────────────────────
def clasificar_planta(imagen_bytes: bytes) -> dict:
    nparr = np.frombuffer(imagen_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return {"estado_visual": "sin_datos", "verde": 0, "amarillo": 0, "cafe": 0}

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    total = img.shape[0] * img.shape[1]

    mask_verde    = cv2.inRange(hsv, (35, 40, 40), (85, 255, 255))
    mask_amarillo = cv2.inRange(hsv, (20, 60, 100), (35, 255, 255))
    mask_cafe     = cv2.inRange(hsv, (8, 40, 30), (20, 200, 180))

    pct_verde    = round(cv2.countNonZero(mask_verde)    / total * 100, 1)
    pct_amarillo = round(cv2.countNonZero(mask_amarillo) / total * 100, 1)
    pct_cafe     = round(cv2.countNonZero(mask_cafe)     / total * 100, 1)

    if pct_verde >= 25:      estado = "sana"
    elif pct_amarillo >= 15: estado = "amarilla"
    elif pct_cafe >= 20:     estado = "cafe"
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
    return {"status": "ok", "service": "PlantSense API v2"}


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

    # Analizar imagen
    analisis = clasificar_planta(img_bytes)

    # Subir foto a Supabase Storage
    timestamp = datetime.utcnow().isoformat()
    foto_nombre = f"{timestamp.replace(':', '-')}.jpg"
    foto_url = None

    try:
        res = supabase.storage.from_("fotos").upload(
            foto_nombre,
            img_bytes,
            {"content-type": "image/jpeg"}
        )
        foto_url = f"{SUPABASE_URL}/storage/v1/object/public/fotos/{foto_nombre}"
    except Exception as e:
        print(f"[ERROR] No se pudo subir foto: {e}")

    # Combinar datos
    datos_completos = {**sensor_data, **analisis}
    recomendaciones = generar_recomendaciones(datos_completos)

    # Guardar en Supabase DB
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
        print(f"[ERROR] Supabase insert: {e}")

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
            .select("*") \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()

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
            .select("*") \
            .order("created_at", desc=True) \
            .limit(limite) \
            .execute()
        return {"lecturas": res.data, "total": len(res.data)}
    except Exception as e:
        return {"lecturas": [], "error": str(e)}
