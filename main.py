"""
PlantSense — Backend FastAPI
GreenLoop Dev · Universidad de La Sabana 2026-1

Endpoints:
  POST /api/lectura          → recibe sensores + imagen (multipart)
  POST /api/lectura/sensores → recibe solo sensores (JSON)
  GET  /api/lecturas         → últimas lecturas
  GET  /api/estado           → estado actual de la planta
  GET  /health               → health check para Render

Deploy en Render:
  Start command: uvicorn main:app --host 0.0.0.0 --port $PORT
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import cv2
import numpy as np
import json
import sqlite3
from datetime import datetime
import os

app = FastAPI(title="PlantSense API", version="1.0.0")

# CORS — permite que el frontend (cualquier origen) consuma la API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── BASE DE DATOS (SQLite — persiste en Render con disco) ────────────────────
DB_PATH = "plantsense.db"

def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lecturas (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp      TEXT    NOT NULL,
            humedad_pct    INTEGER,
            humedad_raw    INTEGER,
            lux            REAL,
            alerta_humedad TEXT,
            alerta_luz     TEXT,
            estado_visual  TEXT,
            color_verde    REAL,
            color_amarillo REAL,
            color_cafe     REAL,
            tiene_imagen   INTEGER DEFAULT 0
        )
    """)
    con.commit()
    con.close()

init_db()

# ─── ANÁLISIS DE IMAGEN CON OPENCV ────────────────────────────────────────────

