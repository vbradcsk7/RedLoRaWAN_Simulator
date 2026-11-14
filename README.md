LoRaWAN Network Simulator and Real-Time Dashboard

A comprehensive, high-concurrency LoRaWAN sensor network simulator featuring Cayenne LPP binary encoding, an MQTT broker, asynchronous processing and ingestion into an SQL (SQLite) database, and a Web Dashboard with real-time metrics for packet loss and end-to-end latency.

System Architecture
mermaid
flowchart TB
    subgraph SIM["📡 LoRaWAN SIMULATOR · Asyncio"]
        direction TB
        N["IoT Nodes · 001 → 100+"]

        S["Sensors<br/>🌡️ Temperature · 💧 Humidity<br/>Pressure · 🔋 Battery · 📍 GPS"]

        F["Frame Counter (f_cnt)<br/>Sequential per device"]

        LPP["Binary Encoder<br/>Cayenne LPP"]

        RF["RF Model · Semtech<br/>Path Loss · SNR · RSSI · ToA"]

        N --> S
        N --> F
        S --> LPP
        F --> LPP
        LPP --> RF
    end

    MQTT["📨 MQTT BROKER · Mosquitto<br/>Port 1883<br/>Topic: lorawan/{dev_eui}/uplink"]

    subgraph API["⚙️ BACKEND · FastAPI"]
        direction TB
        DEC["Cayenne LPP Decoder<br/>Binary → Telemetry"]

        LOSS["Packet Loss Detection<br/>f_cnt Gaps · Lost Frames"]

        LAT["Latency Calculation<br/>Time-on-Air + Backhaul"]

        DB[("🗄️ SQLite<br/>Asynchronous Persistence")]

        WS["WebSocket · /ws<br/>Real-Time Data Streaming"]

        DEC --> LOSS
        DEC --> LAT
        LOSS --> DB
        LAT --> DB
        DEC --> WS
    end

    subgraph DASH["📊 WEB DASHBOARD · HTML5 / JavaScript"]
        direction TB
        KPI["Real-Time KPIs<br/>Packet Loss · Average Latency · Throughput"]

        CHART["Interactive Charts<br/>Chart.js"]

        FEED["Frame Feed<br/>Live Decoded Telemetry"]

        CTRL["Node Management<br/>Interactive Control Console"]
    end

    SIM -->|"Simulated LoRaWAN Uplink"| MQTT
    MQTT -->|"MQTT Subscription"| API
    WS -->|"WebSocket /ws + REST API"| DASH

    style SIM fill:#173B57,stroke:#38BDF8,color:#FFFFFF
    style API fill:#183D35,stroke:#34D399,color:#FFFFFF
    style DASH fill:#382B58,stroke:#A78BFA,color:#FFFFFF
    style MQTT fill:#55401C,stroke:#FBBF24,color:#FFFFFF

Quick Start (One Command)

To start all components (MQTT Broker + Web Server + Simulator with 100 active nodes):

bash
./venv/bin/python scripts/run_all.py


Once the system is running, open your browser:

Real-Time Web Dashboard: http://localhost:8000
Interactive Swagger / OpenAPI Documentation: http://localhost:8000/docs
MQTT Broker: localhost:1883
Project Structure
text
project/
│
├── ⚙️ config/
│   └── mosquitto.conf          # Mosquitto broker configuration
│
├── 🧠 core/
│   ├── __init__.py
│   ├── cayenne_lpp.py          # Cayenne LPP encoder and decoder
│   ├── database.py             # Asynchronous SQLite engine (aiosqlite)
│   └── models.py               # Pydantic and LoRaWAN models
│
├── 📡 simulator/
│   ├── __init__.py
│   ├── node.py                 # Simulated LoRaWAN devices and sensors
│   ├── network_channel.py      # RF propagation, Time-on-Air and packet loss
│   └── simulator.py            # Concurrent simulation engine (100+ nodes)
│
├── 🚀 backend/
│   ├── __init__.py
│   ├── mqtt_service.py         # MQTT consumer, metrics and WebSocket
│   └── api.py                  # REST API and FastAPI server
│
├── 🌐 web/
│   └── static/
│       ├── index.html          # Dark-mode web dashboard
│       └── app.js              # WebSocket client, Chart.js and telemetry
│
├── 🧪 scripts/
│   ├── run_all.py              # Full system execution orchestrator
│   └── test_cayenne.py         # Cayenne LPP and Time-on-Air tests
│
├── 📦 requirements.txt         # Project dependencies
└── 📖 README.md                # Main documentation

How Are the Metrics Calculated?
1. Packet Loss Detection and Rate

In real LoRaWAN networks, each device maintains a frame counter (f_cnt) that increments with every transmission:

If a node transmits frames 10, 11, and 12, but frame 11 fails to reach the gateway due to interference or channel fading, the backend receives:
Frame 10
Frame 12
The backend detects the gap:
Δ
𝑓
_
𝑐
𝑛
𝑡
=
12
−
10
−
1
=
1
 lost frame
The global and per-node packet loss rate is calculated as follows:
Packet Loss Rate (%)
=
Lost Frames
Expected Frames
×
100
%
2. Latency and Time-on-Air (ToA)
Each frame includes its generation timestamp in nanoseconds and the LoRa modulation parameters (Spreading Factor SF7–SF12, bandwidth of 125 kHz, and preamble length).
The exact physical Time-on-Air (ToA) is calculated using the official Semtech SX1276 equations.
The displayed latency represents the total end-to-end delay:

[ \text{Latency} = T_{\text{reception}} - T_{\text{transmission}} = \text{ToA} + T_{\text{propagation}} + T_{\text{backhaul}}
