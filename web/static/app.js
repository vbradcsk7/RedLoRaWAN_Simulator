// LoRaWAN Real-Time Dashboard Client Logic

let ws = null;
let chartLatency = null;
let chartLoss = null;
let allNodes = [];
let isSimRunning = true;

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', () => {
  lucide.createIcons();
  initCharts();
  connectWebSocket();
  loadInitialData();
  // Poll nodes table and simulator status periodically
  setInterval(loadNodesTable, 3000);
  setInterval(checkSimulatorStatus, 4000);
});

// --- CHARTS SETUP ---
function initCharts() {
  const ctxLat = document.getElementById('chart-latency').getContext('2d');
  chartLatency = new Chart(ctxLat, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'Latencia Media (ms)',
        data: [],
        borderColor: '#06b6d4',
        backgroundColor: 'rgba(6, 182, 212, 0.1)',
        fill: true,
        tension: 0.35,
        borderWidth: 2,
        pointRadius: 2,
        pointHoverRadius: 5
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 400 },
      scales: {
        x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8', font: { size: 10 } } },
        y: { 
          grid: { color: 'rgba(255, 255, 255, 0.05)' }, 
          ticks: { color: '#94a3b8', font: { size: 10 } },
          suggestedMin: 30,
          suggestedMax: 120
        }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });

  const ctxLoss = document.getElementById('chart-loss').getContext('2d');
  chartLoss = new Chart(ctxLoss, {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        {
          label: 'Pérdida (%)',
          data: [],
          borderColor: '#f43f5e',
          backgroundColor: 'rgba(244, 63, 94, 0.1)',
          fill: true,
          tension: 0.35,
          borderWidth: 2,
          yAxisID: 'yLoss',
          pointRadius: 2
        },
        {
          label: 'Throughput (pkts/s)',
          data: [],
          borderColor: '#f59e0b',
          borderWidth: 1.5,
          borderDash: [4, 4],
          fill: false,
          tension: 0.35,
          yAxisID: 'yThroughput',
          pointRadius: 1
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 400 },
      scales: {
        x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8', font: { size: 10 } } },
        yLoss: {
          type: 'linear',
          position: 'left',
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#f43f5e', font: { size: 10 }, callback: v => v + '%' },
          suggestedMin: 0,
          suggestedMax: 20
        },
        yThroughput: {
          type: 'linear',
          position: 'right',
          grid: { display: false },
          ticks: { color: '#f59e0b', font: { size: 10 }, callback: v => v + ' pps' },
          suggestedMin: 0,
          suggestedMax: 30
        }
      },
      plugins: {
        legend: {
          labels: { color: '#cbd5e1', font: { size: 11 }, boxWidth: 12 }
        }
      }
    }
  });
}

// --- WEBSOCKET CONNECTION ---
function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    updateWsStatus(true);
  };

  ws.onclose = () => {
    updateWsStatus(false);
    // Automatic reconnect
    setTimeout(connectWebSocket, 2000);
  };

  ws.onerror = () => {
    updateWsStatus(false);
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.event === 'network_stats') {
        updateNetworkStats(msg.stats);
      } else if (msg.event === 'new_packet') {
        renderIncomingPacket(msg.packet);
      }
    } catch (e) {
      console.error('Error parsing WS message:', e);
    }
  };
}

function updateWsStatus(connected) {
  const badge = document.getElementById('ws-badge');
  const text = document.getElementById('ws-text');
  if (connected) {
    badge.className = 'flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-950/60 border border-emerald-800/60 text-xs text-emerald-400';
    text.innerText = 'WS En Vivo';
    badge.querySelector('span:first-child').className = 'w-2 h-2 rounded-full bg-emerald-400';
  } else {
    badge.className = 'flex items-center gap-2 px-3 py-1.5 rounded-lg bg-rose-950/60 border border-rose-800/60 text-xs text-rose-400';
    text.innerText = 'Reconectando...';
    badge.querySelector('span:first-child').className = 'w-2 h-2 rounded-full bg-rose-400 animate-ping';
  }
}

