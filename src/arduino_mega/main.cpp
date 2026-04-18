#include <Arduino.h>
#include <Adafruit_GFX.h>
#include <MCUFRIEND_kbv.h>
#include <TouchScreen.h>
#include "telemetry.h"

MCUFRIEND_kbv tft;

// Touch Pins for most 3.5" Shields
#define YP A3
#define XM A2
#define YM 9
#define XP 8
#define MINPRESSURE 10
#define MAXPRESSURE 1000

TouchScreen ts = TouchScreen(XP, YP, XM, YM, 300);

// Color Definitions
#define BLACK   0x0000
#define GRAY    0x7BEF
#define GREEN   0x07E0
#define CYAN    0x07FF
#define RED     0xF800
#define YELLOW  0xFFE0
#define WHITE   0xFFFF
#define ORANGE  0xFD20

bool ui_drawn = false;
bool rx_blink = false;
bool focus_mode = false;

void drawStaticUI() {
    tft.fillScreen(BLACK);
    tft.drawRect(0, 0, 480, 320, GRAY);
    tft.drawFastHLine(0, 35, 480, GRAY);
    tft.drawFastHLine(0, 220, 480, GRAY);
    tft.drawFastVLine(240, 35, 185, GRAY);
    tft.drawFastHLine(240, 127, 240, GRAY); 

    tft.setTextSize(2);
    tft.setTextColor(CYAN);   tft.setCursor(15, 10);  tft.print("CPU & GPU PEAKS");
    tft.setTextColor(GREEN);  tft.setCursor(255, 10); tft.print("RTX 5080 & 3090");
    tft.setTextColor(YELLOW); tft.setCursor(15, 230); tft.print("SYSTEM TOTAL / PEAK");
}

void updateCPUColumn(const Telemetry& t) {
    tft.setTextColor(WHITE, BLACK); tft.setTextSize(5);
    tft.setCursor(20, 50);  tft.print(String((int)t.cpuPower) + "W  ");
    tft.setTextSize(2);
    tft.setTextColor(CYAN, BLACK);
    tft.setCursor(20, 100); tft.print("LOAD: " + String((int)t.cpuUsage) + "%  ");
    tft.drawFastHLine(10, 125, 220, GRAY);
    tft.setTextColor(WHITE, BLACK);
    tft.setCursor(20, 135); tft.print("CPU PEAK: " + String((int)t.peakCpuPwr) + "W ");
    tft.setTextColor(GREEN, BLACK);
    tft.setCursor(20, 160); tft.print("5080 PEAK:" + String((int)t.peakG1Pwr) + "W ");
    tft.setCursor(20, 185); tft.print("3090 PEAK:" + String((int)t.peakG2Pwr) + "W ");
}

void updateGPU(int id, const Telemetry& t) {
    int yOff = (id == 1) ? 0 : 92;
    const char* name = (id == 1) ? "RTX 5080" : "RTX 3090";
    float pwr = (id == 1) ? t.gpu1Power : t.gpu2Power;
    float temp = (id == 1) ? t.gpu1Temp : t.gpu2Temp;

    tft.setTextSize(2); tft.setTextColor(GREEN, BLACK); tft.setCursor(250, 45 + yOff); tft.print(name);
    tft.setTextSize(3); tft.setTextColor(WHITE, BLACK); tft.setCursor(250, 65 + yOff); tft.print(String((int)pwr) + "W ");
    tft.setTextColor(RED, BLACK); tft.setCursor(250, 95 + yOff); tft.print(String((int)temp) + "C ");
    tft.setTextSize(2); tft.setCursor(350, 103 + yOff); 
}

void updateSystem(const Telemetry& t) {
    tft.setTextSize(5); tft.setCursor(20, 260); tft.setTextColor(YELLOW, BLACK); tft.print(String((int)t.systemPower) + "W");
    tft.setTextColor(GRAY, BLACK); tft.print(" / ");
    tft.setTextColor(ORANGE, BLACK); tft.print(String((int)t.peakSysPwr) + "W ");
}

void drawFocusUI(const Telemetry& t) {
    if (!ui_drawn) { tft.fillScreen(BLACK); ui_drawn = true; }
    tft.setTextSize(3); tft.setTextColor(YELLOW, BLACK); tft.setCursor(40, 40); tft.print("SYSTEM TOTAL");
    tft.setTextSize(9); tft.setCursor(40, 80); tft.print(String((int)t.systemPower) + "W   ");
    tft.drawFastHLine(20, 160, 440, GRAY);
    tft.setTextSize(3); tft.setTextColor(ORANGE, BLACK); tft.setCursor(40, 190); tft.print("SYSTEM PEAK");
    tft.setTextSize(9); tft.setCursor(40, 230); tft.print(String((int)t.peakSysPwr) + "W   ");
}

void checkTouch() {
    TSPoint p = ts.getPoint();
    // MCUFRIEND shares pins with LCD, so we must reset them to OUTPUT
    pinMode(XM, OUTPUT); pinMode(YP, OUTPUT); pinMode(XP, OUTPUT); pinMode(YM, OUTPUT);

    if (p.z > MINPRESSURE && p.z < MAXPRESSURE) {
        focus_mode = !focus_mode;
        ui_drawn = false;
        tft.fillScreen(BLACK);
        delay(300); // Debounce
    }
}

void setup() {
    Serial.begin(115200);
    uint16_t ID = tft.readID();
    if (ID == 0x0000 || ID == 0xFFFF || ID == 0xD3D3) ID = 0x9486; 
    tft.begin(ID);
    tft.setRotation(3);
    tft.fillScreen(BLACK);
    tft.setTextColor(WHITE); tft.setTextSize(2);
    tft.setCursor(60, 140); tft.print("TOUCH ENABLED MONITOR v2.5");
}

void loop() {
    checkTouch();
    if (Serial.available() > 0) {
        String data = Serial.readStringUntil('\n');
        Telemetry t;
        if (parseTelemetry(data.c_str(), t)) {
            if (focus_mode) {
                drawFocusUI(t);
            } else {
                if (!ui_drawn) { drawStaticUI(); ui_drawn = true; }
                rx_blink = !rx_blink;
                tft.fillCircle(465, 18, 5, rx_blink ? GREEN : GRAY);
                updateCPUColumn(t);
                updateGPU(1, t);
                updateGPU(2, t);
                updateSystem(t);
            }
        }
    }
}
