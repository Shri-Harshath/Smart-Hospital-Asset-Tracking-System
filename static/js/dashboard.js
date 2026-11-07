/**
 * Smart Hospital Asset Tracking System
 * Live Dashboard, Interactive Floor Map & Real-Time Data Flow Pipeline
 */

let previousAlertCount = 0;
let lastKnownAssetRooms = {};
let selectedAssetId = null;

// Category icons map
const CATEGORY_ICONS = {
    'Ventilator': 'fa-lungs',
    'Defibrillator': 'fa-heart-pulse',
    'Patient Monitor': 'fa-wave-square',
    'Infusion Pump': 'fa-syringe',
    'ECG Machine': 'fa-file-waveform',
    'Wheelchair': 'fa-wheelchair',
    'Portable X-Ray': 'fa-radiation'
};

document.addEventListener('DOMContentLoaded', () => {
    fetchRealtimeState();
    // Periodic refresh every 2 seconds
    setInterval(fetchRealtimeState, 2000);
    // Connect to Server-Sent Events stream for instant packet delivery
    initSSEStream();
});

// Real-Time State Fetcher
async function fetchRealtimeState() {
    try {
        const res = await fetch('/api/state');
        if (!res.ok) return;
        const data = await res.json();
        
        updateKPIs(data.stats);
        renderFloorPlanAssets(data.assets, data.rooms, data.gateways, data.alerts);
        updateAlertsPanel(data.alerts);
        updateDataFlowPipeline(data.recent_packets[0]);
        updateSimButton(data.simulation_running);
        
        // Update MQTT Status pill
        const mqttPill = document.getElementById('mqtt-status-pill');
        const mqttText = document.getElementById('mqtt-status-text');
        if (mqttPill && mqttText && data.mqtt_status) {
            mqttText.innerText = data.mqtt_status.connected ? "MQTT 3.1.1 Active (TCP:1883)" : "MQTT Fallback Bus";
        }
    } catch (e) {
        console.warn("Failed fetching live state:", e);
    }
}

// Update KPI Stats Cards
function updateKPIs(stats) {
    if (!stats) return;
    document.getElementById('stat-total-assets').innerText = stats.total_assets;
    document.getElementById('stat-in-use').innerText = stats.in_use_assets;
    document.getElementById('stat-available').innerText = stats.available_assets;
    document.getElementById('stat-maintenance').innerText = stats.maintenance_assets;
    document.getElementById('stat-alerts').innerText = stats.active_alerts;
    
    const alertPill = document.getElementById('nav-alert-pill');
    const alertCount = document.getElementById('nav-alert-count');
    if (alertPill && alertCount) {
        alertCount.innerText = stats.active_alerts;
        if (stats.critical_alerts > 0) {
            alertPill.classList.add('active-breach');
        } else {
            alertPill.classList.remove('active-breach');
        }
    }
}

// Render SVG Hospital Floor Plan Assets
function renderFloorPlanAssets(assets, rooms, gateways, alerts) {
    const assetContainer = document.getElementById('svg-assets-layer');
    if (!assetContainer) return;

    // Detect rooms with critical breach alerts
    const breachedRooms = new Set();
    alerts.forEach(al => {
        if (!al.acknowledged && (al.alert_type === 'GEOFENCE_BREACH' || al.alert_type === 'EXIT_PROXIMITY')) {
            breachedRooms.add(al.room_id);
        }
    });

    // Update room styling if breached
    rooms.forEach(r => {
        const roomBox = document.getElementById(`room-rect-${r.room_id}`);
        if (roomBox) {
            if (breachedRooms.has(r.room_id)) {
                roomBox.classList.add('geofence-breached');
            } else {
                roomBox.classList.remove('geofence-breached');
            }
        }
    });

    // Group assets by room
    const assetsByRoom = {};
    assets.forEach(a => {
        if (!assetsByRoom[a.current_room_id]) assetsByRoom[a.current_room_id] = [];
        assetsByRoom[a.current_room_id].push(a);

        // Check for room transfer animation
        if (lastKnownAssetRooms[a.asset_id] && lastKnownAssetRooms[a.asset_id] !== a.current_room_id) {
            showToast(`Asset <strong>${a.name}</strong> moved to ${a.current_room_name}`, 'info');
        }
        lastKnownAssetRooms[a.asset_id] = a.current_room_id;
    });

    let html = '';

    rooms.forEach(room => {
        const roomAssets = assetsByRoom[room.room_id] || [];
        const startX = room.x + 12;
        const startY = room.y + 45;
        const itemsPerRow = room.width > 200 ? 3 : (room.width > 100 ? 2 : 1);

        roomAssets.forEach((asset, idx) => {
            const col = idx % itemsPerRow;
            const row = Math.floor(idx / itemsPerRow);
            const posX = startX + (col * 68);
            const posY = startY + (row * 36);

            const isBreached = breachedRooms.has(asset.current_room_id);
            
            // Asset badge color
            let badgeBg = '#1e293b';
            let badgeBorder = '#334155';
            let textColor = '#f8fafc';
            if (isBreached) {
                badgeBg = '#7f1d1d';
                badgeBorder = '#ef4444';
            } else if (asset.status === 'In Use') {
                badgeBorder = '#3b82f6';
            } else if (asset.status === 'Maintenance') {
                badgeBorder = '#f59e0b';
            }

            // Battery color
            let battColor = '#10b981';
            if (asset.battery <= 20) battColor = '#ef4444';
            else if (asset.battery <= 50) battColor = '#f59e0b';

            html += `
                <g class="asset-pill-group" transform="translate(${posX}, ${posY})" onclick="openAssetDrawer('${asset.asset_id}')">
                    <rect width="64" height="28" rx="6" fill="${badgeBg}" stroke="${badgeBorder}" stroke-width="${isBreached ? 2 : 1.2}"/>
                    <text x="8" y="18" fill="#38bdf8" font-size="11" font-family="Inter, sans-serif" font-weight="700">
                        ${asset.asset_id.replace('AST-', '')}
                    </text>
                    <!-- Battery circle -->
                    <circle cx="53" cy="14" r="4.5" fill="${battColor}"/>
                </g>
            `;
        });
    });

    assetContainer.innerHTML = html;
}

