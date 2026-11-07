/**
 * Feature 2: Hospital Floor Map Controller
 * Real-time floor plan visualization and interactive room inspector.
 */

let allAssets = [];
let allRooms = [];
let allGateways = [];
let selectedRoomId = 'ICU';

const CATEGORY_ICONS = {
    'Ventilator': 'fa-lungs',
    'Defibrillator': 'fa-heart-pulse',
    'Patient Monitor': 'fa-wave-square',
    'Infusion Pump': 'fa-syringe',
    'ECG Machine': 'fa-file-waveform',
    'Wheelchair': 'fa-wheelchair',
    'Portable X-Ray': 'fa-radiation',
    'Ultrasound': 'fa-satellite-dish',
    'Dialysis Machine': 'fa-flask',
    'Syringe Pump': 'fa-syringe',
    'Medical Device': 'fa-kit-medical'
};

document.addEventListener('DOMContentLoaded', () => {
    loadFloorMapData();
    setInterval(loadFloorMapData, 2000);
});

// Primary data loader
async function loadFloorMapData() {
    try {
        const res = await fetch('/api/state');
        if (!res.ok) return;
        const data = await res.json();

        allAssets = data.assets || [];
        allRooms = data.rooms || [];
        allGateways = data.gateways || [];

        renderFloorMap();
        renderRoomInspector();
    } catch (e) {
        console.warn("Error refreshing floor map:", e);
    }
}

// Filter assets based on top filter dropdowns
function getFilteredAssets() {
    const cat = document.getElementById('map-category-filter').value;
    const stat = document.getElementById('map-status-filter').value;

    return allAssets.filter(a => {
        const matchCat = (cat === 'ALL' || a.category === cat);
        const matchStat = (stat === 'ALL' || a.status === stat);
        return matchCat && matchStat;
    });
}

function filterMapAssets() {
    renderFloorMap();
    renderRoomInspector();
}

// Render dynamic equipment markers on the SVG layout
function renderFloorMap() {
    const container = document.getElementById('map-svg-assets-layer');
    if (!container) return;

    const filtered = getFilteredAssets();
    document.getElementById('map-total-badge').innerText = `${filtered.length} Assets`;

    // Group assets by current physical room
    const assetsByRoom = {};
    filtered.forEach(a => {
        if (!assetsByRoom[a.current_room_id]) assetsByRoom[a.current_room_id] = [];
        assetsByRoom[a.current_room_id].push(a);
    });

    // Update room selection highlight
    allRooms.forEach(r => {
        const roomRect = document.getElementById(`map-room-rect-${r.room_id}`);
        if (roomRect) {
            if (r.room_id === selectedRoomId) {
                roomRect.style.stroke = '#38bdf8';
                roomRect.style.strokeWidth = '3';
                roomRect.style.fill = 'rgba(56, 189, 248, 0.16)';
            } else {
                roomRect.style.stroke = r.color || '#334155';
                roomRect.style.strokeWidth = '1.5';
                roomRect.style.fill = `${r.color || '#334155'}14`;
            }
        }
    });

    let html = '';

    allRooms.forEach(room => {
        const roomAssets = assetsByRoom[room.room_id] || [];
        const startX = room.x + 12;
        const startY = room.y + 70;
        const itemsPerRow = room.width > 200 ? 3 : (room.width > 120 ? 2 : 1);
        const itemWidth = 65;
        const itemHeight = 30;

        roomAssets.forEach((asset, idx) => {
            const row = Math.floor(idx / itemsPerRow);
            const col = idx % itemsPerRow;
            const x = startX + (col * (itemWidth + 6));
            const y = startY + (row * (itemHeight + 6));

            let statusColor = '#10b981'; // Available
            if (asset.status === 'In Use') statusColor = '#3b82f6';
            if (asset.status === 'Maintenance') statusColor = '#f59e0b';

            const iconClass = CATEGORY_ICONS[asset.category] || 'fa-kit-medical';

            html += `
                <g class="asset-marker" transform="translate(${x}, ${y})" onclick="selectRoom('${room.room_id}'); event.stopPropagation();" style="cursor: pointer;">
                    <rect width="${itemWidth}" height="${itemHeight}" rx="5" fill="#0f172a" stroke="${statusColor}" stroke-width="1.2" opacity="0.95"/>
                    <circle cx="12" cy="15" r="7" fill="${statusColor}22" stroke="${statusColor}" stroke-width="0.8"/>
                    <text x="12" y="18" fill="${statusColor}" font-size="8" text-anchor="middle" font-family="monospace">●</text>
                    <text x="24" y="14" fill="#f8fafc" font-size="7.5" font-family="Inter" font-weight="700">${asset.asset_id.replace('AST-', '')}</text>
                    <text x="24" y="23" fill="#94a3b8" font-size="6.5" font-family="Inter">${asset.battery}% 🔋</text>
                </g>
            `;
        });
    });

    container.innerHTML = html;
}

