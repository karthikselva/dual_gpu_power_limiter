#include "M5CoreInk.h"
#include <M5GFX.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include "telemetry.h"
#include "secrets.h"

// --- CONFIGURATION ---
const char* ssid     = WIFI_SSID;
const char* password = WIFI_PASSWORD;
const int udpPort    = 9999;
const int LED_PIN    = 10; // Built-in Green LED

// RTC/Sleep config
const int SLEEP_DURATION_SEC = 10;

WiFiUDP udp;
Ink_Sprite InkPageSprite(&M5.M5Ink);

void setup() {
    M5.begin();
    if (!M5.M5Ink.isInit()) {
        while (1) delay(100);
    }
    M5.M5Ink.clear(); // Clear screen once at start
    delay(1000);

    analogSetAttenuation(ADC_11db); // For battery reading on GPIO 35

    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, HIGH); // LED is active low, HIGH = OFF

    // Initialize Sprite
    if (InkPageSprite.creatSprite(0, 0, 200, 200, true) != 0) {
        while (1) delay(100);
    }

    Serial.begin(115200);
    
    // Connect to WiFi
    WiFi.begin(ssid, password);
    Serial.print("Connecting to WiFi");
    
    // Timeout for WiFi connection to save battery if PC is off
    int retry = 0;
    while (WiFi.status() != WL_CONNECTED && retry < 20) {
        delay(500);
        Serial.print(".");
        retry++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nConnected!");
        udp.begin(udpPort);
    } else {
        Serial.println("\nWiFi Failed.");
    }
}

void drawTelemetry(const Telemetry& t) {
    // Blink LED to denote successful sync
    digitalWrite(LED_PIN, LOW); // ON
    delay(100);
    digitalWrite(LED_PIN, HIGH); // OFF
    
    InkPageSprite.clear(); // Defaults to 0 (White)
    
    // --- 1. SYSTEM TOTAL CELL (Top) ---
    InkPageSprite.drawRect(4, 4, 192, 65, 1);
    InkPageSprite.drawString(55, 8, "TOTAL POWER", &AsciiFont8x16);
    
    // Battery Percentage (Divider: 5.1k / 20k+5.1k = 5.1/25.1)
    uint32_t raw = analogRead(35);
    float vbat = (float)raw * 3.3 / 4095.0 * (25.1 / 5.1);
    int batPct = (int)((vbat - 3.2) / (4.2 - 3.2) * 100.0);
    if (batPct > 100) batPct = 100;
    if (batPct < 0) batPct = 0;
    char batBuf[16];
    snprintf(batBuf, sizeof(batBuf), "B:%d%%", batPct);
    InkPageSprite.drawString(155, 8, batBuf, &AsciiFont8x16);

    char sysBuf[16];
    snprintf(sysBuf, sizeof(sysBuf), "%dW", (int)t.systemPower);
    InkPageSprite.drawString(65, 25, sysBuf, &AsciiFont24x48);

    // --- 2. DEVICE TABLE CELLS (Middle - Floating Grid) ---
    // Header Row
    InkPageSprite.drawRect(4, 73, 94, 25, 1); // Device Header Box
    InkPageSprite.drawString(25, 78, "DEVICE", &AsciiFont8x16);
    
    InkPageSprite.drawRect(102, 73, 94, 25, 1); // Pwr/Tmp Header Box
    InkPageSprite.drawString(115, 78, "PWR/TMP", &AsciiFont8x16);

    // RTX 5080 Row
    InkPageSprite.drawRect(4, 102, 94, 30, 1); // Box
    InkPageSprite.drawString(10, 109, "RTX 5080", &AsciiFont8x16);
    
    InkPageSprite.drawRect(102, 102, 94, 30, 1); // Box
    char g1Buf[20];
    snprintf(g1Buf, sizeof(g1Buf), "%dW / %dC", (int)t.gpu1Power, (int)t.gpu1Temp);
    InkPageSprite.drawString(108, 109, g1Buf, &AsciiFont8x16);

    // RTX 3090 Row
    InkPageSprite.drawRect(4, 136, 94, 30, 1); // Box
    InkPageSprite.drawString(10, 143, "RTX 3090", &AsciiFont8x16);
    
    InkPageSprite.drawRect(102, 136, 94, 30, 1); // Box
    char g2Buf[20];
    snprintf(g2Buf, sizeof(g2Buf), "%dW / %dC", (int)t.gpu2Power, (int)t.gpu2Temp);
    InkPageSprite.drawString(108, 143, g2Buf, &AsciiFont8x16);

    // --- 3. FOOTER CELL (Bottom) ---
    InkPageSprite.drawRect(4, 170, 192, 26, 1);
    char footerBuf[40];
    snprintf(footerBuf, sizeof(footerBuf), "SYNC:%s | PEAK:%dW", 
             (strlen(t.time) > 0) ? t.time : "--:--", 
             (int)t.peakSysPwr);
    InkPageSprite.drawString(12, 175, footerBuf, &AsciiFont8x16);

    if (M5.M5Ink.displayBusy()) delay(500); 
    InkPageSprite.pushSprite();
    M5.M5Ink.display();
}

void loop() {
    bool received = false;
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("Waiting for UDP packet (10s timeout)...");
        unsigned long start = millis();
        while (millis() - start < 10000) {
            int packetSize = udp.parsePacket();
            if (packetSize) {
                char packetBuffer[255];
                int len = udp.read(packetBuffer, 255);
                if (len > 0) packetBuffer[len] = 0;

                Telemetry t;
                if (parseTelemetry(packetBuffer, t)) {
                    Serial.printf("Received data at %s\n", t.time);
                    drawTelemetry(t);
                    received = true;
                    break;
                }
            }
            delay(100);
        }
    }

    if (!received && WiFi.status() == WL_CONNECTED) {
        digitalWrite(LED_PIN, LOW); // Solid ON to indicate offline/timeout
        InkPageSprite.clear();
        InkPageSprite.drawRect(0, 0, 200, 200, 0);
        InkPageSprite.drawString(60, 90, "PC OFFLINE", &AsciiFont8x16);
        
        // Battery Percentage
        uint32_t raw = analogRead(35);
        float vbat = (float)raw * 3.3 / 4095.0 * (25.1 / 5.1);
        int batPct = (int)((vbat - 3.2) / (4.2 - 3.2) * 100.0);
        if (batPct > 100) batPct = 100;
        if (batPct < 0) batPct = 0;
        char batBuf[16];
        snprintf(batBuf, sizeof(batBuf), "BAT: %d%%", batPct);
        InkPageSprite.drawString(120, 5, batBuf, &AsciiFont8x16);

        InkPageSprite.pushSprite();
        M5.M5Ink.display();
    }

    Serial.println("Loop finished, waiting 5s...");
    delay(5000); 
}
