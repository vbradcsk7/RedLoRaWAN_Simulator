# Simulador de Red LoRaWAN y dashboard en Tiempo Real

Simulador integral de red de sensores **LoRaWAN** de alta concurrencia con codificación binaria **Cayenne LPP**, broker **MQTT**, procesamiento e ingestión asíncrona en base de datos **SQL (SQLite)** y **Dashboard Web** con métricas en tiempo real de **pérdida de paquetes** y **latencia end-to-end**.

---

## Arquitectura del Sistema

┌────────────────────────────────────────────────────────┐
│               Simulador LoRaWAN (Asyncio)              │
│  [Nodo 001] [Nodo 002] ... [Nodo 100+]                 │
│  - Sensores: Temp, Humedad, Presión, Batería, GPS      │
│  - Frame Counter (f_cnt) secuencial                    │
│  - Codificador Binario Cayenne LPP                     │
│  - Modelo RF: Path Loss, SNR, RSSI, ToA (Semtech)      │
└──────────────────────────┬─────────────────────────────┘
                           │ Publica uplink en lorawan/{dev_eui}/uplink
                           ▼
┌────────────────────────────────────────────────────────┐
│                Broker MQTT (Mosquitto)                 │
│                 Puerto: 1883                           │
└──────────────────────────┬─────────────────────────────┘
                           │ Suscripción MQTT
                           ▼
┌────────────────────────────────────────────────────────┐
│             API de Ingestión (FastAPI Backend)         │
│  - Decodificador Cayenne LPP (Binary -> Telemetría)    │
│  - Detección de pérdida por salto de f_cnt (Lost Gaps) │
│  - Cálculo de Latencia (Tiempo en Aire + Backhaul)     │
│  - Persistencia Asíncrona en SQL (SQLite)              │
│  - Servidor WebSocket (Transmisión en subsegundo)      │
└──────────────────────────┬─────────────────────────────┘
                           │ WebSocket /ws + REST API
                           ▼
┌────────────────────────────────────────────────────────┐
│          Dashboard Web en Tiempo Real (HTML5/JS)       │
│  - Tarjetas KPI: % Pérdida, Latencia media, Throughput │
│  - Gráficos interactivos Chart.js                      │
│  - Feed de tramas decodificadas en vivo                │
│  - Registro de nodos y consola de control interactiva  │
└────────────────────────────────────────────────────────┘

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
├── config/
│   └── mosquitto.conf          # Configuración del Broker Mosquitto
├── core/
│   ├── __init__.py
│   ├── cayenne_lpp.py          # Codificador y Decodificador Cayenne LPP
│   ├── database.py             # Motor SQLite asíncrono (aiosqlite)
│   └── models.py               # Modelos de datos Pydantic y LoRaWAN
├── simulator/
│   ├── __init__.py
│   ├── node.py                 # Dispositivo LoRaWAN simulado con sensores
│   ├── network_channel.py      # Modelo de propagación RF, Time on Air y pérdidas
│   └── simulator.py            # Motor de simulación concurrente (100+ nodos)
├── backend/
│   ├── __init__.py
│   ├── mqtt_service.py         # Consumidor MQTT, cálculo de métricas y WebSocket
│   └── api.py                  # Endpoints REST y servidor FastAPI
├── web/
│   └── static/
│       ├── index.html          # Panel de control web moderno en modo oscuro
│       └── app.js              # Cliente WebSocket, Chart.js y tabla en tiempo real
├── scripts/
│   ├── run_all.py              # Orquestador todo-en-uno
│   └── test_cayenne.py         # Tests unitarios de Cayenne LPP y ToA
├── requirements.txt
└── README.md


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