// Live Data Flow Pipeline Visualizer
function updateDataFlowPipeline(latestPacket) {
    if (!latestPacket) return;

    const ticker = document.getElementById('pipeline-ticker-text');
    if (ticker) {
        ticker.innerHTML = `
            <span class="ticker-highlight"><i class="fa-solid fa-cube"></i> Live Packet:</span>
            <span>Tag: <strong class="ticker-highlight">${latestPacket.tag_id}</strong></span> |
            <span>Asset: <strong>${latestPacket.asset_id}</strong></span> |
            <span>Gateway: <strong>${latestPacket.gateway_id}</strong> (${latestPacket.source_ip})</span> |
            <span>RSSI: <strong class="ticker-highlight">${latestPacket.rssi} dBm</strong></span> |
            <span>Dist: <strong>${latestPacket.distance_m}m</strong></span> |
            <span>Topic: <code style="color: #fbbf24;">${latestPacket.topic}</code></span>
        `;
    }

    // Sequentially pulse nodes
    const nodes = document.querySelectorAll('.pipeline-node');
    nodes.forEach(n => n.classList.remove('active-packet'));
    let i = 0;
    const interval = setInterval(() => {
        if (i > 0 && nodes[i - 1]) nodes[i - 1].classList.remove('active-packet');
        if (i < nodes.length) {
            nodes[i].classList.add('active-packet');
            i++;
        } else {
            clearInterval(interval);
            setTimeout(() => {
                nodes.forEach(n => n.classList.remove('active-packet'));
            }, 300);
        }
    }, 120);
}

// Server-Sent Events (SSE) Stream
function initSSEStream() {
    if (!window.EventSource) return;
    const sse = new EventSource('/api/stream');

    sse.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'PACKET' && data.packet) {
                appendLogEntry(data.packet);
            }
        } catch (e) {
            // Ignore parse errors on heartbeat pings
        }
    };

    sse.onerror = () => {
        // Fallback gracefully; fetchRealtimeState polling handles rest
    };
}

// Append Network Packet to Live Terminal
function appendLogEntry(pkt) {
    const terminal = document.getElementById('packet-terminal-body');
    if (!terminal) return;

    const isDrop = pkt.status.includes('DROPPED');
    const protoClass = isDrop ? 'log-proto-drop' : 'log-proto-mqtt';

    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `
        <div class="log-meta-line">
            <span class="log-time">[${pkt.timestamp}]</span>
            <span class="${protoClass}">${pkt.protocol}</span>
            <span class="log-ip">${pkt.source_ip}:${pkt.port} &rarr; ${pkt.dest_ip}</span>
            <span class="log-topic">${pkt.topic}</span>
        </div>
        <div class="log-detail">
            Asset: <strong style="color: #f1f5f9;">${pkt.asset_id}</strong> (${pkt.tag_id}) | 
            RSSI: <strong>${pkt.rssi} dBm</strong> (d &approx; ${pkt.distance_m}m) | 
            VLAN: <strong>${pkt.vlan}</strong> | 
            Size: <strong>${pkt.packet_size_bytes}B</strong> | 
            Status: <span style="color: ${isDrop ? '#ef4444' : '#10b981'}; font-weight: 700;">${pkt.status}</span>
        </div>
    `;

    terminal.insertBefore(entry, terminal.firstChild);

    // Limit to 40 entries in terminal DOM
    while (terminal.children.length > 40) {
        terminal.removeChild(terminal.lastChild);
    }
}

