"""
Asynchronous SQLite Database Manager for LoRaWAN metrics and packet storage.
"""

import aiosqlite
import json
import time
from typing import List, Dict, Any, Optional
from core.models import DecodedPacket, NodeStats, NetworkStats

DB_PATH = "data/lorawan.db"


async def init_db():
    """Initializes the database schema."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                dev_eui TEXT PRIMARY KEY,
                name TEXT,
                first_seen REAL,
                last_seen REAL,
                last_fcnt INTEGER,
                packets_expected INTEGER DEFAULT 0,
                packets_received INTEGER DEFAULT 0,
                packets_lost INTEGER DEFAULT 0,
                total_latency_ms REAL DEFAULT 0,
                battery_v REAL DEFAULT 3.3,
                last_rssi REAL DEFAULT 0,
                last_snr REAL DEFAULT 0
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS packets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dev_eui TEXT,
                f_cnt INTEGER,
                f_port INTEGER,
                payload_hex TEXT,
                decoded_json TEXT,
                rssi REAL,
                snr REAL,
                spreading_factor INTEGER,
                toa_ms REAL,
                latency_ms REAL,
                lost_gap INTEGER DEFAULT 0,
                received_at REAL,
                FOREIGN KEY (dev_eui) REFERENCES nodes (dev_eui)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS metrics_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                total_received INTEGER,
                total_lost INTEGER,
                loss_rate_pct REAL,
                avg_latency_ms REAL,
                active_nodes INTEGER,
                throughput_pps REAL
            )
        """)

        # Indexes for speed with high volume
        await db.execute("CREATE INDEX IF NOT EXISTS idx_packets_eui ON packets(dev_eui);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_packets_time ON packets(received_at DESC);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_metrics_time ON metrics_history(timestamp DESC);")

        await db.commit()


async def save_packet(packet: DecodedPacket, battery_v: float = 3.3) -> Dict[str, Any]:
    """
    Saves packet and updates the node statistics with frame counter loss detection.
    Returns calculated packet loss gap for this packet.
    """
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # 1. Check existing node state
        cursor = await db.execute("SELECT * FROM nodes WHERE dev_eui = ?", (packet.dev_eui,))
        node = await cursor.fetchone()

        lost_gap = 0
        if node is None:
            # First packet from this node
            expected = 1
            received = 1
            lost = 0
            total_lat = packet.latency_ms
            await db.execute("""
                INSERT INTO nodes (
                    dev_eui, name, first_seen, last_seen, last_fcnt,
                    packets_expected, packets_received, packets_lost,
                    total_latency_ms, battery_v, last_rssi, last_snr
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                packet.dev_eui, f"Node-{packet.dev_eui[-4:]}", now, now, packet.f_cnt,
                expected, received, lost, total_lat, battery_v, packet.rssi, packet.snr
            ))
        else:
            prev_fcnt = node["last_fcnt"]
            # Detect frame counter jumps (e.g. prev=10, current=13 => 2 packets dropped: 11, 12)
            if packet.f_cnt > prev_fcnt:
                lost_gap = packet.f_cnt - prev_fcnt - 1
            elif packet.f_cnt < prev_fcnt:
                # Counter roll-over or reset
                lost_gap = 0

            new_expected = node["packets_expected"] + 1 + lost_gap
            new_received = node["packets_received"] + 1
            new_lost = node["packets_lost"] + lost_gap
            new_total_lat = node["total_latency_ms"] + packet.latency_ms

            await db.execute("""
                UPDATE nodes SET
                    last_seen = ?,
                    last_fcnt = ?,
                    packets_expected = ?,
                    packets_received = ?,
                    packets_lost = ?,
                    total_latency_ms = ?,
                    battery_v = ?,
                    last_rssi = ?,
                    last_snr = ?
                WHERE dev_eui = ?
            """, (
                now, packet.f_cnt, new_expected, new_received, new_lost,
                new_total_lat, battery_v, packet.rssi, packet.snr, packet.dev_eui
            ))

        # 2. Insert Packet
        decoded_str = json.dumps(packet.readings)
        await db.execute("""
            INSERT INTO packets (
                dev_eui, f_cnt, f_port, payload_hex, decoded_json,
                rssi, snr, spreading_factor, toa_ms, latency_ms,
                lost_gap, received_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            packet.dev_eui, packet.f_cnt, packet.f_port, packet.payload_hex,
            decoded_str, packet.rssi, packet.snr, packet.spreading_factor,
            packet.toa_ms, packet.latency_ms, lost_gap, packet.received_at
        ))

        await db.commit()

        return {
            "lost_gap": lost_gap,
            "dev_eui": packet.dev_eui,
            "f_cnt": packet.f_cnt
        }


