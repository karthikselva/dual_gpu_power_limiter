# Test-Simulator.ps1
$pio = "C:\Users\karth\.platformio\penv\Scripts\platformio.exe"
$toml = "wokwi.toml"

Write-Host "--- 1. Building Unit Tests for Wokwi ---" -ForegroundColor Cyan
& $pio test -e test_simulator

# Updated path for test_simulator environment
$testPath = ".pio/build/test_simulator/test/test_parser/firmware.hex"
$testElf = ".pio/build/test_simulator/test/test_parser/firmware.elf"

if (Test-Path $testPath) {
    Write-Host "--- 2. Switching Wokwi to Test Mode ---" -ForegroundColor Yellow
    $content = @"
[wokwi]
version = 1
firmware = '$testPath'
elf = '$testElf'
"@
    Set-Content -Path $toml -Value $content
    
    Write-Host "--- SUCCESS ---" -ForegroundColor Green
    Write-Host "The simulator is now in TEST MODE."
    Write-Host "1. Press F1 in VS Code"
    Write-Host "2. Select 'Wokwi: Start Simulator'"
    Write-Host "3. Check the Serial Monitor (bottom of sim) for results."
    Write-Host ""
    Write-Host "Press any key to revert back to APP MODE..."
    $null = [Console]::ReadKey()

    Write-Host "--- 3. Reverting Wokwi to App Mode ---" -ForegroundColor Cyan
    $appContent = @"
[wokwi]
version = 1
firmware = '.pio/build/megaatmega2560/firmware.hex'
elf = '.pio/build/megaatmega2560/firmware.elf'
"@
    Set-Content -Path $toml -Value $appContent
    Write-Host "Back to App Mode."
} else {
    Write-Host "FAILED: Test firmware not found. Did the build fail?" -ForegroundColor Red
}