// --- UPDATE KPIS ---
function updateNetworkStats(stats) {
  // Loss %
  const lossElem = document.getElementById('kpi-loss-pct');
  lossElem.innerText = stats.packet_loss_rate_pct.toFixed(1) + '%';
  
  const badge = document.getElementById('kpi-loss-badge');
  if (stats.packet_loss_rate_pct < 5.0) {
    badge.className = 'text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
    badge.innerText = 'Excelente';
  } else if (stats.packet_loss_rate_pct < 12.0) {
    badge.className = 'text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30';
    badge.innerText = 'Normal';
  } else {
    badge.className = 'text-xs font-semibold px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/30';
    badge.innerText = 'Degradado';
  }

  document.getElementById('kpi-lost-count').innerText = stats.total_lost.toLocaleString();
  document.getElementById('kpi-expected-count').innerText = stats.total_expected.toLocaleString();

  // Latency
  document.getElementById('kpi-avg-latency').innerText = stats.avg_latency_ms.toFixed(1);
  document.getElementById('kpi-min-latency').innerText = stats.min_latency_ms.toFixed(0);
  document.getElementById('kpi-max-latency').innerText = stats.max_latency_ms.toFixed(0);

  // Nodes
  document.getElementById('kpi-active-nodes').innerText = stats.active_nodes;
  document.getElementById('kpi-total-nodes').innerText = stats.total_nodes;

  // Throughput
  document.getElementById('kpi-throughput').innerText = stats.current_throughput_pps.toFixed(1);
  document.getElementById('kpi-received-count').innerText = stats.total_received.toLocaleString();
  
  const mins = Math.floor(stats.uptime_seconds / 60);
  const secs = Math.floor(stats.uptime_seconds % 60);
  document.getElementById('kpi-uptime').innerText = `${mins}m ${secs}s`;

  // Update chart data points
  pushChartPoint(stats);
}

function pushChartPoint(stats) {
  const timeLabel = new Date().toLocaleTimeString('es-ES', { hour12: false });
  
  // Latency chart
  chartLatency.data.labels.push(timeLabel);
  chartLatency.data.datasets[0].data.push(stats.avg_latency_ms);
  if (chartLatency.data.labels.length > 25) {
    chartLatency.data.labels.shift();
    chartLatency.data.datasets[0].data.shift();
  }
  chartLatency.update('none');

  // Loss chart
  chartLoss.data.labels.push(timeLabel);
  chartLoss.data.datasets[0].data.push(stats.packet_loss_rate_pct);
  chartLoss.data.datasets[1].data.push(stats.current_throughput_pps);
  if (chartLoss.data.labels.length > 25) {
    chartLoss.data.labels.shift();
    chartLoss.data.datasets[0].data.shift();
    chartLoss.data.datasets[1].data.shift();
  }
  chartLoss.update('none');
}

