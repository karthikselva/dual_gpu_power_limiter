# Ultimate Power & Temp Monitor v5.3 - Serial Edition (Dual GPU + Limits)
$ErrorActionPreference = "SilentlyContinue"

# --- SERIAL CONFIG ---
$portName = "COM3" 
$baudRate = 115200

try {
    $port = New-Object System.IO.Ports.SerialPort $portName, $baudRate
    $port.Open()
} catch { }

# 1. Config
$cpuTdp = 120.0 
$moboEstimate = 95.0 
$interval = 1 
$nvismi = "C:\Windows\System32\nvidia-smi.exe"

while($true) {
    # --- GPU DATA ---
    $gpuMetrics = @()
    # Added power.limit to query
    $gpuOut = cmd /c "`"$nvismi`" --query-gpu=power.draw,temperature.gpu,power.limit --format=csv,noheader,nounits 2>&1"
    foreach ($line in $gpuOut) {
        if ($line -match "(\d+\.\d+),\s*(\d+),\s*(\d+\.\d+)") {
            $gpuMetrics += [PSCustomObject]@{
                Power = [double]$matches[1]
                Temp  = [int]$matches[2]
                Limit = [double]$matches[3]
            }
        }
    }

    $g1P = if ($gpuMetrics.Count -gt 0) { $gpuMetrics[0].Power } else { 0.0 }
    $g1T = if ($gpuMetrics.Count -gt 0) { $gpuMetrics[0].Temp } else { 0 }
    $g1L = if ($gpuMetrics.Count -gt 0) { $gpuMetrics[0].Limit } else { 0.0 }
    
    $g2P = if ($gpuMetrics.Count -gt 1) { $gpuMetrics[1].Power } else { 0.0 }
    $g2T = if ($gpuMetrics.Count -gt 1) { $gpuMetrics[1].Temp } else { 0 }
    $g2L = if ($gpuMetrics.Count -gt 1) { $gpuMetrics[1].Limit } else { 0.0 }

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

    # --- SEND TO ARDUINO & GUI ---
    # New Format: Usage,CpuPwr,CpuTemp,G1P,G1T,G1L,G2P,G2T,G2L,SysPwr (10 values)
    $dataString = "{0},{1:N1},{2:N1},{3:N1},{4},{5:N1},{6:N1},{7},{8:N1},{9:N1}" -f $cpuUsage, $cpuPower, $cpuTemp, $g1P, $g1T, $g1L, $g2P, $g2T, $g2L, $totalSystem
    
    if ($port -and $port.IsOpen) {
        $port.WriteLine($dataString)
    }

    # UDP BROADCAST FOR GUI
    try {
        $udpClient = New-Object System.Net.Sockets.UdpClient
        $byteData = [System.Text.Encoding]::ASCII.GetBytes($dataString)
        $null = $udpClient.Send($byteData, $byteData.Length, "127.0.0.1", 9999)
        $udpClient.Close()
    } catch {}

    Clear-Host
    Write-Host "Monitoring Active... (Broadcasting to GUI)" -ForegroundColor Gray
    Write-Host "CPU: $cpuUsage% | $cpuPower W"
    Write-Host "G1: $g1P W / $g1L W | $g1T C"
    Write-Host "G2: $g2P W / $g2L W | $g2T C"
    Write-Host "SYS: $totalSystem W"

    Start-Sleep -Seconds $interval
}
if ($port) { $port.Close() }
