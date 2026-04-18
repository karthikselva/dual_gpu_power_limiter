## 🎯 Who is this for?

1.  **Hardware Enthusiasts & Modders:** For those who want a dedicated real-time hardware dashboard (CPU/GPU load, temps, power) visible through their PC cabinet's glass side panel.
    *   **Pre-requisites:** Arduino Uno or Mega + 3.5" (or larger) TFT LCD Shield.
2.  **Power-Conscious Users (Dual GPU/Small Circuits):** For users running high-performance hardware (like Dual RTX 3090/5080) on standard residential circuits (e.g., 6A sockets in India) who need to monitor real-time wattage to prevent tripping breakers or damaging electrical infrastructure.


## ⚠️ Safety & Power Management (Dual GPU Context)

Running a dual GPU setup with a **RTX 3090** and **RTX 5080** on a standard **1000W PSU** presents significant electrical challenges, particularly during long-running Machine Learning tasks (LoRA training, LLM inference).

### The Challenge
1.  **Transient Power Spikes:** High-end GPUs are notorious for "micro-spikes" (millisecond-duration transients) that can exceed their rated TDP significantly. Combined, these spikes can overwhelm a 1000W PSU's OCP (Over-Current Protection), leading to sudden system shutdowns or hardware stress.
2.  **Infrastructure Limits (India):** In many Indian residential settings, standard power sockets are rated for **6A**. At 230V, while the theoretical limit is ~1380W, sustained high-wattage draw (especially on shared circuits with aging wiring) risks overheating sockets or tripping breakers. 
3.  **Economic Constraints:** Upgrading to high-tier 1200W-1600W PSUs involves exponentially rising costs. Additionally, many of these PSUs require 16A industrial-style sockets, which necessitates expensive electrical modifications to the room.

### The Solution
This project provides a software-controlled safety layer:
*   **Active Monitoring:** Real-time visibility into "Actual vs Limit" wattage on both the Arduino and the PC GUI allows you to see exactly how much headroom remains.
*   **Dynamic Capping:** One-click toggles to drop power limits (e.g., capping the GPUs during 10+ hour training sessions). This ensures total system draw stays within a "Safe Zone" (~600-700W), providing ample headroom for transient spikes and protecting both the PSU and the local electrical infrastructure.
  
# Dead Simple Power & Temp Monitor v2.5

Simple system telemetry suite for Arduino Mega/Uno and Windows. This project provides a real-time hardware dashboard on a 3.5" TFT Shield and a desktop control utility for managing GPU power limits.

## 🖼 Visuals

| Arduino Hardware Dashboard | PC Control Panel |
| :---: | :---: |
| ![PC GUI](screenshots/IMG_2677.JPEG) | ![Arduino Dashboard](screenshots/snap_ui.png) |
| ![PC GUI](screenshots/IMG_2675.JPEG) | ![Arduino Dashboard](screenshots/IMG_2676.JPEG) |

| M5 Core Ink Wireless Dashboard |
| :---: |
| ![Core Ink](screenshots/core_ink.JPEG) |


## 🏗 Architecture & Summary

The system follows a **Producer-Dual Consumer** model with an integrated **Control Feedback** loop:

1.  **Producer (PowerCheck_Serial.ps1):** A hidden PowerShell service that gathers CPU metrics (WMI) and Dual GPU metrics (Nvidia-SMI), including live power draw, temperatures, and set power limits.
2.  **Transmitter:** 
    *   **Serial (USB):** Sends a 10-value CSV packet to the Arduino every second.
    *   **UDP (Local):** Broadcasts the same packet on port `9999` for the local Python GUI.
3.  **Consumer A (Arduino):** Displays a high-density landscape dashboard. Features a **Touch Toggle** to switch between "All Metrics" and a "Big Font Focus Mode".
4.  **Consumer B (Python GUI):** A dark-themed desktop monitor that mirrors the Arduino and provides buttons to dynamically adjust RTX 5080 and RTX 3090 power limits via batch scripts.