// --- RENDER INCOMING PACKET ---
function renderIncomingPacket(pkt) {
  const feed = document.getElementById('packet-feed');
  
  // Clear placeholder if present
  if (feed.children.length === 1 && feed.children[0].innerText.includes('Esperando')) {
    feed.innerHTML = '';
  }

  const item = document.createElement('div');
  item.className = 'p-3 rounded-xl bg-dark-700/50 border border-dark-600 hover:border-dark-500 transition space-y-1.5';

  // Format telemetry pills
  let telemetryBadges = '';
  if (Array.isArray(pkt.readings)) {
    pkt.readings.forEach(r => {
      if (r.type === 'temperature') {
        telemetryBadges += `<span class="px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 text-[10px]">🌡 ${r.value}°C</span> `;
      } else if (r.type === 'humidity') {
        telemetryBadges += `<span class="px-2 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20 text-[10px]">💧 ${r.value}%</span> `;
      } else if (r.type === 'barometer') {
        telemetryBadges += `<span class="px-2 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20 text-[10px]">🧭 ${r.value} hPa</span> `;
      } else if (r.type === 'analog_in') {
        telemetryBadges += `<span class="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 text-[10px]">🔋 ${r.value}V</span> `;
      } else if (r.type === 'illuminance') {
        telemetryBadges += `<span class="px-2 py-0.5 rounded bg-yellow-500/10 text-yellow-300 border border-yellow-500/20 text-[10px]">☀️ ${r.value} lx</span> `;
      } else if (r.type === 'gps') {
        telemetryBadges += `<span class="px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 text-[10px]">📍 GPS OK</span> `;
      }
    });
  }

  // Loss gap warning badge
  let lossNotice = '';
  if (pkt.lost_before_this && pkt.lost_before_this > 0) {
    lossNotice = `<span class="px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 font-bold border border-rose-500/30 text-[10px] animate-pulse">⚠️ +${pkt.lost_before_this} PERDIDO(S)</span>`;
  }

  item.innerHTML = `
    <div class="flex items-center justify-between text-[11px]">
      <div class="flex items-center gap-1.5 font-bold text-emerald-400">
        <span>${pkt.dev_eui}</span>
        <span class="text-slate-400 font-normal">#${pkt.f_cnt}</span>
        ${lossNotice}
      </div>
      <div class="flex items-center gap-2 text-slate-400 text-[10px]">
        <span class="text-cyan-400 font-semibold">${pkt.latency_ms} ms</span>
        <span>SF${pkt.spreading_factor}</span>
        <span>${pkt.rssi} dBm</span>
      </div>
    </div>
    <div class="flex flex-wrap gap-1 items-center">
      ${telemetryBadges}
    </div>
    <div class="text-[10px] text-slate-500 truncate font-mono">
      RAW: <span class="text-slate-400">${pkt.payload_hex}</span>
    </div>
  `;

  // Prepend to top of feed
  feed.insertBefore(item, feed.firstChild);

  // Keep max 20 visible packets in DOM for performance
  if (feed.children.length > 20) {
    feed.removeChild(feed.lastChild);
  }
}

// --- NODE REGISTRY TABLE ---
async function loadNodesTable() {
  try {
    const res = await fetch('/api/nodes?limit=200');
    if (!res.ok) return;
    allNodes = await res.json();
    filterNodesTable();
  } catch (e) {
    console.error('Failed to fetch nodes:', e);
  }
}

function filterNodesTable() {
  const query = (document.getElementById('node-search').value || '').toLowerCase().trim();
  const tbody = document.getElementById('nodes-table-body');
  
  const filtered = allNodes.filter(n => n.dev_eui.toLowerCase().includes(query) || n.name.toLowerCase().includes(query));

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-6 text-slate-500">No hay nodos registrados todavía</td></tr>`;
    return;
  }

  let html = '';
  filtered.forEach(n => {
    const lossColor = n.loss_rate_pct > 12 ? 'text-rose-400' : (n.loss_rate_pct > 5 ? 'text-amber-400' : 'text-emerald-400');
    const statusBadge = n.status === 'active' 
      ? '<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-[10px]">Activo</span>'
      : '<span class="px-2 py-0.5 rounded bg-slate-700 text-slate-400 text-[10px]">Inactivo</span>';

    html += `
      <tr class="hover:bg-dark-700/40 transition">
        <td class="p-2.5 font-bold text-slate-200">${n.dev_eui}</td>
        <td class="p-2.5 text-slate-300">#${n.last_fcnt}</td>
        <td class="p-2.5 font-bold ${lossColor}">${n.loss_rate_pct.toFixed(1)}% <span class="text-[10px] font-normal text-slate-400">(${n.packets_lost}/${n.packets_expected})</span></td>
        <td class="p-2.5 text-cyan-300">${n.avg_latency_ms.toFixed(1)} ms</td>
        <td class="p-2.5 text-slate-300">${n.avg_rssi} dBm / ${n.avg_snr} dB</td>
        <td class="p-2.5 text-emerald-300">${n.battery_v.toFixed(2)}V</td>
        <td class="p-2.5">${statusBadge}</td>
      </tr>
    `;
  });

  tbody.innerHTML = html;
}

