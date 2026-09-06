/*
 * sketch.ino — Quadra Inteligente de Beach Tennis
 * ESP32 simulado no Wokwi (Community License)
 *
 * ⚠️  MQTT é não-bloqueante: botão e LED funcionam mesmo sem MQTT.
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <time.h>

const char* WIFI_SSID     = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";
const char* MQTT_BROKER   = "localhost";
const int   MQTT_PORT     = 1883;
const char* MQTT_CLIENT   = "esp32-court01";
const char* TOPIC         = "quadra/highlight";

const int PIN_BUTTON = 13;
const int PIN_LED    = 2;

const unsigned long DEBOUNCE_MS   = 300;
const unsigned long MQTT_RETRY_MS = 5000;

unsigned long lastPressMs       = 0;
unsigned long lastMqttAttemptMs = 0;

WiFiClient   wifiClient;
PubSubClient mqttClient(wifiClient);

void blinkLED(int times, int ms) {
  for (int i = 0; i < times; i++) {
    digitalWrite(PIN_LED, HIGH); delay(ms);
    digitalWrite(PIN_LED, LOW);
    if (i < times - 1) delay(ms);
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_BUTTON, INPUT_PULLUP);
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);

  // WiFi
  Serial.print("📶  WiFi...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long t = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t < 10000) {
    delay(500); Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n✅  WiFi OK: %s\n", WiFi.localIP().toString().c_str());
    configTime(0, 0, "pool.ntp.org");
  } else {
    Serial.println("\n⚠️  WiFi falhou — modo offline");
  }

  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setBufferSize(512);

  blinkLED(3, 150);  // 3 blinks = pronto
  Serial.println("✅  Pronto! Pressione o botão.");
}

void loop() {
  // MQTT não-bloqueante
  if (!mqttClient.connected()) {
    if (millis() - lastMqttAttemptMs >= MQTT_RETRY_MS) {
      lastMqttAttemptMs = millis();
      Serial.printf("📡  MQTT %s:%d... ", MQTT_BROKER, MQTT_PORT);
      if (mqttClient.connect(MQTT_CLIENT)) Serial.println("OK ✅");
      else Serial.printf("falhou (rc=%d)\n", mqttClient.state());
    }
  } else {
    mqttClient.loop();
  }

  // Botão
  if (digitalRead(PIN_BUTTON) == LOW) {
    unsigned long now = millis();
    if (now - lastPressMs >= DEBOUNCE_MS) {
      lastPressMs = now;

      StaticJsonDocument<256> doc;
      doc["court_id"]   = "court_01";
      doc["player"]     = "A";
      doc["event_type"] = "highlight";
      doc["timestamp"]  = (unsigned long)time(nullptr);

      char payload[256];
      serializeJson(doc, payload);

      bool ok = mqttClient.publish(TOPIC, payload);
      Serial.printf("📤  %s | %s\n", payload, ok ? "✅" : "❌");

      blinkLED(1, 500);
    }
  }
}
