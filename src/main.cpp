#include <Arduino.h>
#include <Adafruit_GFX.h>
#include <MCUFRIEND_kbv.h>
#include "telemetry.h"

MCUFRIEND_kbv tft;

// Color Definitions
#define BLACK   0x0000
#define GRAY    0x7BEF
#define GREEN   0x07E0
#define CYAN    0x07FF
#define RED     0xF800
#define YELLOW  0xFFE0
#define WHITE   0xFFFF
#define ORANGE  0xFD20

// Peak Tracking
struct Peaks {
    int cpuW;
    int gpu1W, gpu1T;
    int gpu2W, gpu2T;
    int sysW;
} peaks = {0, 0, 0, 0, 0, 0};

bool ui_drawn = false;
bool rx_blink = false;

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

void updateCPUColumn(float pwr, float usage) {
    if (pwr > peaks.cpuW) peaks.cpuW = (int)pwr;

    // CPU Live Data
    tft.setTextColor(WHITE, BLACK); tft.setTextSize(5);
    tft.setCursor(20, 50);  tft.print(String((int)pwr) + "W  ");
    
    tft.setTextSize(2);
    tft.setTextColor(CYAN, BLACK);
    tft.setCursor(20, 100); tft.print("LOAD: " + String((int)usage) + "%  ");
    
    tft.drawFastHLine(10, 125, 220, GRAY);

    // Peak Section
    tft.setTextColor(WHITE, BLACK);
    tft.setCursor(20, 135); tft.print("CPU PEAK: " + String(peaks.cpuW) + "W ");
    tft.setTextColor(GREEN, BLACK);
    tft.setCursor(20, 160); tft.print("5080 PEAK:" + String(peaks.gpu1W) + "W ");
    tft.setCursor(20, 185); tft.print("3090 PEAK:" + String(peaks.gpu2W) + "W ");
}

void updateGPU(int id, float pwr, float temp) {
    int yOff = (id == 1) ? 0 : 92;
    const char* name = (id == 1) ? "RTX 5080" : "RTX 3090";
    
    if (id == 1) {
        if (pwr > peaks.gpu1W) peaks.gpu1W = (int)pwr;
        if (temp > peaks.gpu1T) peaks.gpu1T = (int)temp;
    } else {
        if (pwr > peaks.gpu2W) peaks.gpu2W = (int)pwr;
        if (temp > peaks.gpu2T) peaks.gpu2T = (int)temp;
    }

    tft.setTextSize(2);
    tft.setTextColor(GREEN, BLACK);
    tft.setCursor(250, 45 + yOff); tft.print(name);
    
    // Power Draw
    tft.setTextSize(3);
    tft.setTextColor(WHITE, BLACK);
    tft.setCursor(250, 65 + yOff); tft.print(String((int)pwr) + "W ");
    
    // Temp + Max Temp on same line
    tft.setTextSize(3);
    tft.setTextColor(RED, BLACK);
    tft.setCursor(250, 95 + yOff); tft.print(String((int)temp) + "C ");
    
    tft.setTextSize(2);
    tft.setCursor(350, 103 + yOff); // Shifted right and adjusted for size
    tft.print("M:" + String((id == 1) ? peaks.gpu1T : peaks.gpu2T) + "C");
}

void updateSystem(float pwr) {
    if (pwr > peaks.sysW) peaks.sysW = (int)pwr;
    
    // System Total
    tft.setTextSize(5);
    tft.setCursor(20, 260);
    tft.setTextColor(YELLOW, BLACK);
    tft.print(String((int)pwr) + "W");
    
    // Separator
    tft.setTextColor(GRAY, BLACK);
    tft.print(" / ");

    // System Peak (Same size/style)
    tft.setTextColor(ORANGE, BLACK);
    tft.print(String(peaks.sysW) + "W ");
}

void setup() {
    Serial.begin(115200);
    uint16_t ID = tft.readID();
    if (ID == 0x0000 || ID == 0xFFFF || ID == 0xD3D3) ID = 0x9486; 
    tft.begin(ID);
    tft.setRotation(1);
    tft.fillScreen(BLACK);
    tft.setTextColor(WHITE); tft.setTextSize(2);
    tft.setCursor(60, 140); tft.print("PRO DUAL GPU MONITOR v2.4");
}

void loop() {
    if (Serial.available() > 0) {
        String data = Serial.readStringUntil('\n');
        Telemetry t;
        if (parseTelemetry(data.c_str(), t)) {
            if (!ui_drawn) { drawStaticUI(); ui_drawn = true; }
            
            rx_blink = !rx_blink;
            tft.fillCircle(465, 18, 5, rx_blink ? GREEN : GRAY);
            
            updateCPUColumn(t.cpuPower, t.cpuUsage);
            updateGPU(1, t.gpu1Power, t.gpu1Temp);
            updateGPU(2, t.gpu2Power, t.gpu2Temp);
            updateSystem(t.systemPower);
        }
    }
}
