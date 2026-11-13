"""
Simulated LoRaWAN Node with Cayenne LPP Payload Generator.
"""

import random
import time
from typing import Optional, Dict, Any, Tuple
from core.cayenne_lpp import CayenneLPP
from simulator.network_channel import LoRaChannel


class LoRaWANNode:
    """Represents a simulated IoT device running over LoRaWAN."""

    def __init__(self, node_id: int, channel: LoRaChannel):
        self.node_id = node_id
        self.dev_eui = f"A84041{node_id:010X}"
        self.app_eui = "70B3D57ED0000000"
        self.app_key = f"2B7E151628AED2A6ABF7158809CF4F{node_id:02X}"
        self.channel = channel

        self.f_cnt = 0
        self.f_port = 1

        # Device physical environment
        self.distance_m = random.uniform(80.0, 3200.0)
        # Select realistic Spreading Factor based on distance (Adaptive Data Rate simulation)
        if self.distance_m < 500:
            self.spreading_factor = 7
        elif self.distance_m < 1000:
            self.spreading_factor = 8
        elif self.distance_m < 1800:
            self.spreading_factor = 9
        elif self.distance_m < 2500:
            self.spreading_factor = 10
        else:
            self.spreading_factor = random.choice([11, 12])

        self.bandwidth_khz = 125
        self.frequency_hz = random.choice(self.channel.frequencies)

        # Dynamic sensor states
        self.temperature = round(random.uniform(19.0, 26.0), 1)
        self.humidity = round(random.uniform(45.0, 65.0), 1)
        self.barometer = round(random.uniform(1011.0, 1015.0), 1)
        self.battery_v = round(random.uniform(3.2, 3.6), 2)
        self.illuminance = random.randint(150, 800)

        # Geographic coordinates centered around a city (e.g. Madrid / Barcelona / CDMX)
        base_lat = 40.4168
        base_lon = -3.7038
        self.latitude = base_lat + (random.uniform(-0.02, 0.02))
        self.longitude = base_lon + (random.uniform(-0.02, 0.02))
        self.altitude = round(random.uniform(620.0, 680.0), 1)

    def _update_sensors(self):
        """Simulates environmental fluctuations."""
        self.temperature = round(self.temperature + random.uniform(-0.3, 0.3), 1)
        self.temperature = max(-10.0, min(50.0, self.temperature))

        self.humidity = round(self.humidity + random.uniform(-0.5, 0.5), 1)
        self.humidity = max(20.0, min(95.0, self.humidity))

        self.barometer = round(self.barometer + random.uniform(-0.1, 0.1), 1)
        self.battery_v = max(2.8, round(self.battery_v - 0.00005, 3))
        self.illuminance = max(0, min(2000, self.illuminance + random.randint(-20, 20)))

    def generate_cayenne_payload(self) -> bytes:
        """Encodes current sensor telemetry into Cayenne LPP format."""
        self._update_sensors()
        lpp = CayenneLPP()
        # Channel 1: Temperature
        lpp.add_temperature(1, self.temperature)
        # Channel 2: Relative Humidity
        lpp.add_humidity(2, self.humidity)
        # Channel 3: Barometric Pressure
        lpp.add_barometer(3, self.barometer)
        # Channel 4: Battery Voltage (Analog Input)
        lpp.add_analog_input(4, self.battery_v)
        # Channel 5: Illuminance
        lpp.add_luminosity(5, self.illuminance)
        # Channel 6: GPS (every 5 packets to save airtime)
        if self.f_cnt % 5 == 0:
            lpp.add_gps(6, self.latitude, self.longitude, self.altitude)

        return lpp.buffer

    def transmit(self) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Executes a transmission cycle:
        1. Encodes Cayenne LPP payload.
        2. Calculates radio link parameters (RSSI, SNR, ToA).
        3. Evaluates channel loss.
        4. Increments frame counter (fcnt).
        Returns: (packet_dict or None, is_dropped)
        """
        sent_time = time.time()
        payload_bytes = self.generate_cayenne_payload()
        payload_hex = payload_bytes.hex()
        current_fcnt = self.f_cnt

        # Increment frame counter for every transmit attempt (essential for loss detection!)
        self.f_cnt += 1

        # Channel RF physics
        rssi, snr = self.channel.simulate_rf(self.distance_m)
        toa_ms = self.channel.calculate_toa_ms(
            payload_size_bytes=len(payload_bytes),
            sf=self.spreading_factor,
            bw_khz=self.bandwidth_khz
        )

        is_lost = self.channel.is_packet_lost(snr, self.spreading_factor)

        if is_lost:
            # Packet was dropped in the wireless medium; never reaches the gateway/broker!
            return None, True

        # Successful transmission packet envelope
        packet = {
            "dev_eui": self.dev_eui,
            "app_eui": self.app_eui,
            "f_cnt": current_fcnt,
            "f_port": self.f_port,
            "payload_hex": payload_hex,
            "frequency_hz": self.frequency_hz,
            "spreading_factor": self.spreading_factor,
            "bandwidth_khz": self.bandwidth_khz,
            "rssi": rssi,
            "snr": snr,
            "toa_ms": toa_ms,
            "gateway_id": "GW-ESP32-EU868-01",
            "sent_timestamp": sent_time,
            "battery_v": self.battery_v
        }

        return packet, False
