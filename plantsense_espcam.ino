/*
 * PlantSense — ESP32-CAM (Cliente principal)
 * Cada 30s: consulta sensores al DevKit + toma foto + envía al backend
 *
 * Librerías necesarias:
 *   - ArduinoJson by Benoit Blanchon
 *
 * Board: AI Thinker ESP32-CAM
 */

#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
const char* WIFI_SSID     = "FAMILIA ZULETA 2.4";
const char* WIFI_PASSWORD = "Z36516720Z";

// IP del ESP32 DevKit (la que aparece en su Serial Monitor)
const char* DEVKIT_IP  = "192.168.40.55"; // ← cambia esto

// Backend en Render
const char* BACKEND_URL = "https://iot-proyecto.onrender.com";

// Intervalo de lectura (ms)
const unsigned long INTERVALO_MS = 30000;

// ─── PINES CÁMARA AI-THINKER ──────────────────────────────────────────────────
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22
#define PIN_FLASH          4

// ─── GLOBALES ─────────────────────────────────────────────────────────────────
unsigned long ultimaLectura = 0;

// ─── SETUP ────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(PIN_FLASH, OUTPUT);
  digitalWrite(PIN_FLASH, LOW);

  initCamera();
  conectarWifi();

  Serial.println("[OK] ESP32-CAM listo");
}

// ─── LOOP ─────────────────────────────────────────────────────────────────────
void loop() {
  if (millis() - ultimaLectura >= INTERVALO_MS) {
    ultimaLectura = millis();

    // 1. Pedir sensores al DevKit
    StaticJsonDocument<256> sensores;
    bool sensorOk = pedirSensores(sensores);

    // 2. Capturar foto
    camera_fb_t* fb = capturarImagen();

    // 3. Enviar al backend
    if (fb != NULL) {
      enviarAlBackend(sensores, sensorOk, fb);
      esp_camera_fb_return(fb);
    }

    // Reconectar WiFi si se cayó
    if (WiFi.status() != WL_CONNECTED) conectarWifi();
  }
}

// ─── FUNCIONES ────────────────────────────────────────────────────────────────

void conectarWifi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[WiFi] Conectando");
  int intentos = 0;
  while (WiFi.status() != WL_CONNECTED && intentos < 20) {
    delay(500);
    Serial.print(".");
    intentos++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[OK] WiFi — IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\n[ERROR] WiFi no conectado");
  }
}

void initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM; config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM; config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM; config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM; config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = FRAMESIZE_QVGA;
  config.jpeg_quality = 12;
  config.fb_count     = 1;

  if (esp_camera_init(&config) == ESP_OK) {
    Serial.println("[OK] Cámara lista");
  } else {
    Serial.println("[ERROR] Cámara no inicializada");
  }
}

bool pedirSensores(StaticJsonDocument<256>& doc) {
  if (WiFi.status() != WL_CONNECTED) return false;

  HTTPClient http;
  String url = String("http://") + DEVKIT_IP + "/sensores";
  http.begin(url);
  http.setTimeout(5000);

  int code = http.GET();
  if (code == 200) {
    String payload = http.getString();
    deserializeJson(doc, payload);
    Serial.printf("[Sensor] Luz: %.1f lux | Humedad: %d%%\n",
      doc["lux"].as<float>(), doc["humedad_pct"].as<int>());
    http.end();
    return true;
  }

  Serial.printf("[ERROR] DevKit no respondió: %d\n", code);
  http.end();
  return false;
}

camera_fb_t* capturarImagen() {
  digitalWrite(PIN_FLASH, HIGH);
  delay(100);
  camera_fb_t* fb = esp_camera_fb_get();
  digitalWrite(PIN_FLASH, LOW);

  if (!fb) {
    Serial.println("[ERROR] Fallo al capturar imagen");
    return NULL;
  }
  Serial.printf("[Cámara] %d bytes\n", fb->len);
  return fb;
}

void enviarAlBackend(StaticJsonDocument<256>& sensores, bool sensorOk, camera_fb_t* fb) {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  String url = String(BACKEND_URL) + "/api/lectura";
  http.begin(url);
  http.setTimeout(15000);

  String boundary = "PlantSenseBoundary";
  http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);

  // JSON con sensores
  String jsonStr = "{}";
  if (sensorOk) {
    serializeJson(sensores, jsonStr);
  }

  String jsonPart = "--" + boundary + "\r\n";
  jsonPart += "Content-Disposition: form-data; name=\"datos\"\r\n";
  jsonPart += "Content-Type: application/json\r\n\r\n";
  jsonPart += jsonStr + "\r\n";

  String imgPart = "--" + boundary + "\r\n";
  imgPart += "Content-Disposition: form-data; name=\"imagen\"; filename=\"planta.jpg\"\r\n";
  imgPart += "Content-Type: image/jpeg\r\n\r\n";

  String closing = "\r\n--" + boundary + "--\r\n";

  int totalLen = jsonPart.length() + imgPart.length() + fb->len + closing.length();
  uint8_t* body = (uint8_t*)malloc(totalLen);

  if (!body) {
    Serial.println("[ERROR] Sin memoria para el body");
    http.end();
    return;
  }

  int pos = 0;
  memcpy(body + pos, jsonPart.c_str(), jsonPart.length()); pos += jsonPart.length();
  memcpy(body + pos, imgPart.c_str(), imgPart.length());   pos += imgPart.length();
  memcpy(body + pos, fb->buf, fb->len);                    pos += fb->len;
  memcpy(body + pos, closing.c_str(), closing.length());

  int httpCode = http.POST(body, totalLen);
  free(body);

  if (httpCode == 200 || httpCode == 201) {
    Serial.printf("[OK] Backend %d: %s\n", httpCode, http.getString().c_str());
  } else {
    Serial.printf("[ERROR] Backend: %d\n", httpCode);
  }

  http.end();
}
