# Ultimate Power & Temp Monitor v5.4 - Serial Edition (Dual GPU + Limits)
$ErrorActionPreference = "SilentlyContinue"

# Force period as decimal separator regardless of PC locale
[threading.thread]::CurrentThread.CurrentCulture = [cultureinfo]::InvariantCulture

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

# --- PEAK TRACKING (PC SIDE) ---
$peakCpuPwr = 0.0
$peakG1Pwr = 0.0
$peakG2Pwr = 0.0
$peakSysPwr = 0.0

while($true) {
    # --- GPU DATA ---
    $gpuMetrics = @()
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

    # --- UPDATE PEAKS ---
    if ($cpuPower -gt $peakCpuPwr) { $peakCpuPwr = $cpuPower }
    if ($g1P -gt $peakG1Pwr) { $peakG1Pwr = $g1P }
    if ($g2P -gt $peakG2Pwr) { $peakG2Pwr = $g2P }

    # --- TOTALS ---
    $gpuTotalPwr = $g1P + $g2P
    $totalSystem = $gpuTotalPwr + $cpuPower + $moboEstimate
    if ($totalSystem -gt $peakSysPwr) { $peakSysPwr = $totalSystem }

    $timestamp = Get-Date -Format "HH:mm"

    # --- SEND TO ARDUINO & GUI ---
    # New Format: Usage,CpuPwr,CpuTemp,G1P,G1T,G1L,G2P,G2T,G2L,SysPwr,PeakCpu,PeakG1,PeakG2,PeakSys,Time (15 values)
    # Using Invariant Culture strings to ensure '.' for decimals
    $dataString = "{0},{1:F1},{2:F1},{3:F1},{4},{5:F1},{6:F1},{7},{8:F1},{9:F1},{10:F1},{11:F1},{12:F1},{13:F1},{14}" -f `
        $cpuUsage, $cpuPower, $cpuTemp, $g1P, $g1T, $g1L, $g2P, $g2T, $g2L, $totalSystem, `
        $peakCpuPwr, $peakG1Pwr, $peakG2Pwr, $peakSysPwr, $timestamp
    
    if ($port -and $port.IsOpen) {
        $port.WriteLine($dataString)
    }

    # UDP BROADCAST FOR GUI & CORE INK
    try {
        $udpClient = New-Object System.Net.Sockets.UdpClient
        $byteData = [System.Text.Encoding]::ASCII.GetBytes($dataString)
        # Send to local GUI
        $null = $udpClient.Send($byteData, $byteData.Length, "127.0.0.1", 9999)
        # Send to local Web Client
        $null = $udpClient.Send($byteData, $byteData.Length, "127.0.0.1", 9998)
        # Send to Network Broadcast for Core Ink
        $null = $udpClient.Send($byteData, $byteData.Length, "255.255.255.255", 9999)
        $udpClient.Close()
    } catch {}

    Clear-Host
    Write-Host "Monitoring Active... (Broadcasting to GUI)" -ForegroundColor Gray
    Write-Host "CPU: $cpuUsage% | $cpuPower W (Peak: $peakCpuPwr W)"
    Write-Host "G1: $g1P W / $g1L W | $g1T C (Peak: $peakG1Pwr W)"
    Write-Host "G2: $g2P W / $g2L W | $g2T C (Peak: $peakG2Pwr W)"
    Write-Host "SYS: $totalSystem W (Peak: $peakSysPwr W)"

    Start-Sleep -Seconds $interval
}
if ($port) { $port.Close() }
