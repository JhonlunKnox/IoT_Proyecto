/*
 * PlantSense — ESP32 DevKit v3
 * - Lee BH1750 + Raindrop + Capacitivo
 * - NTP para sincronización de tiempo
 * - Publica por MQTT TLS cada 30s
 * - Sirve HTTP /sensores y /health
 *
 * Librerías: BH1750, ArduinoJson, PubSubClient
 * Board: ESP32 Dev Module
 */

#include <Wire.h>
#include <BH1750.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <time.h>

// ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
const char* WIFI_SSID     = "*******";
const char* WIFI_PASSWORD = "*******";

// NTP
const char* NTP_SERVER   = "*******";
const long  GMT_OFFSET_S = *****;
const int   DST_OFFSET_S = *;

// HiveMQ
const char* MQTT_HOST   = "******";
const int   MQTT_PORT   = ****;
const char* MQTT_USER   = "*****";
const char* MQTT_PASS   = "*****";
const char* MQTT_TOPIC  = "********";
const char* MQTT_CLIENT = "*******";

// Pines
#define I2C_SDA              4
#define I2C_SCL              5
#define PIN_HUMEDAD_RAINDROP 34
#define PIN_HUMEDAD_SUELO    35

// Umbrales
const int   RAINDROP_SECO   = 3500;
const int   RAINDROP_HUMEDO = 1500;
const int   SUELO_SECO      = 3300;
const int   SUELO_HUMEDO    = 1400;
const float LUZ_BAJA_LUX    = 200.0;
const float LUZ_ALTA_LUX    = 60000.0;

const unsigned long INTERVALO_MQTT = 30000;

// ─── OBJETOS ──────────────────────────────────────────────────────────────────
BH1750 luminosidad;
WebServer server(80);
WiFiClientSecure wifiSecure;
PubSubClient mqtt(wifiSecure);
unsigned long ultimaPublicacion = 0;
bool bh1750Ok = false;

// ─── NTP ──────────────────────────────────────────────────────────────────────
String getTimestamp() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) return "sin-ntp";
  char buf[25];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%S", &timeinfo);
  return String(buf);
}

// ─── INIT BH1750 ─────────────────────────────────────────────────────────────
bool initBH1750() {
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(100000);
  delay(1000);
  // CONTINUOUS — mide de forma continua sin necesidad de reiniciar
  if (luminosidad.begin(BH1750::CONTINUOUS_HIGH_RES_MODE)) {
    Serial.println("[OK] BH1750 listo (CONTINUOUS mode)");
    return true;
  }
  Serial.println("[ERROR] BH1750 no responde");
  return false;
}

// ─── LEER SENSORES ────────────────────────────────────────────────────────────
String leerSensoresJSON() {
  // Leer BH1750 directamente — CONTINUOUS no necesita reiniciar
  float lux = -1;
  if (bh1750Ok) {
    lux = luminosidad.readLightLevel();
  }

  int rainRaw  = analogRead(PIN_HUMEDAD_RAINDROP);
  int rainPct  = constrain(map(rainRaw, RAINDROP_SECO, RAINDROP_HUMEDO, 0, 100), 0, 100);
  int sueloRaw = analogRead(PIN_HUMEDAD_SUELO);
  int sueloPct = constrain(map(sueloRaw, SUELO_SECO, SUELO_HUMEDO, 0, 100), 0, 100);

  String alertaRain  = rainRaw  > RAINDROP_SECO ? "seco" : rainRaw  < RAINDROP_HUMEDO ? "exceso_agua" : "ok";
  String alertaSuelo = sueloRaw > SUELO_SECO    ? "seco" : sueloRaw < SUELO_HUMEDO    ? "humedo"      : "ok";
  String alertaLuz   = (lux < 0 || lux < LUZ_BAJA_LUX) ? "poca_luz" : lux > LUZ_ALTA_LUX ? "exceso_luz" : "ok";

  Serial.printf("[Sensor] Luz: %.1f lux | Rain: %d%%(raw=%d) | Suelo: %d%%(raw=%d)\n",
    lux, rainPct, rainRaw, sueloPct, sueloRaw);

  StaticJsonDocument<512> doc;
  doc["timestamp"]      = getTimestamp();
  doc["lux"]            = lux;
  doc["alerta_luz"]     = alertaLuz;
  doc["humedad_pct"]    = rainPct;
  doc["humedad_raw"]    = rainRaw;
  doc["alerta_humedad"] = alertaRain;
  doc["suelo_pct"]      = sueloPct;
  doc["suelo_raw"]      = sueloRaw;
  doc["alerta_suelo"]   = alertaSuelo;

  String json;
  serializeJson(doc, json);
  return json;
}

// ─── SETUP ────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(1000);

  bh1750Ok = initBH1750();

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[WiFi] Conectando");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.printf("\n[OK] IP: %s\n", WiFi.localIP().toString().c_str());
  Serial.println(">>> Guarda esta IP para el ESP32-CAM <<<");

  delay(2000); // estabilizar WiFi antes de NTP
  configTime(GMT_OFFSET_S, DST_OFFSET_S, "time.google.com", "time.cloudflare.com");
  Serial.print("[NTP] Sincronizando");
  struct tm timeinfo;
  int ntpTry = 0;
  while (!getLocalTime(&timeinfo) && ntpTry < 20) {
    delay(500); Serial.print("."); ntpTry++;
  }
  Serial.println(ntpTry < 20 ? "\n[OK] NTP: " + getTimestamp() : "\n[WARN] NTP sin sync");

  wifiSecure.setInsecure();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(512);

  server.on("/sensores", HTTP_GET, []() {
    String json = leerSensoresJSON();
    server.send(200, "application/json", json);
    Serial.println("[HTTP] /sensores servido");
  });
  server.on("/health", HTTP_GET, []() {
    String h = "{\"status\":\"ok\",\"bh1750\":" + String(bh1750Ok ? "true" : "false") +
               ",\"time\":\"" + getTimestamp() + "\"}";
    server.send(200, "application/json", h);
  });
  server.begin();
  Serial.println("[OK] Servidor HTTP listo");
}

// ─── MQTT RECONNECT ───────────────────────────────────────────────────────────
void reconnectMQTT() {
  int intentos = 0;
  while (!mqtt.connected() && intentos < 3) {
    Serial.print("[MQTT] Conectando...");
    if (mqtt.connect(MQTT_CLIENT, MQTT_USER, MQTT_PASS)) {
      Serial.println(" OK");
    } else {
      Serial.printf(" fallo rc=%d\n", mqtt.state());
      delay(3000); intentos++;
    }
  }
}

// ─── LOOP ─────────────────────────────────────────────────────────────────────
void loop() {
  server.handleClient();

  if (millis() - ultimaPublicacion >= INTERVALO_MQTT) {
    ultimaPublicacion = millis();
    if (!mqtt.connected()) reconnectMQTT();
    if (mqtt.connected()) {
      String json = leerSensoresJSON();
      mqtt.publish(MQTT_TOPIC, json.c_str());
      Serial.println("[MQTT] Publicado: " + json);
    }
  }

  mqtt.loop();
}