// Room selector function
function selectRoom(roomId) {
    selectedRoomId = roomId;
    const dropdown = document.getElementById('room-selector-dropdown');
    if (dropdown) dropdown.value = roomId;

    renderFloorMap();
    renderRoomInspector();
}

// Render the details of equipment present in the selected room
function renderRoomInspector() {
    const room = allRooms.find(r => r.room_id === selectedRoomId);
    if (!room) return;

    // Room Header & Meta
    document.getElementById('inspector-room-name').innerText = `${room.name} Inspector`;

    const gw = allGateways.find(g => g.room_id === selectedRoomId);
    if (gw) {
        document.getElementById('insp-gw-id').innerText = gw.gateway_id;
        document.getElementById('insp-gw-ip').innerText = gw.ip_address;
    }

    const filtered = getFilteredAssets();
    const roomEquipment = filtered.filter(a => a.current_room_id === selectedRoomId);
    document.getElementById('inspector-count-badge').innerText = `${roomEquipment.length} Devices`;

    const container = document.getElementById('inspector-equipment-container');
    if (!container) return;

    if (roomEquipment.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; color: #64748b; padding: 2.5rem 1rem; background: #090e1a; border-radius: 8px; border: 1px dashed #1e293b;">
                <i class="fa-solid fa-box-open" style="font-size: 2rem; color: #475569; margin-bottom: 0.75rem;"></i>
                <div style="font-weight: 600; color: #94a3b8; font-size: 0.88rem;">No Equipment Present</div>
                <div style="font-size: 0.75rem; color: #64748b; margin-top: 0.25rem;">There are currently no assets registered in ${room.name}.</div>
            </div>
        `;
        return;
    }

    let html = '';
    roomEquipment.forEach(item => {
        let statusBadge = '<span class="status-badge status-badge-available">Available</span>';
        if (item.status === 'In Use') statusBadge = '<span class="status-badge status-badge-in-use">In Use</span>';
        if (item.status === 'Maintenance') statusBadge = '<span class="status-badge status-badge-maintenance">Maintenance</span>';

        const icon = CATEGORY_ICONS[item.category] || 'fa-kit-medical';
        const batteryColor = item.battery > 50 ? '#10b981' : (item.battery > 20 ? '#f59e0b' : '#ef4444');

        html += `
            <div style="background: #090e1a; border: 1px solid #1e293b; border-radius: 8px; padding: 0.85rem; margin-bottom: 0.75rem; transition: border-color 0.2s;" onmouseenter="this.style.borderColor='#38bdf8'" onmouseleave="this.style.borderColor='#1e293b'">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.4rem;">
                    <div style="display: flex; gap: 0.6rem; align-items: center;">
                        <div style="width: 32px; height: 32px; border-radius: 6px; background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.3); display: flex; align-items: center; justify-content: center; color: #38bdf8; font-size: 0.95rem;">
                            <i class="fa-solid ${icon}"></i>
                        </div>
                        <div>
                            <div style="font-weight: 700; font-size: 0.88rem; color: #f8fafc;">${item.name}</div>
                            <div style="font-size: 0.72rem; color: #94a3b8; font-family: var(--font-mono);">${item.asset_id} · ${item.model}</div>
                        </div>
                    </div>
                    ${statusBadge}
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.4rem; font-size: 0.74rem; background: #0c1322; padding: 0.45rem 0.65rem; border-radius: 4px; margin-top: 0.5rem;">
                    <div><span style="color: #64748b;">BLE Tag:</span> <span style="font-family: var(--font-mono); color: #2dd4bf;">${item.tag_id}</span></div>
                    <div><span style="color: #64748b;">RSSI:</span> <span style="font-family: var(--font-mono); color: #38bdf8;">${item.rssi} dBm</span></div>
                    <div><span style="color: #64748b;">Battery:</span> <span style="color: ${batteryColor}; font-weight: 700;">${item.battery}%</span></div>
                    <div><span style="color: #64748b;">Condition:</span> <span style="color: #94a3b8;">${item.maintenance_status}</span></div>
                </div>

                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem; font-size: 0.7rem; color: #64748b;">
                    <span>Last seen: ${item.last_updated.split(' ')[1] || item.last_updated}</span>
                    <a href="/movement" style="color: #38bdf8; text-decoration: none; font-weight: 600;">
                        <i class="fa-solid fa-arrow-right"></i> Move
                    </a>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

