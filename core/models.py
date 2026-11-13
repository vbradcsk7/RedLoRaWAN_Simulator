"""
LoRaWAN and System Data Models.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import time


class LoRaWANPacket(BaseModel):
    dev_eui: str
    app_eui: str = "70B3D57ED0000000"
    f_port: int = 1
    f_cnt: int
    payload_hex: str
    frequency_hz: int = 868100000
    spreading_factor: int = 7
    bandwidth_khz: int = 125
    rssi: float
    snr: float
    toa_ms: float
    gateway_id: str = "GW-001"
    sent_timestamp: float = Field(default_factory=time.time)
    received_timestamp: Optional[float] = None
    latency_ms: Optional[float] = None


class DecodedPacket(BaseModel):
    id: Optional[int] = None
    dev_eui: str
    f_cnt: int
    f_port: int
    payload_hex: str
    readings: List[Dict[str, Any]]
    rssi: float
    snr: float
    spreading_factor: int
    toa_ms: float
    latency_ms: float
    lost_before_this: int = 0
    received_at: float


class NodeStats(BaseModel):
    dev_eui: str
    name: str
    last_seen: float
    last_fcnt: int
    packets_expected: int
    packets_received: int
    packets_lost: int
    loss_rate_pct: float
    avg_latency_ms: float
    avg_rssi: float
    avg_snr: float
    battery_v: float
    status: str = "active"


class NetworkStats(BaseModel):
    total_nodes: int
    active_nodes: int
    total_expected: int
    total_received: int
    total_lost: int
    packet_loss_rate_pct: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    current_throughput_pps: float
    uptime_seconds: float


class SimulatorConfig(BaseModel):
    num_nodes: int = 100
    interval_seconds: float = 5.0
    loss_probability: float = 0.05   # 5% base artificial radio loss
    jitter_max_ms: float = 50.0
    running: bool = False
