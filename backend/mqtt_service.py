"""
LoRaWAN MQTT Ingestion Service.

Subscribes to uplink topics, decodes Cayenne LPP payloads, computes latency & packet loss,
persists records to SQLite, and broadcasts real-time telemetry to WebSocket clients.
"""

import asyncio
import json
import logging
import time
from typing import Set, Optional
import paho.mqtt.client as mqtt

from core.cayenne_lpp import CayenneLPP
from core.models import DecodedPacket
from core.database import save_packet, record_metrics_snapshot, get_network_stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (Backend) %(message)s")
logger = logging.getLogger("MQTTService")


class MQTTIngestionService:
    """Consumes LoRaWAN packets from MQTT and handles real-time ingestion."""

    def __init__(self, host: str = "127.0.0.1", port: int = 1883, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.host = host
        self.port = port
        self.loop = loop
        self.client: Optional[mqtt.Client] = None
        self.ws_subscribers: Set[asyncio.Queue] = set()
        self.is_connected = False
        self._snapshot_task: Optional[asyncio.Task] = None

    def start(self, loop: asyncio.AbstractEventLoop):
        """Starts the MQTT consumer service."""
        self.loop = loop
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="lorawan-api-ingestor",
            protocol=mqtt.MQTTv311
        )

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        try:
            self.client.connect(self.host, self.port, keepalive=60)
            self.client.loop_start()
            logger.info(f"Connected ingestion service to MQTT broker {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Could not connect to MQTT broker: {e}")

        # Start periodic background metric snapshots
        self._snapshot_task = self.loop.create_task(self._periodic_snapshots())

    def stop(self):
        """Stops the MQTT service."""
        if self._snapshot_task:
            self._snapshot_task.cancel()

        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.client = None
        logger.info("MQTT ingestion service stopped.")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        logger.info(f"Subscribing to 'lorawan/+/uplink' (rc={rc})")
        self.is_connected = True
        client.subscribe("lorawan/+/uplink", qos=0)

    def _on_disconnect(self, client, userdata, disconnect_flags, rc, properties=None):
        self.is_connected = False
        logger.warning(f"Disconnected from MQTT broker (rc={rc})")

    def _on_message(self, client, userdata, msg):
        """Handles incoming MQTT uplink packet from simulated or real gateway."""
        try:
            recv_time = time.time()
            data = json.loads(msg.payload.decode("utf-8"))

            dev_eui = data["dev_eui"]
            f_cnt = data["f_cnt"]
            payload_hex = data["payload_hex"]
            sent_timestamp = data.get("sent_timestamp", recv_time)
            battery_v = data.get("battery_v", 3.3)

            # 1. Compute End-to-End Latency
            latency_ms = max(1.0, round((recv_time - sent_timestamp) * 1000.0, 2))

            # 2. Decode Cayenne LPP binary payload
            payload_bytes = bytes.fromhex(payload_hex)
            readings = CayenneLPP.decode(payload_bytes)

            decoded = DecodedPacket(
                dev_eui=dev_eui,
                f_cnt=f_cnt,
                f_port=data.get("f_port", 1),
                payload_hex=payload_hex,
                readings=readings,
                rssi=data.get("rssi", -80.0),
                snr=data.get("snr", 8.0),
                spreading_factor=data.get("spreading_factor", 7),
                toa_ms=data.get("toa_ms", 50.0),
                latency_ms=latency_ms,
                received_at=recv_time
            )

            # Schedule async database persistence and WebSocket dispatch
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self._process_packet(decoded, battery_v), self.loop)

        except Exception as e:
            logger.error(f"Error parsing MQTT packet: {e}")

    async def _process_packet(self, decoded: DecodedPacket, battery_v: float):
        """Asynchronously saves packet to SQL and broadcasts to WebSocket subscribers."""
        try:
            # Save to SQLite and compute packet loss gap
            res = await save_packet(decoded, battery_v)
            decoded.lost_before_this = res.get("lost_gap", 0)

            # Broadcast packet event to all connected dashboard websockets
            if self.ws_subscribers:
                ws_payload = {
                    "event": "new_packet",
                    "packet": decoded.model_dump()
                }
                msg_str = json.dumps(ws_payload)
                for q in list(self.ws_subscribers):
                    try:
                        q.put_nowait(msg_str)
                    except asyncio.QueueFull:
                        pass
        except Exception as e:
            logger.error(f"Error persisting packet: {e}")

    async def _periodic_snapshots(self):
        """Periodically saves metrics history and broadcasts global dashboard metrics."""
        while True:
            try:
                await asyncio.sleep(2.0)
                await record_metrics_snapshot()

                # Broadcast stats update over WebSockets
                if self.ws_subscribers:
                    stats = await get_network_stats()
                    ws_payload = {
                        "event": "network_stats",
                        "stats": stats.model_dump()
                    }
                    msg_str = json.dumps(ws_payload)
                    for q in list(self.ws_subscribers):
                        try:
                            q.put_nowait(msg_str)
                        except asyncio.QueueFull:
                            pass
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Snapshot error: {e}")

    def add_ws_subscriber(self, q: asyncio.Queue):
        self.ws_subscribers.add(q)

    def remove_ws_subscriber(self, q: asyncio.Queue):
        self.ws_subscribers.discard(q)


# Global ingestion instance
mqtt_service = MQTTIngestionService()
