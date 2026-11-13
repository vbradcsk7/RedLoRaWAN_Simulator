"""
Physical LoRa Radio Channel and Gateway Simulation Model.

Implements:
- Semtech Time-on-Air (ToA) calculation.
- Log-distance path loss, RSSI, and SNR models.
- Channel packet loss simulation (fading, collisions, and artificial injection).
- Network transport delay and jitter.
"""

import math
import random
from typing import Tuple


class LoRaChannel:
    """Simulates physical wireless propagation and packet reception."""

    def __init__(self, loss_probability: float = 0.05, base_jitter_ms: float = 25.0):
        self.loss_probability = loss_probability
        self.base_jitter_ms = base_jitter_ms
        # EU868 standard frequencies
        self.frequencies = [
            868100000, 868300000, 868500000,
            867100000, 867300000, 867500000, 867700000, 867900000
        ]

    def calculate_toa_ms(
        self,
        payload_size_bytes: int,
        sf: int = 7,
        bw_khz: int = 125,
        cr: int = 1,          # 1 = 4/5, 2 = 4/6, etc.
        preamble_len: int = 8,
        explicit_header: bool = True,
        crc_enabled: bool = True,
        low_data_rate_opt: bool = False
    ) -> float:
        """
        Exact Semtech SX1276 LoRa Time-on-Air (ToA) calculation in milliseconds.
        """
        bw_hz = bw_khz * 1000.0
        t_sym_s = (2 ** sf) / bw_hz
        t_preamble_s = (preamble_len + 4.25) * t_sym_s

        ih = 0 if explicit_header else 1
        crc = 1 if crc_enabled else 0
        de = 1 if (sf >= 11 and bw_khz == 125) or low_data_rate_opt else 0

        numerator = 8 * payload_size_bytes - 4 * sf + 28 + 16 * crc - 20 * ih
        denominator = 4 * (sf - 2 * de)

        if denominator <= 0:
            term = 0
        else:
            term = math.ceil(max(0, numerator) / denominator)

        payload_symbols = 8 + max(0, term * (cr + 4))
        t_payload_s = payload_symbols * t_sym_s

        total_toa_ms = (t_preamble_s + t_payload_s) * 1000.0
        return round(total_toa_ms, 2)

    def simulate_rf(self, distance_m: float, tx_power_dbm: float = 14.0) -> Tuple[float, float]:
        """
        Calculates RSSI and SNR using Log-Distance Path Loss model.
        PL(d) = PL(d0) + 10 * n * log10(d/d0) + X_sigma
        """
        d0 = 1.0  # reference 1 meter
        path_loss_exponent = 2.8  # suburban / urban environment
        shadowing_sigma = 3.5     # log-normal shadowing variation

        distance = max(10.0, distance_m)
        pl_d0 = 40.0  # ~40 dB loss at 1m for 868MHz
        path_loss = pl_d0 + 10 * path_loss_exponent * math.log10(distance / d0)
        path_loss += random.gauss(0, shadowing_sigma)

        rssi = tx_power_dbm - path_loss
        rssi = max(-130.0, min(-40.0, rssi))

        # Thermal noise floor around -115 dBm for 125kHz
        noise_floor = -115.0 + random.gauss(0, 1.5)
        snr = rssi - noise_floor
        snr = max(-20.0, min(15.0, snr))

        return round(rssi, 1), round(snr, 1)

    def is_packet_lost(self, snr: float, sf: int) -> bool:
        """
        Determines whether the packet is dropped due to:
        1. SNR falling below LoRa demodulation threshold for the given Spreading Factor.
        2. Configured channel loss probability (collisions/interference).
        """
        # Minimum SNR thresholds per SF (Semtech specs)
        snr_thresholds = {
            7: -7.5,
            8: -10.0,
            9: -12.5,
            10: -15.0,
            11: -17.5,
            12: -20.0
        }
        threshold = snr_thresholds.get(sf, -7.5)

        # 1. Physics-based SNR drop
        if snr < threshold:
            return True

        # 2. Configurable channel loss (collisions, obstruction, fading)
        if random.random() < self.loss_probability:
            return True

        return False

    def simulate_latency_ms(self, toa_ms: float) -> float:
        """
        Simulates end-to-end network latency:
        ToA + Gateway processing + backhaul transmission (Ethernet/Cellular) + MQTT broker processing.
        """
        network_delay = random.gauss(self.base_jitter_ms, 8.0)
        network_delay = max(5.0, network_delay)
        return round(toa_ms + network_delay, 2)
