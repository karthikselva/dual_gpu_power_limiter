@echo off
:: 390W is the card's hard ceiling (nvidia-smi power.max_limit), 30W above the
:: 360W stock default. Nothing above this will be accepted by the driver.
"C:\Windows\system32\nvidia-smi.exe" -pm 0
"C:\Windows\system32\nvidia-smi.exe" -i 0 -pl 390
