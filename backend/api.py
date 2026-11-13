"""
FastAPI Application and REST/WebSocket API.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.database import (
    init_db,
    get_network_stats,
    get_nodes_list,
    get_recent_packets,
    get_metrics_timeseries,
    clear_database
)
from backend.mqtt_service import mqtt_service
from simulator.simulator import get_simulator
from core.models import SimulatorConfig


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    loop = asyncio.get_running_loop()
    mqtt_service.start(loop)
    # Start simulator automatically with 100 nodes for instant out-of-the-box demo
    sim = get_simulator()
    await sim.start()
    yield
    # Shutdown
    await sim.stop()
    mqtt_service.stop()


app = FastAPI(title="LoRaWAN Network Simulator & Real-Time Dashboard", lifespan=lifespan)

# Mount static web directory
app.mount("/static", StaticFiles(directory="web/static"), name="static")


@app.get("/")
async def serve_dashboard():
    return FileResponse("web/static/index.html")


@app.get("/api/stats")
async def api_stats():
    return await get_network_stats()


@app.get("/api/nodes")
async def api_nodes(limit: int = Query(default=200, ge=1, le=1000)):
    return await get_nodes_list(limit=limit)


@app.get("/api/packets")
async def api_packets(limit: int = Query(default=50, ge=1, le=500)):
    return await get_recent_packets(limit=limit)


@app.get("/api/metrics/timeseries")
async def api_timeseries(limit: int = Query(default=60, ge=10, le=300)):
    return await get_metrics_timeseries(limit=limit)


class ConfigPayload(BaseModel):
    num_nodes: Optional[int] = None
    interval_seconds: Optional[float] = None
    loss_probability: Optional[float] = None


@app.get("/api/simulator/status")
async def api_sim_status():
    sim = get_simulator()
    return {
        "running": sim.is_running,
        "nodes_count": len(sim.nodes),
        "interval_seconds": sim.config.interval_seconds,
        "loss_probability": sim.config.loss_probability,
        "simulated_transmissions": sim.simulated_transmissions,
        "simulated_sent": sim.simulated_sent,
        "simulated_drops": sim.simulated_drops
    }


@app.post("/api/simulator/start")
async def api_sim_start():
    sim = get_simulator()
    if not sim.is_running:
        await sim.start()
    return {"status": "started", "running": sim.is_running}


@app.post("/api/simulator/stop")
async def api_sim_stop():
    sim = get_simulator()
    if sim.is_running:
        await sim.stop()
    return {"status": "stopped", "running": sim.is_running}


@app.post("/api/simulator/configure")
async def api_sim_configure(payload: ConfigPayload):
    sim = get_simulator()
    sim.set_config(
        num_nodes=payload.num_nodes,
        interval=payload.interval_seconds,
        loss=payload.loss_probability
    )
    return {
        "status": "updated",
        "num_nodes": len(sim.nodes),
        "interval_seconds": sim.config.interval_seconds,
        "loss_probability": sim.config.loss_probability
    }


@app.post("/api/database/clear")
async def api_clear_data():
    await clear_database()
    return {"status": "database_cleared"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time streaming websocket for live dashboard metrics and packets."""
    await websocket.accept()
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    mqtt_service.add_ws_subscriber(q)

    # Send initial snapshot immediately upon connection
    stats = await get_network_stats()
    await websocket.send_json({"event": "network_stats", "stats": stats.model_dump()})

    try:
        while True:
            # Receive broadcast from queue and send to browser
            data = await q.get()
            await websocket.send_text(data)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        mqtt_service.remove_ws_subscriber(q)