## 📊 Data Flow & Protocol

```text
[ WINDOWS PC ]                                     [ ARDUINO ]
PowerCheck Service  ---( Serial USB )----------->  Dashboard UI
(Producer)          |                              (Consumer A)
      |             |
      |             +---( UDP Port 9999 )-------+
      |                                         |
      v                                         v
[ CONTROL PANEL ] <---( Execute BAT )--- [ PYTHON GUI ]
(Feedback Loop)                          (Consumer B)
```

### CSV Protocol Specification
The system uses a **15-value** floating-point string:
`usage, cpuPwr, cpuTemp, g1Pwr, g1Temp, g1Limit, g2Pwr, g2Temp, g2Limit, sysPwr, peakCpu, peakG1, peakG2, peakSys, time`

| Field | Description | Field | Description |
| :--- | :--- | :--- | :--- |
| `usage` | CPU Load % | `g2Temp` | RTX 3090 Temp (°C) |
| `cpuPwr` | CPU Watts | `g2Limit` | RTX 3090 Power Limit (W) |
| `cpuTemp`| (Reserved) | `sysPwr` | Total System Draw |
| `g1Pwr` | RTX 5080 Watts | `peakCpu` | Session Peak CPU (W) |
| `g1Temp` | RTX 5080 Temp (°C) | `peakG1` | Session Peak G1 (W) |
| `g1Limit`| RTX 5080 Power Limit (W)| `peakG2` | Session Peak G2 (W) |
| `g2Pwr` | RTX 3090 Watts | `peakSys` | Session Peak System (W) |
| `time` | Sync Time (HH:mm) | | |

## 🚀 How to Run

### 1. Arduino Setup
*   Open the folder in VS Code with **PlatformIO** installed.
*   **For Wired Display:** Select the `mega2560` or `uno` environment and click **Upload**.
*   **For Wireless Core Ink:** 
    *   Open `include/secrets.h` and enter your WiFi SSID and Password.
    *   Select the `m5stack-coreink` environment and click **Upload**.
*   **Touch Function (TFT):** Tap the screen anytime to toggle "Focus Mode".

### 2. PC Control Panel
*   Locate `Run_Control_Panel.bat` in the project root.
*   **Double-click it** (it will automatically ask for Admin rights).
*   Click **START TELEMETRY SERVICE** to begin monitoring.
*   Use the **MAX** and **LOW** buttons to toggle GPU power profiles.

## 🖥 Features

### Arduino Dashboard
*   **Standard View:** Parallel columns for CPU and Dual GPU live data + Peak tracking.
*   **Focus View:** Massive font display of Total System Watts and All-time Peak.
*   **Heartbeat:** Green LED in the top right blinks on every successful packet.

### Python GUI
*   **Live Mirror:** Real-time data from the PowerShell service.
*   **Limit Monitoring:** Shows `Actual Watts / Limit Watts` for both GPUs.
*   **Background Operation:** The PowerShell window is hidden automatically when started.

## 📂 Project Structure
```text
├── Run_Control_Panel.bat    # Entry point for PC software
├── platformio.ini           # Arduino build config
├── src/
│   ├── arduino_mega/        # Arduino Mega/Uno Display & Touch logic
│   └── m5_core_ink/         # M5 Core Ink Wireless Display logic
├── include/telemetry.h      # Shared C++ parsing logic
└── pc_side/
    ├── control_gui.py       # Python Monitoring App
    ├── PowerCheck_Serial.ps1 # Telemetry Service
    └── *_power_limit.bat    # GPU Control scripts
```

## 📌 Maintenance Tips
*   **Pinning to Taskbar:** Create a shortcut for `Run_Control_Panel.bat`, right-click -> Properties, and change the target to: `cmd /c "PATH_TO_BATCH"`.
*   **Auto-Start:** Add that shortcut to `shell:startup` for monitoring on every boot.
