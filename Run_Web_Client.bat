@echo off
title Telemetry Web Client Server
echo Starting Telemetry Web Client Server...
echo Make sure you have installed requirements: pip install -r pc_side/requirements.txt
python web_client/server.py
pause
