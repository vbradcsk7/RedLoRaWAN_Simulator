#!/usr/bin/env python3
"""
Orchestrator script:
Starts Mosquitto Broker + FastAPI Server + LoRaWAN Multi-Node Simulator in a single command.
"""

import os
import sys
import time
import subprocess
import signal

MOSQUITTO_BIN = "/opt/homebrew/opt/mosquitto/sbin/mosquitto"
CONFIG_PATH = os.path.abspath("config/mosquitto.conf")

processes = []


def signal_handler(sig, frame):
    print("\n[!] Shutting down all services...")
    for p in processes:
        try:
            p.terminate()
            p.wait(timeout=2)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
    print("[*] All services stopped cleanly.")
    sys.exit(0)


def check_port(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("=" * 70)
    print("  🚀 LORAWAN NETWORK SIMULATOR + REAL-TIME DASHBOARD")
    print("=" * 70)

    # 1. Start or verify Mosquitto MQTT Broker
    if check_port(1883):
        print("[✓] An MQTT broker is already running on port 1883.")
    else:
        if os.path.exists(MOSQUITTO_BIN):
            print(f"[*] Starting Mosquitto broker ({MOSQUITTO_BIN})...")
            p_mosq = subprocess.Popen(
                [MOSQUITTO_BIN, "-c", CONFIG_PATH],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            processes.append(p_mosq)
            time.sleep(1)
            if check_port(1883):
                print("[✓] Mosquitto broker started successfully on 127.0.0.1:1883")
            else:
                print("[!] Warning: Mosquitto could not be confirmed on port 1883.")
        else:
            print(f"[!] Mosquitto binary not found at {MOSQUITTO_BIN}. Please ensure an MQTT broker is running on port 1883.")

    # 2. Start FastAPI Backend & Web Dashboard
    print("[*] Starting FastAPI Backend & Web Dashboard on http://127.0.0.1:8000 ...")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()

    p_web = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"],
        env=env
    )
    processes.append(p_web)

    time.sleep(2)
    print("\n" + "=" * 70)
    print("  🌟 SISTEMA LORAWAN INICIADO CON ÉXITO")
    print("  👉 Dashboard Web:       http://localhost:8000")
    print("  👉 API REST / Docs:     http://localhost:8000/docs")
    print("  👉 Broker MQTT:         mqtt://127.0.0.1:1883")
    print("  👉 Nodos Activos:       100 nodos LoRaWAN transmitiendo")
    print("=" * 70 + "\n")
    print("Presiona Ctrl+C para detener todos los servicios.\n")

    p_web.wait()


if __name__ == "__main__":
    main()