def clasificar_planta_por_color(imagen_bytes: bytes) -> dict:
    """
    Clasificación MVP por distribución de color HSV.
    
    Retorna:
      estado_visual: "sana" | "amarilla" | "cafe" | "sin_datos"
      porcentajes de píxeles en cada rango de color
    """
    # Decodificar imagen JPEG
    nparr = np.frombuffer(imagen_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img is None:
        return {"estado_visual": "sin_datos", "verde": 0, "amarillo": 0, "cafe": 0}
    
    # Convertir a HSV para mejor segmentación de color
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    total_pixeles = img.shape[0] * img.shape[1]
    
    # Rangos HSV (H: 0-179 en OpenCV, S: 0-255, V: 0-255)
    
    # Verde (planta sana)
    mask_verde1 = cv2.inRange(hsv, (35, 40, 40), (85, 255, 255))
    # Verde oscuro
    mask_verde2 = cv2.inRange(hsv, (85, 20, 20), (100, 255, 200))
    mask_verde = cv2.bitwise_or(mask_verde1, mask_verde2)
    
    # Amarillo (falta de agua / exceso de luz)
    mask_amarillo = cv2.inRange(hsv, (20, 60, 100), (35, 255, 255))
    
    # Café/marrón (planta muy enferma o tierra)
    mask_cafe = cv2.inRange(hsv, (8, 40, 30), (20, 200, 180))
    
    pct_verde    = round(cv2.countNonZero(mask_verde)    / total_pixeles * 100, 1)
    pct_amarillo = round(cv2.countNonZero(mask_amarillo) / total_pixeles * 100, 1)
    pct_cafe     = round(cv2.countNonZero(mask_cafe)     / total_pixeles * 100, 1)
    
    # Lógica de clasificación
    if pct_verde >= 25:
        estado = "sana"
    elif pct_amarillo >= 15:
        estado = "amarilla"  # posible falta de agua o exceso de luz
    elif pct_cafe >= 20:
        estado = "cafe"      # planta muy deteriorada
    else:
        estado = "indeterminado"  # poca planta visible o imagen oscura
    
    return {
        "estado_visual": estado,
        "verde":    pct_verde,
        "amarillo": pct_amarillo,
        "cafe":     pct_cafe,
    }

def generar_recomendaciones(datos: dict) -> list[str]:
    """Genera mensajes de alerta legibles para el usuario."""
    recs = []
    
    if datos.get("alerta_humedad") == "seco":
        recs.append("💧 La planta necesita agua — suelo muy seco")
    elif datos.get("alerta_humedad") == "exceso_agua":
        recs.append("🚿 Exceso de agua — riesgo de pudrición de raíces")
    
    if datos.get("alerta_luz") == "poca_luz":
        recs.append("☀️ Poca luz — mover a lugar más iluminado")
    elif datos.get("alerta_luz") == "exceso_luz":
        recs.append("🌤️ Demasiada luz directa — considerar sombra parcial")
    
    estado_visual = datos.get("estado_visual", "")
    if estado_visual == "amarilla":
        recs.append("🟡 Hojas amarillas detectadas — revisar riego o nutrientes")
    elif estado_visual == "cafe":
        recs.append("🟫 Hojas marrones detectadas — posible enfermedad o quemadura")
    
    if not recs:
        recs.append("✅ Todo bien — planta en buen estado")
    
    return recs

# ─── ENDPOINTS ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Health check para que Render sepa que el servicio está vivo."""
    return {"status": "ok", "service": "PlantSense API"}


@app.post("/api/lectura")
async def recibir_lectura_completa(
    datos: str = Form(...),        # JSON string con sensores
    imagen: UploadFile = File(...) # JPEG del ESP32-CAM
):
    """
    Recibe sensores + imagen del ESP32-CAM.
    Analiza la imagen con OpenCV y guarda todo en la DB.
    """
    try:
        sensor_data = json.loads(datos)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON de sensores inválido")
    
    # Leer imagen
    img_bytes = await imagen.read()
    
    # Analizar imagen
    analisis = clasificar_planta_por_color(img_bytes)
    
    # Combinar datos
    datos_completos = {**sensor_data, **analisis}
    recomendaciones = generar_recomendaciones(datos_completos)
    
    # Guardar en DB
    timestamp = datetime.utcnow().isoformat()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        INSERT INTO lecturas 
        (timestamp, humedad_pct, humedad_raw, lux, alerta_humedad, alerta_luz,
         estado_visual, color_verde, color_amarillo, color_cafe, tiene_imagen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (
        timestamp,
        sensor_data.get("humedad_pct"),
        sensor_data.get("humedad_raw"),
        sensor_data.get("lux"),
        sensor_data.get("alerta_humedad"),
        sensor_data.get("alerta_luz"),
        analisis["estado_visual"],
        analisis["verde"],
        analisis["amarillo"],
        analisis["cafe"],
    ))
    con.commit()
    con.close()
    
    return {
        "ok": True,
        "timestamp": timestamp,
        "sensores": sensor_data,
        "vision": analisis,
        "recomendaciones": recomendaciones,
    }


@app.post("/api/lectura/sensores")
async def recibir_solo_sensores(payload: dict):
    """
    Recibe solo datos de sensores (sin imagen).
    Útil como fallback cuando la cámara falla.
    """
    recomendaciones = generar_recomendaciones(payload)
    
    timestamp = datetime.utcnow().isoformat()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        INSERT INTO lecturas 
        (timestamp, humedad_pct, humedad_raw, lux, alerta_humedad, alerta_luz, tiene_imagen)
        VALUES (?, ?, ?, ?, ?, ?, 0)
    """, (
        timestamp,
        payload.get("humedad_pct"),
        payload.get("humedad_raw"),
        payload.get("lux"),
        payload.get("alerta_humedad"),
        payload.get("alerta_luz"),
    ))
    con.commit()
    con.close()
    
    return {
        "ok": True,
        "timestamp": timestamp,
        "recomendaciones": recomendaciones,
    }


@app.get("/api/lecturas")
def obtener_lecturas(limite: int = 20):
    """Retorna las últimas N lecturas para el dashboard."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("""
        SELECT * FROM lecturas 
        ORDER BY id DESC 
        LIMIT ?
    """, (limite,))
    rows = [dict(row) for row in cur.fetchall()]
    con.close()
    return {"lecturas": rows, "total": len(rows)}


@app.get("/api/estado")
def obtener_estado_actual():
    """
    Retorna el estado más reciente de la planta.
    Endpoint principal para el dashboard.
    """
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT * FROM lecturas ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    con.close()
    
    if not row:
        return {"estado": "sin_datos", "mensaje": "No hay lecturas aún"}
    
    datos = dict(row)
    recomendaciones = generar_recomendaciones(datos)
    
    # Estado general combinado
    hay_alerta = (
        datos.get("alerta_humedad") != "ok" or
        datos.get("alerta_luz") != "ok" or
        datos.get("estado_visual") in ("amarilla", "cafe")
    )
    
    return {
        "estado_general": "alerta" if hay_alerta else "bien",
        "ultima_lectura": datos["timestamp"],
        "humedad_pct":    datos.get("humedad_pct"),
        "lux":            datos.get("lux"),
        "estado_visual":  datos.get("estado_visual"),
        "alerta_humedad": datos.get("alerta_humedad"),
        "alerta_luz":     datos.get("alerta_luz"),
        "recomendaciones": recomendaciones,
    }
