# Ultimate Power & Temp Monitor v5.2 - Serial Edition (Dual GPU)
$ErrorActionPreference = "SilentlyContinue"

# --- SERIAL CONFIG ---
$portName = "COM3" # CHANGE THIS to your Arduino COM port
$baudRate = 115200

try {
    $port = New-Object System.IO.Ports.SerialPort $portName, $baudRate
    $port.Open()
    Write-Host "Connected to Arduino on $portName" -ForegroundColor Green
} catch {
    Write-Host "Failed to open $portName. Check if Arduino is connected." -ForegroundColor Red
}

# 1. Config
$cpuTdp = 120.0 
$moboEstimate = 95.0 
$interval = 1 
$nvismi = "C:\Windows\System32\nvidia-smi.exe"

while($true) {
    # --- GPU DATA ---
    $gpuMetrics = @()
    $gpuOut = cmd /c "`"$nvismi`" --query-gpu=power.draw,temperature.gpu --format=csv,noheader,nounits 2>&1"
    foreach ($line in $gpuOut) {
        if ($line -match "(\d+\.\d+),\s*(\d+)") {
            $gpuMetrics += [PSCustomObject]@{
                Power = [double]$matches[1]
                Temp  = [int]$matches[2]
            }
        }
    }

    # Ensure we have at least 2 entries for the string (even if 0)
    $g1P = if ($gpuMetrics.Count -gt 0) { $gpuMetrics[0].Power } else { 0.0 }
    $g1T = if ($gpuMetrics.Count -gt 0) { $gpuMetrics[0].Temp } else { 0 }
    $g2P = if ($gpuMetrics.Count -gt 1) { $gpuMetrics[1].Power } else { 0.0 }
    $g2T = if ($gpuMetrics.Count -gt 1) { $gpuMetrics[1].Temp } else { 0 }

    # --- CPU DATA ---
    $cpuUsage = 0
    try {
        $cpuInfo = Get-CimInstance -ClassName Win32_PerfFormattedData_Counters_ProcessorInformation -Filter "Name='_Total'"
        if ($cpuInfo) { $cpuUsage = $cpuInfo.PercentProcessorUtility }
    } catch { }
    $cpuPower = 20.0 + (($cpuUsage / 100) * ($cpuTdp - 20.0))
    $cpuTemp = 38.0 + (($cpuUsage / 100) * (85.0 - 38.0))

    # --- TOTALS ---
    $gpuTotalPwr = $g1P + $g2P
    $totalSystem = $gpuTotalPwr + $cpuPower + $moboEstimate

    # --- SEND TO ARDUINO ---
    # Format: Usage,CpuPwr,CpuTemp,Gpu1Pwr,Gpu1Temp,Gpu2Pwr,Gpu2Temp,SysPwr (8 values)
    if ($port -and $port.IsOpen) {
        $dataString = "{0},{1:N1},{2:N1},{3:N1},{4},{5:N1},{6},{7:N1}" -f $cpuUsage, $cpuPower, $cpuTemp, $g1P, $g1T, $g2P, $g2T, $totalSystem
        $port.WriteLine($dataString)
    }

    # --- LOCAL DISPLAY ---
    Clear-Host
    Write-Host "Sending to Arduino: $dataString" -ForegroundColor Gray
    Write-Host "CPU: $cpuUsage% | $cpuPower W | $cpuTemp C" -ForegroundColor Cyan
    Write-Host "G1: $g1P W | $g1T C" -ForegroundColor Green
    Write-Host "G2: $g2P W | $g2T C" -ForegroundColor Green
    Write-Host "SYS: $totalSystem W" -ForegroundColor White

    Start-Sleep -Seconds $interval
}

# Cleanup on exit
if ($port) { $port.Close() }
