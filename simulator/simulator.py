"""
Multi-Node LoRaWAN Network Simulator Engine.

Supports:
- Hundreds of concurrently active nodes.
- MQTT publishing of Cayenne LPP frames.
- Dynamic runtime configuration (loss probability, node count, transmission rate).
- CLI and Programmatic API interface.
"""

import asyncio
import json
import logging
import random
import time
from typing import List, Optional
import paho.mqtt.client as mqtt

from simulator.node import LoRaWANNode
from simulator.network_channel import LoRaChannel
from core.models import SimulatorConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (Simulator) %(message)s")
logger = logging.getLogger("LoRaSimulator")


class LoRaWANSimulator:
    """Orchestrates hundreds of simulated LoRaWAN nodes."""

    def __init__(
        self,
        mqtt_host: str = "127.0.0.1",
        mqtt_port: int = 1883,
        config: Optional[SimulatorConfig] = None
    ):
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.config = config or SimulatorConfig(num_nodes=100, interval_seconds=5.0, loss_probability=0.06)

        self.channel = LoRaChannel(loss_probability=self.config.loss_probability)
        self.nodes: List[LoRaWANNode] = []
        self._is_running = False
        self._mqtt_client: Optional[mqtt.Client] = None
        self._tasks: List[asyncio.Task] = []

        # Local stats counters
        self.simulated_transmissions = 0
        self.simulated_drops = 0
        self.simulated_sent = 0

        self._setup_nodes()

    def _setup_nodes(self):
        """Initializes the node pool based on configured count."""
        self.nodes = [LoRaWANNode(node_id=i + 1, channel=self.channel) for i in range(self.config.num_nodes)]
        logger.info(f"Initialized {len(self.nodes)} simulated LoRaWAN nodes.")

    def set_config(self, num_nodes: Optional[int] = None, interval: Optional[float] = None, loss: Optional[float] = None):
        """Dynamically updates simulator parameters during runtime."""
        if loss is not None:
            self.config.loss_probability = max(0.0, min(1.0, loss))
            self.channel.loss_probability = self.config.loss_probability
            logger.info(f"Updated loss probability to: {self.config.loss_probability * 100:.1f}%")

        if interval is not None:
            self.config.interval_seconds = max(0.5, interval)
            logger.info(f"Updated transmission interval to: {self.config.interval_seconds:.1f}s")

        if num_nodes is not None and num_nodes != len(self.nodes):
            old_count = len(self.nodes)
            self.config.num_nodes = max(1, num_nodes)
            if self.config.num_nodes > old_count:
                # Add extra nodes
                for i in range(old_count, self.config.num_nodes):
                    self.nodes.append(LoRaWANNode(node_id=i + 1, channel=self.channel))
            else:
                # Truncate
                self.nodes = self.nodes[:self.config.num_nodes]
            logger.info(f"Resized active nodes pool from {old_count} to {len(self.nodes)} nodes.")

    def _connect_mqtt(self):
        """Initializes and connects MQTT client."""
        client_id = f"lora-simulator-{random.randint(1000, 9999)}"
        self._mqtt_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv311
        )

        try:
            self._mqtt_client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
            self._mqtt_client.loop_start()
            logger.info(f"Connected simulator MQTT publisher to {self.mqtt_host}:{self.mqtt_port}")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker {self.mqtt_host}:{self.mqtt_port} - {e}")
            # Keep client but don't crash startup

    def publish_packet(self, packet: dict):
        """Publishes uplink packet to MQTT broker."""
        if not self._mqtt_client:
            return

        topic = f"lorawan/{packet['dev_eui']}/uplink"
        payload_str = json.dumps(packet)
        self._mqtt_client.publish(topic, payload_str, qos=0)
        self.simulated_sent += 1

    async def _node_loop(self, node: LoRaWANNode):
        """Individual asynchronous routine for each node."""
        # Initial jitter to desynchronize nodes
        await asyncio.sleep(random.uniform(0.1, self.config.interval_seconds))

        while self._is_running:
            try:
                self.simulated_transmissions += 1
                packet, dropped = node.transmit()

                if dropped:
                    self.simulated_drops += 1
                else:
                    # Simulate realistic airtime & propagation delay before arrival at broker
                    sim_delay_ms = self.channel.simulate_latency_ms(packet["toa_ms"])
                    await asyncio.sleep(sim_delay_ms / 1000.0)
                    self.publish_packet(packet)

                # Wait for next periodic uplink with natural random jitter (+/- 20%)
                jitter = random.uniform(-0.2, 0.2) * self.config.interval_seconds
                sleep_duration = max(0.5, self.config.interval_seconds + jitter)
                await asyncio.sleep(sleep_duration)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in node {node.dev_eui}: {e}")
                await asyncio.sleep(1.0)

    async def start(self):
        """Starts the multi-node simulation loop."""
        if self._is_running:
            logger.warning("Simulator is already running.")
            return

        logger.info(f"Starting LoRaWAN simulator with {len(self.nodes)} nodes...")
        self._is_running = True
        self.config.running = True
        self._connect_mqtt()

        # Launch an async task for each node
        self._tasks = [asyncio.create_task(self._node_loop(node)) for node in self.nodes]

    async def stop(self):
        """Gracefully stops the simulation."""
        if not self._is_running:
            return

        logger.info("Stopping LoRaWAN simulator...")
        self._is_running = False
        self.config.running = False

        for task in self._tasks:
            task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        if self._mqtt_client:
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()
            self._mqtt_client = None

        logger.info("Simulator stopped.")

    @property
    def is_running(self) -> bool:
        return self._is_running


# Global simulator instance for FastAPI dependency injection
global_simulator: Optional[LoRaWANSimulator] = None


def get_simulator() -> LoRaWANSimulator:
    global global_simulator
    if global_simulator is None:
        global_simulator = LoRaWANSimulator()
    return global_simulator


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LoRaWAN Network Simulator")
    parser.add_argument("--nodes", type=int, default=100, help="Number of nodes to simulate (e.g. 100)")
    parser.add_argument("--interval", type=float, default=4.0, help="Transmission interval in seconds")
    parser.add_argument("--loss", type=float, default=0.07, help="Channel loss probability (0.0 - 1.0)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="MQTT Broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT Broker port")
    args = parser.parse_args()

    cfg = SimulatorConfig(num_nodes=args.nodes, interval_seconds=args.interval, loss_probability=args.loss)
    sim = LoRaWANSimulator(mqtt_host=args.host, mqtt_port=args.port, config=cfg)

    async def main():
        await sim.start()
        print(f"[*] Simulating {args.nodes} LoRaWAN nodes... Press Ctrl+C to stop.")
        try:
            while True:
                await asyncio.sleep(5)
                drop_pct = (sim.simulated_drops / max(1, sim.simulated_transmissions)) * 100.0
                print(f"[Sim Stats] Attempts: {sim.simulated_transmissions} | Sent: {sim.simulated_sent} | Dropped: {sim.simulated_drops} ({drop_pct:.1f}%)")
        except KeyboardInterrupt:
            await sim.stop()

    asyncio.run(main())