async def get_network_stats() -> NetworkStats:
    """Computes global network statistics."""
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Nodes aggregation
        cursor = await db.execute("""
            SELECT 
                COUNT(*) as total_nodes,
                SUM(CASE WHEN (? - last_seen) < 30 THEN 1 ELSE 0 END) as active_nodes,
                COALESCE(SUM(packets_expected), 0) as total_expected,
                COALESCE(SUM(packets_received), 0) as total_received,
                COALESCE(SUM(packets_lost), 0) as total_lost,
                COALESCE(SUM(total_latency_ms), 0) as sum_latency
            FROM nodes
        """, (now,))
        row = await cursor.fetchone()

        total_nodes = row["total_nodes"] or 0
        active_nodes = row["active_nodes"] or 0
        total_expected = row["total_expected"] or 0
        total_received = row["total_received"] or 0
        total_lost = row["total_lost"] or 0
        sum_latency = row["sum_latency"] or 0

        loss_rate = (total_lost / total_expected * 100.0) if total_expected > 0 else 0.0
        avg_latency = (sum_latency / total_received) if total_received > 0 else 0.0

        # Latency Min/Max and recent throughput (last 10 seconds)
        cursor = await db.execute("""
            SELECT 
                COALESCE(MIN(latency_ms), 0) as min_lat,
                COALESCE(MAX(latency_ms), 0) as max_lat,
                COUNT(*) as recent_pkts
            FROM packets
            WHERE received_at >= (? - 10)
        """, (now,))
        lat_row = await cursor.fetchone()
        min_lat = lat_row["min_lat"]
        max_lat = lat_row["max_lat"]
        throughput = round(lat_row["recent_pkts"] / 10.0, 2)

        # Uptime based on earliest node
        cursor = await db.execute("SELECT MIN(first_seen) as start_time FROM nodes")
        start_row = await cursor.fetchone()
        start_time = start_row["start_time"] if start_row and start_row["start_time"] else now
        uptime = max(0.0, now - start_time)

        return NetworkStats(
            total_nodes=total_nodes,
            active_nodes=active_nodes,
            total_expected=total_expected,
            total_received=total_received,
            total_lost=total_lost,
            packet_loss_rate_pct=round(loss_rate, 2),
            avg_latency_ms=round(avg_latency, 2),
            min_latency_ms=round(min_lat, 2),
            max_latency_ms=round(max_lat, 2),
            current_throughput_pps=throughput,
            uptime_seconds=round(uptime, 1)
        )


async def get_nodes_list(limit: int = 200) -> List[NodeStats]:
    """Retrieves all simulated nodes and their individual metrics."""
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM nodes 
            ORDER BY last_seen DESC 
            LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()

        nodes = []
        for r in rows:
            expected = r["packets_expected"] or 1
            received = r["packets_received"] or 0
            lost = r["packets_lost"] or 0
            loss_pct = (lost / expected * 100.0) if expected > 0 else 0.0
            avg_lat = (r["total_latency_ms"] / received) if received > 0 else 0.0
            status = "active" if (now - r["last_seen"]) < 20 else "inactive"

            nodes.append(NodeStats(
                dev_eui=r["dev_eui"],
                name=r["name"],
                last_seen=r["last_seen"],
                last_fcnt=r["last_fcnt"],
                packets_expected=expected,
                packets_received=received,
                packets_lost=lost,
                loss_rate_pct=round(loss_pct, 2),
                avg_latency_ms=round(avg_lat, 2),
                avg_rssi=round(r["last_rssi"], 1),
                avg_snr=round(r["last_snr"], 1),
                battery_v=round(r["battery_v"], 2),
                status=status
            ))
        return nodes


async def get_recent_packets(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves recent decoded packets for the live feed."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT id, dev_eui, f_cnt, f_port, payload_hex, decoded_json,
                   rssi, snr, spreading_factor, toa_ms, latency_ms, lost_gap, received_at
            FROM packets
            ORDER BY received_at DESC
            LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()

        results = []
        for r in rows:
            item = dict(r)
            try:
                item["readings"] = json.loads(item["decoded_json"])
            except Exception:
                item["readings"] = []
            results.append(item)
        return results


async def record_metrics_snapshot():
    """Takes a periodic snapshot of network metrics into metrics_history table."""
    stats = await get_network_stats()
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO metrics_history (
                timestamp, total_received, total_lost, loss_rate_pct,
                avg_latency_ms, active_nodes, throughput_pps
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            now, stats.total_received, stats.total_lost, stats.packet_loss_rate_pct,
            stats.avg_latency_ms, stats.active_nodes, stats.current_throughput_pps
        ))
        await db.commit()


async def get_metrics_timeseries(limit: int = 60) -> List[Dict[str, Any]]:
    """Returns historical metric points for charts."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT timestamp, loss_rate_pct, avg_latency_ms, throughput_pps, active_nodes
            FROM metrics_history
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()
        # Return chronological order (oldest to newest)
        return [dict(r) for r in reversed(rows)]


async def clear_database():
    """Resets all metrics and packets."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM packets")
        await db.execute("DELETE FROM nodes")
        await db.execute("DELETE FROM metrics_history")
        await db.commit()
