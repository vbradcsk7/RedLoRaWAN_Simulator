# Simulador de Red LoRaWAN y dashboard en Tiempo Real

Simulador integral de red de sensores **LoRaWAN** de alta concurrencia con codificación binaria **Cayenne LPP**, broker **MQTT**, procesamiento e ingestión asíncrona en base de datos **SQL (SQLite)** y **Dashboard Web** con métricas en tiempo real de **pérdida de paquetes** y **latencia end-to-end**.

---

## Arquitectura del Sistema
flowchart TB
    subgraph SIM["📡 SIMULADOR LoRaWAN · Asyncio"]
        direction TB
        N["Nodos IoT · 001 → 100+"]

        S["Sensores<br/>🌡️ Temperatura · 💧 Humedad<br/>Presión · 🔋 Batería · 📍 GPS"]

        F["Frame Counter (f_cnt)<br/>Secuencial por dispositivo"]

        LPP["Codificador binario<br/>Cayenne LPP"]

        RF["Modelo RF · Semtech<br/>Path Loss · SNR · RSSI · ToA"]

        N --> S
        N --> F
        S --> LPP
        F --> LPP
        LPP --> RF
    end

    MQTT["📨 BROKER MQTT · Mosquitto<br/>Puerto 1883<br/>Topic: lorawan/{dev_eui}/uplink"]

    subgraph API["⚙️ BACKEND · FastAPI"]
        direction TB
        DEC["Decodificador Cayenne LPP<br/>Binary → Telemetría"]

        LOSS["Detección de pérdida<br/>Saltos de f_cnt · Lost Gaps"]

        LAT["Cálculo de latencia<br/>Tiempo en Aire + Backhaul"]

        DB[("🗄️ SQLite<br/>Persistencia asíncrona")]

        WS["WebSocket · /ws<br/>Transmisión en tiempo real"]

        DEC --> LOSS
        DEC --> LAT
        LOSS --> DB
        LAT --> DB
        DEC --> WS
    end

    subgraph DASH["📊 DASHBOARD WEB · HTML5 / JavaScript"]
        direction TB
        KPI["KPIs en tiempo real<br/>Pérdida · Latencia media · Throughput"]

        CHART["Gráficos interactivos<br/>Chart.js"]

        FEED["Feed de tramas<br/>Decodificadas en vivo"]

        CTRL["Registro de nodos<br/>Consola de control interactiva"]
    end

    SIM -->|"Uplink LoRaWAN simulado"| MQTT
    MQTT -->|"Suscripción MQTT"| API
    WS -->|"WebSocket /ws + REST API"| DASH

    style SIM fill:#173B57,stroke:#38BDF8,color:#FFFFFF
    style API fill:#183D35,stroke:#34D399,color:#FFFFFF
    style DASH fill:#382B58,stroke:#A78BFA,color:#FFFFFF
    style MQTT fill:#55401C,stroke:#FBBF24,color:#FFFFFF

---

## Ejecución Rápida (1 Comando)

Para iniciar todos los componentes (Broker MQTT + Servidor Web + Simulador con 100 nodos activos):

bash
./venv/bin/python scripts/run_all.py

Una vez iniciado, abre en tu navegador:
-  **Dashboard Web en Tiempo Real**: [http://localhost:8000](http://localhost:8000)
-  **Documentación Interactiva Swagger / OpenAPI**: [http://localhost:8000/docs](http://localhost:8000/docs)
-  **Broker MQTT**: `localhost:1883`

---

##  Estructura del Proyecto

proyecto/
│
├── ⚙️ config/
│   └── mosquitto.conf          # Configuración del broker Mosquitto
│
├── 🧠 core/
│   ├── __init__.py
│   ├── cayenne_lpp.py          # Codificador y decodificador Cayenne LPP
│   ├── database.py             # Motor SQLite asíncrono (aiosqlite)
│   └── models.py               # Modelos Pydantic y LoRaWAN
│
├── 📡 simulator/
│   ├── __init__.py
│   ├── node.py                 # Dispositivos LoRaWAN simulados y sensores
│   ├── network_channel.py      # Propagación RF, Time on Air y pérdidas
│   └── simulator.py            # Motor concurrente (100+ nodos)
│
├── 🚀 backend/
│   ├── __init__.py
│   ├── mqtt_service.py         # Consumidor MQTT, métricas y WebSocket
│   └── api.py                  # API REST y servidor FastAPI
│
├── 🌐 web/
│   └── static/
│       ├── index.html          # Dashboard web en modo oscuro
│       └── app.js              # Cliente WebSocket, Chart.js y telemetría
│
├── 🧪 scripts/
│   ├── run_all.py              # Orquestador de ejecución completa
│   └── test_cayenne.py         # Tests de Cayenne LPP y Time on Air
│
├── 📦 requirements.txt         # Dependencias del proyecto
└── 📖 README.md                # Documentación principal


---

## ¿Cómo se Calculan las Métricas?

### 1. Detección y Tasa de Pérdida de Paquetes
En redes LoRaWAN reales, cada dispositivo cuenta con un contador de tramas (`f_cnt`) que se incrementa en cada intento de transmisión:
- Si el nodo transmite las tramas `10`, `11`, `12`, pero debido a interferencia o desvanecimiento del canal la trama `11` no llega a la pasarela, el backend recibe:
  - Trama `10`
  - Trama `12`
- El backend detecta el salto: $\Delta f\_cnt = 12 - 10 - 1 = 1 \text{ trama perdida}$.
- La tasa de pérdida global y por nodo se computa como:
  $$\text{Tasa de Pérdida (\%)} = \frac{\text{Tramas Perdidas}}{\text{Tramas Esperadas}} \times 100\%$$

### 2. Latencia y Tiempo en el Aire (Time-on-Air - ToA)
- Cada trama incluye la marca de tiempo de generación en nanosegundos y los parámetros de modulación LoRa (Spreading Factor SF7–SF12, ancho de banda 125 kHz, longitud de preámbulo).
- Se computa el **ToA** físico exacto según las ecuaciones oficiales de Semtech SX1276.
- La latencia mostrada corresponde al retardo total de extremo a extremo:
  $$\text{Latencia} = T_{\text{recepción}} - T_{\text{emisión}} = \text{ToA} + T_{\text{propagación}} + T_{\text{backhaul}}$$

---

## Consola de Control en el Dashboard

El panel web te permite ajustar parámetros en caliente sin reiniciar el script:
- **Número de Nodos**: desde 10 hasta 500 dispositivos concurrentes.
- **Intervalo de Envío**: de 1.0s (alta carga) a 15.0s.
- **Probabilidad de Pérdida**: de 0% (enlace ideal) a 40% (canal altamente degradado).
- **Botón Pausar / Reanudar**: para pruebas paso a paso.
- **Botón Limpiar DB**: para reiniciar el histórico de métricas.

---

## Ejecución de Tests

Para verificar el codificador Cayenne LPP y el cálculo físico de ToA:

bash
./venv/bin/python scripts/test_cayenne.py