// --- INITIAL DATA & METRICS HISTORY ---
async function loadInitialData() {
  try {
    const [resTimeseries, resNodes] = await Promise.all([
      fetch('/api/metrics/timeseries?limit=30'),
      fetch('/api/nodes?limit=200')
    ]);

    if (resTimeseries.ok) {
      const data = await resTimeseries.json();
      data.forEach(pt => {
        const timeLabel = new Date(pt.timestamp * 1000).toLocaleTimeString('es-ES', { hour12: false });
        chartLatency.data.labels.push(timeLabel);
        chartLatency.data.datasets[0].data.push(pt.avg_latency_ms);
        chartLoss.data.labels.push(timeLabel);
        chartLoss.data.datasets[0].data.push(pt.loss_rate_pct);
        chartLoss.data.datasets[1].data.push(pt.throughput_pps);
      });
      chartLatency.update();
      chartLoss.update();
    }

    if (resNodes.ok) {
      allNodes = await resNodes.json();
      filterNodesTable();
    }
  } catch (e) {
    console.error('Error loading initial data:', e);
  }
}

// --- SIMULATOR CONTROLS ---
async function toggleSimulator() {
  const btn = document.getElementById('btn-toggle-sim');
  const text = document.getElementById('btn-toggle-text');

  if (isSimRunning) {
    const res = await fetch('/api/simulator/stop', { method: 'POST' });
    if (res.ok) {
      isSimRunning = false;
      updateSimBadge(false);
    }
  } else {
    const res = await fetch('/api/simulator/start', { method: 'POST' });
    if (res.ok) {
      isSimRunning = true;
      updateSimBadge(true);
    }
  }
}

async function checkSimulatorStatus() {
  try {
    const res = await fetch('/api/simulator/status');
    if (!res.ok) return;
    const data = await res.json();
    isSimRunning = data.running;
    updateSimBadge(data.running);
  } catch (e) {
    console.error('Status check error:', e);
  }
}

function updateSimBadge(running) {
  const badge = document.getElementById('sim-badge');
  const text = document.getElementById('sim-state-text');
  const btnText = document.getElementById('btn-toggle-text');
  const btn = document.getElementById('btn-toggle-sim');

  if (running) {
    badge.className = 'flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-950/60 border border-emerald-800/60 text-xs text-emerald-400';
    text.innerText = 'Simulador Activo';
    btnText.innerText = 'Pausar';
    btn.className = 'px-3.5 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 active:scale-95 text-white text-xs font-semibold flex items-center gap-1.5 transition';
  } else {
    badge.className = 'flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-xs text-slate-400';
    text.innerText = 'Simulador Pausado';
    btnText.innerText = 'Reanudar';
    btn.className = 'px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-white text-xs font-semibold flex items-center gap-1.5 transition';
  }
}

async function applySimConfig() {
  const nodes = parseInt(document.getElementById('slider-nodes').value);
  const interval = parseFloat(document.getElementById('slider-interval').value);
  const loss = parseFloat(document.getElementById('slider-loss').value);

  try {
    const res = await fetch('/api/simulator/configure', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        num_nodes: nodes,
        interval_seconds: interval,
        loss_probability: loss
      })
    });
    if (res.ok) {
      alert(`✅ Configuración aplicada con éxito:\n- ${nodes} Nodos\n- Intervalo: ${interval}s\n- Pérdida canal: ${(loss * 100).toFixed(0)}%`);
    }
  } catch (e) {
    alert('Error al aplicar configuración: ' + e);
  }
}

async function clearDb() {
  if (!confirm('¿Estás seguro de que deseas reiniciar todos los paquetes y estadísticas de la base de datos?')) {
    return;
  }
  try {
    await fetch('/api/database/clear', { method: 'POST' });
    chartLatency.data.labels = [];
    chartLatency.data.datasets[0].data = [];
    chartLatency.update();
    chartLoss.data.labels = [];
    chartLoss.data.datasets[0].data = [];
    chartLoss.data.datasets[1].data = [];
    chartLoss.update();
    document.getElementById('packet-feed').innerHTML = '<div class="text-center py-10 text-slate-500">Esperando paquetes LoRaWAN...</div>';
    loadNodesTable();
  } catch (e) {
    console.error('Error clearing DB:', e);
  }
}
