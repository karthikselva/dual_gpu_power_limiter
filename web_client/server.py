import asyncio
import socket
import os
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn
import json

# Store the latest telemetry data
latest_data = {
    "usage": 0, "cpuPwr": 0, "cpuTemp": 0,
    "g1Pwr": 0, "g1Temp": 0, "g1Limit": 0,
    "g2Pwr": 0, "g2Temp": 0, "g2Limit": 0,
    "sysPwr": 0, "peakCpu": 0, "peakG1": 0,
    "peakG2": 0, "peakSys": 0, "time": "00:00"
}

class TelemetryProtocol(asyncio.DatagramProtocol):
    def datagram_received(self, data, addr):
        global latest_data
        try:
            msg = data.decode("ascii")
            vals = msg.split(",")
            if len(vals) >= 15:
                latest_data = {
                    "usage": float(vals[0]), "cpuPwr": float(vals[1]), "cpuTemp": float(vals[2]),
                    "g1Pwr": float(vals[3]), "g1Temp": int(float(vals[4])), "g1Limit": float(vals[5]),
                    "g2Pwr": float(vals[6]), "g2Temp": int(float(vals[7])), "g2Limit": float(vals[8]),
                    "sysPwr": float(vals[9]), "peakCpu": float(vals[10]), "peakG1": float(vals[11]),
                    "peakG2": float(vals[12]), "peakSys": float(vals[13]), "time": vals[14]
                }
        except Exception as e:
            pass

async def start_udp_listener():
    loop = asyncio.get_running_loop()
    
    # Use port 9998 specifically for Web Client to avoid conflicts on Windows
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(('', 9998))
    except Exception as e:
        print(f"Socket bind failed on port 9998: {e}")
        return

    transport, protocol = await loop.create_datagram_endpoint(
        lambda: TelemetryProtocol(),
        sock=sock
    )
    print("UDP Listener started on port 9998 (Dedicated Web Stream)")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    task = asyncio.create_task(start_udp_listener())
    yield
    # Shutdown logic
    task.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/stream")
async def message_stream(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            data = json.dumps(latest_data)
            yield f"data: {data}\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Get absolute path to the static directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

if __name__ == "__main__":
    ip = get_ip()
    print(f"\n=======================================")
    print(f"Telemetry Web Server Active")
    print(f"Local URL: http://localhost:8000")
    print(f"iPhone URL: http://{ip}:8000")
    print(f"=======================================\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
