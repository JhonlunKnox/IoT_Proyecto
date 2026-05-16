/*
 * PlantSense — ESP32 DevKit v2
 * Lee sensores y publica por MQTT a HiveMQ Cloud
 * También sirve HTTP /sensores para el ESP32-CAM
 *
 * Librerías adicionales:
 *   - EspMQTTClient by Patrick Lapointe
 *
 * Board: ESP32 Dev Module
 */

#include <Wire.h>
#include <BH1750.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>

// ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
const char* WIFI_SSID     = "FAMILIA ZULETA 2.4";
const char* WIFI_PASSWORD = "Z36516720Z";

// HiveMQ
const char* MQTT_HOST     = "47a47f3de86f476a91bd8afead18912b.s1.eu.hivemq.cloud";
const int   MQTT_PORT     = 8883;
const char* MQTT_USER     = "juanluzu";
const char* MQTT_PASS     = "Reach2001.";
const char* MQTT_TOPIC    = "plantsense/sensores";
const char* MQTT_CLIENT   = "plantsense-devkit";

// Pines
#define I2C_SDA              21
#define I2C_SCL              22
#define PIN_HUMEDAD_RAINDROP 34
#define PIN_HUMEDAD_SUELO    35

// Umbrales
const int RAINDROP_SECO   = 3500;
const int RAINDROP_HUMEDO = 1500;
const int SUELO_SECO      = 3300;
const int SUELO_HUMEDO    = 1400;
const float LUZ_BAJA_LUX  = 200.0;
const float LUZ_ALTA_LUX  = 60000.0;

// Intervalo publicación MQTT (ms)
const unsigned long INTERVALO_MQTT = 30000;

// ─── OBJETOS ──────────────────────────────────────────────────────────────────
BH1750 luminosidad;
WebServer server(80);
WiFiClientSecure wifiSecure;
PubSubClient mqtt(wifiSecure);
unsigned long ultimaPublicacion = 0;

// ─── LEER SENSORES ────────────────────────────────────────────────────────────
String leerSensoresJSON() {
  float lux    = luminosidad.readLightLevel();
  int rainRaw  = analogRead(PIN_HUMEDAD_RAINDROP);
  int rainPct  = constrain(map(rainRaw, RAINDROP_SECO, RAINDROP_HUMEDO, 0, 100), 0, 100);
  int sueloRaw = analogRead(PIN_HUMEDAD_SUELO);
  int sueloPct = constrain(map(sueloRaw, SUELO_SECO, SUELO_HUMEDO, 0, 100), 0, 100);

  String alertaRain  = rainRaw > RAINDROP_SECO ? "seco" : rainRaw < RAINDROP_HUMEDO ? "exceso_agua" : "ok";
  String alertaSuelo = sueloRaw > SUELO_SECO   ? "seco" : sueloRaw < SUELO_HUMEDO   ? "humedo"      : "ok";
  String alertaLuz   = lux < LUZ_BAJA_LUX      ? "poca_luz" : lux > LUZ_ALTA_LUX   ? "exceso_luz"  : "ok";

  StaticJsonDocument<512> doc;
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

  Wire.begin(I2C_SDA, I2C_SCL);
  delay(500);
  luminosidad.begin(BH1750::CONTINUOUS_HIGH_RES_MODE);
  Serial.println("[OK] BH1750 listo");

  // WiFi
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[WiFi] Conectando");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.printf("\n[OK] IP: %s\n", WiFi.localIP().toString().c_str());

  // MQTT TLS (sin verificar certificado para MVP)
  wifiSecure.setInsecure();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(512);

  // HTTP servidor local
  server.on("/sensores", HTTP_GET, []() {
    String json = leerSensoresJSON();
    server.send(200, "application/json", json);
    Serial.println("[HTTP] /sensores → " + json);
  });
  server.on("/health", HTTP_GET, []() {
    server.send(200, "text/plain", "ok");
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
      delay(3000);
      intentos++;
    }
  }
}

// ─── LOOP ─────────────────────────────────────────────────────────────────────
void loop() {
  server.handleClient();

  // Publicar por MQTT cada 30s
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
