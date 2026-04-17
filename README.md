# Ultimate Power & Temp Monitor v2.0

A professional telemetry dashboard for Arduino Mega/Uno using a 3.5" TFT Shield. This project monitors real-time CPU and GPU power consumption, temperatures, and usage metrics from your Windows PC.

## 🏗 Architecture

The system operates in a producer-consumer model:

1.  **Producer (Windows PC):** A PowerShell script (`PowerCheck_Serial.ps1`) runs in the background. It queries `nvidia-smi` for GPU data and WMI/CIM for CPU data.
2.  **Transmitter:** Data is formatted as a CSV string (`usage,cpuPwr,cpuTemp,gpuPwr,gpuTemp,sysPwr`) and sent over Serial (USB) at 115200 baud.
3.  **Consumer (Arduino):** The Arduino parses the incoming string, tracks peak values, and updates a high-resolution 3.5" TFT display using an optimized landscape UI.

## 📊 Data Flow & Formats

```text
[ WINDOWS PC ]                            [ ARDUINO ]
PowerCheck.ps1   ---( Serial USB )--->    main.cpp
      |                                      |
      |   "45,60.5,52.3,210.8,65,350.2"      |
      v                                      v
1. Gather Metrics                      1. Serial.readStringUntil('\n')
2. Format as CSV String                2. Parse String to Float Array
3. Port.WriteLine(data)                3. Update UI & Peak Tracking
```

### Protocol Specification (CSV)
The Arduino expects exactly 6 floating-point/integer values separated by commas:

| Index | Field | Type | Description |
| :--- | :--- | :--- | :--- |
| 0 | `usage` | Float | CPU Load percentage (0.0 - 100.0) |
| 1 | `cpuPwr` | Float | CPU Power Draw in Watts |
| 2 | `cpuTemp`| Float | CPU Temperature in Celsius |
| 3 | `gpuPwr` | Float | GPU Power Draw in Watts |
| 4 | `gpuTemp`| Int | GPU Temperature in Celsius |
| 5 | `sysPwr` | Float | Total Estimated System Power in Watts |

**Example Packet:** `22,45.2,48.5,180.5,55,320.7`

## 🛠 Tools & Tech Stack

*   **VS Code:** Primary IDE for development.
*   **PlatformIO:** Professional extension for Arduino development and library management.
*   **Wokwi Simulator:** Integrated simulator for testing hardware logic without physical devices.
*   **PowerShell:** System-level telemetry gathering script.
*   **Libraries:**
    *   `MCUFRIEND_kbv`: Optimized for 8-bit parallel TFT shields.
    *   `Adafruit GFX`: Core graphics primitive library.

## 🚀 Getting Started

### 1. Prerequisites
*   Install **VS Code**.
*   Install the **PlatformIO IDE** extension.
*   Install the **Wokwi Simulator** extension (optional, for simulation).

### 2. Physical Setup
*   Plug your 3.5" TFT Shield into your Arduino Mega 2560 or Uno.
*   Connect the Arduino to your PC via USB.

### 3. Build and Upload
1.  Open this folder in VS Code.
2.  PlatformIO will automatically download the required libraries.
3.  Click the **Checkmark (✓)** icon in the bottom bar to **Build**.
4.  Click the **Right Arrow (→)** icon to **Upload** to your Arduino.

### 4. Running the Telemetry
1.  Open `pc_side/PowerCheck_Serial.ps1`.
2.  Update the `$portName` variable (e.g., `"COM3"`) to match your Arduino's port.
3.  Right-click the script and select **Run with PowerShell**.

## 🖥 Simulation (Wokwi)
1.  Ensure you have built the project (`mega2560` environment).
2.  Press `F1` and select **Wokwi: Start Simulator**.
3.  The simulator will use a mapped ILI9488 display to show the UI.
4.  *Note: To feed data to the simulator, you can use the Wokwi Serial terminal to paste strings like `50,65.5,55.0,250.2,62,410.5`.*

## 📂 Project Structure
```text
power_meter_arduino_vscode/
├── .vscode/             # VS Code settings & extensions
├── lib/                 # Private libraries
├── src/
│   └── main.cpp         # Main Arduino logic (C++)
├── pc_side/
│   └── PowerCheck_Serial.ps1  # PC Telemetry script
├── platformio.ini       # Project configuration
├── diagram.json         # Wokwi hardware wiring
└── wokwi.toml           # Wokwi simulation config
```

## 🎨 UI Customization
The UI is designed for **Landscape Mode (Rotation 1)**.
*   **Left Pane:** CPU metrics (Watts, Temp, Load, Peaks).
*   **Right Pane:** GPU metrics (Watts, Temp, Peaks).
*   **Bottom Pane:** System Total (Real-time and All-time Max).
*   **Pulse LED:** A green indicator in the top right blinks on every successful data packet received.