// Update Active Alerts Panel
function updateAlertsPanel(alerts) {
    const container = document.getElementById('alerts-list-container');
    if (!container) return;

    if (!alerts || alerts.length === 0) {
        container.innerHTML = `
            <div style="padding: 1.5rem; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
                <i class="fa-solid fa-circle-check text-green" style="font-size: 1.5rem; margin-bottom: 0.5rem; display: block;"></i>
                All systems normal. No active hospital security or geofence breaches.
            </div>
        `;
        return;
    }

    // Check if new critical alert arrived
    const currentUnacked = alerts.filter(a => !a.acknowledged).length;
    if (currentUnacked > previousAlertCount) {
        const latest = alerts[0];
        if (latest && latest.severity === 'CRITICAL') {
            playHospitalAlertChime('CRITICAL');
        } else {
            playHospitalAlertChime('WARNING');
        }
    }
    previousAlertCount = currentUnacked;

    let html = '';
    alerts.forEach(al => {
        const isAcked = al.acknowledged == 1;
        const sevClass = al.severity.toLowerCase();
        html += `
            <div class="alert-item ${sevClass}" style="${isAcked ? 'opacity: 0.55;' : ''}">
                <div class="alert-content">
                    <div class="alert-header">
                        <span class="alert-badge ${sevClass}">${al.severity}</span>
                        <span style="font-size: 0.78rem; font-weight: 700; color: #f8fafc;">${al.asset_name}</span>
                        <span style="font-size: 0.7rem; color: #94a3b8;">(${al.room_name})</span>
                    </div>
                    <div class="alert-msg">${al.message}</div>
                    <div class="alert-time"><i class="fa-regular fa-clock"></i> ${al.timestamp}</div>
                </div>
                <div>
                    ${!isAcked ? `
                        <button class="btn btn-sm btn-secondary" onclick="acknowledgeAlert(${al.id})">
                            <i class="fa-solid fa-check"></i> Ack
                        </button>
                    ` : `
                        <span style="font-size: 0.7rem; color: #34d399;"><i class="fa-solid fa-check-double"></i> Resolved</span>
                    `}
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

async function acknowledgeAlert(alertId) {
    try {
        await fetch(`/api/alerts/acknowledge/${alertId}`, { method: 'POST' });
        showToast("Alert acknowledged", "info");
        fetchRealtimeState();
    } catch (e) {
        showToast("Error acknowledging alert: " + e, "error");
    }
}

// Asset Detail Drawer
async function openAssetDrawer(assetId) {
    try {
        const res = await fetch(`/api/asset/${assetId}`);
        if (!res.ok) return;
        const asset = await res.json();
        selectedAssetId = assetId;

        document.getElementById('drawer-asset-title').innerText = asset.name;
        document.getElementById('drawer-asset-id').innerText = asset.asset_id;
        document.getElementById('drawer-category').innerText = asset.category;
        document.getElementById('drawer-model').innerText = asset.model;
        document.getElementById('drawer-tag-id').innerText = `${asset.tag_id} (${asset.tag_mac})`;
        document.getElementById('drawer-assigned-room').innerText = asset.assigned_room_name;
        document.getElementById('drawer-current-room').innerText = asset.current_room_name;
        document.getElementById('drawer-gateway').innerText = `${asset.gateway_name} (${asset.gateway_ip})`;
        document.getElementById('drawer-rssi').innerText = `${asset.rssi} dBm (Approx ${asset.distance_m}m)`;
        document.getElementById('drawer-battery').innerText = `${asset.battery}%`;
        document.getElementById('drawer-status').innerText = asset.status;
        document.getElementById('drawer-maint').innerText = asset.maintenance_status;

        // Populate relocation select
        const sel = document.getElementById('drawer-target-room');
        if (sel) sel.value = asset.current_room_id;

        const drawer = document.getElementById('asset-detail-drawer');
        if (drawer) drawer.classList.remove('hidden');
    } catch (e) {
        console.warn("Failed to load asset details:", e);
    }
}

function closeAssetDrawer() {
    const drawer = document.getElementById('asset-detail-drawer');
    if (drawer) drawer.classList.add('hidden');
}

async function transferSelectedAsset() {
    if (!selectedAssetId) return;
    const targetRoomSelect = document.getElementById('drawer-target-room');
    const targetRoom = targetRoomSelect ? targetRoomSelect.value : '';
    if (!targetRoom) {
        showToast("Please choose a destination ward", "warning");
        return;
    }
    try {
        const res = await fetch('/api/move', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ asset_id: selectedAssetId, room_id: targetRoom })
        });
        
        let data;
        const contentType = res.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            data = await res.json();
        } else {
            throw new Error(`Server returned HTTP ${res.status}`);
        }

        if (res.ok && data.status === 'success') {
            showToast(data.message, "success");
            playHospitalAlertChime('INFO');
            await fetchRealtimeState();
            closeAssetDrawer();
        } else {
            showToast("Failed to move: " + (data.error || data.message || "Unknown error"), "error");
        }
    } catch (e) {
        showToast("Error executing transfer: " + e.message, "error");
    }
}

