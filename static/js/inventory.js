/**
 * Smart Hospital Asset Tracking System
 * Asset Inventory Management & Maintenance Tracker
 */

let allAssets = [];

document.addEventListener('DOMContentLoaded', () => {
    loadInventory();
    // Auto-refresh every 3 seconds to reflect live movements
    setInterval(loadInventory, 3000);
});

async function loadInventory() {
    try {
        const res = await fetch('/api/assets');
        if (!res.ok) return;
        allAssets = await res.json();
        renderTable();
    } catch (e) {
        console.warn("Failed loading assets:", e);
    }
}

function renderTable() {
    const tableBody = document.getElementById('inventory-table-body');
    if (!tableBody) return;

    const searchTerm = (document.getElementById('inventory-search')?.value || '').toLowerCase();
    const categoryFilter = document.getElementById('inventory-filter-cat')?.value || '';
    const statusFilter = document.getElementById('inventory-filter-status')?.value || '';
    const roomFilter = document.getElementById('inventory-filter-room')?.value || '';

    const filtered = allAssets.filter(a => {
        const matchSearch = a.name.toLowerCase().includes(searchTerm) ||
                            a.asset_id.toLowerCase().includes(searchTerm) ||
                            a.model.toLowerCase().includes(searchTerm) ||
                            a.tag_id.toLowerCase().includes(searchTerm);
        const matchCat = !categoryFilter || a.category === categoryFilter;
        const matchStatus = !statusFilter || a.status === statusFilter;
        const matchRoom = !roomFilter || a.current_room_id === roomFilter;
        return matchSearch && matchCat && matchStatus && matchRoom;
    });

    document.getElementById('inventory-count-badge').innerText = `${filtered.length} of ${allAssets.length} Assets`;

    if (filtered.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="9" style="text-align: center; padding: 2rem; color: #94a3b8;">
                    No assets found matching the selected filter criteria.
                </td>
            </tr>
        `;
        return;
    }

    let html = '';
    filtered.forEach(asset => {
        const isBreached = asset.current_room_id !== asset.assigned_room_id && 
                           (asset.category === 'Ventilator' || asset.current_room_id === 'EXIT');

        // Battery gauge color
        let battColor = '#10b981';
        if (asset.battery <= 20) battColor = '#ef4444';
        else if (asset.battery <= 50) battColor = '#f59e0b';

        // Status chip
        let statusBadgeClass = 'status-badge-avail';
        if (asset.status === 'In Use') statusBadgeClass = 'status-badge-inuse';
        if (asset.status === 'Maintenance') statusBadgeClass = 'status-badge-maint';

        html += `
            <tr style="${isBreached ? 'background: rgba(239, 68, 68, 0.08);' : ''}">
                <td style="font-weight: 700; color: #38bdf8; font-family: monospace;">
                    ${asset.asset_id}
                </td>
                <td>
                    <div style="font-weight: 600; color: #f8fafc;">${asset.name}</div>
                    <div style="font-size: 0.7rem; color: #94a3b8;">${asset.model}</div>
                </td>
                <td>
                    <span style="font-size: 0.78rem; background: rgba(255,255,255,0.05); padding: 0.2rem 0.5rem; border-radius: 4px;">
                        ${asset.category}
                    </span>
                </td>
                <td style="font-family: monospace; font-size: 0.75rem;">
                    <div>${asset.tag_id}</div>
                    <div style="color: #64748b; font-size: 0.68rem;">${asset.tag_mac}</div>
                </td>
                <td>
                    <div style="font-weight: 700; color: ${isBreached ? '#ef4444' : '#22d3ee'};">
                        ${isBreached ? '<i class="fa-solid fa-triangle-exclamation"></i> ' : '<i class="fa-solid fa-location-dot"></i> '}${asset.current_room_name}
                    </div>
                    <div style="font-size: 0.7rem; color: #94a3b8;">
                        <i class="fa-solid fa-house-medical"></i> Base: ${asset.assigned_room_name}
                    </div>
                </td>
                <td>
                    <div style="display: flex; align-items: center; gap: 0.4rem;">
                        <div style="width: 45px; height: 7px; background: #1e293b; border-radius: 4px; overflow: hidden;">
                            <div style="width: ${asset.battery}%; height: 100%; background: ${battColor};"></div>
                        </div>
                        <span style="font-size: 0.75rem; font-weight: 700; color: ${battColor};">${asset.battery}%</span>
                    </div>
                </td>
                <td style="font-size: 0.75rem; font-family: monospace;">
                    ${asset.rssi} dBm <span style="color: #64748b;">(~${asset.distance_m}m)</span>
                </td>
                <td>
                    <span class="status-chip ${statusBadgeClass}">
                        ${asset.status}
                    </span>
                </td>
                <td style="white-space: nowrap;">
                    ${(window.CURRENT_USER && window.CURRENT_USER.role === 'ADMIN') ? `
                        <button class="btn btn-sm btn-cyan" onclick="openRelocateModal('${asset.asset_id}', '${asset.current_room_id}')" title="Move Equipment">
                            <i class="fa-solid fa-arrows-up-down-left-right"></i> Move
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="confirmDeleteAsset('${asset.asset_id}', '${asset.name.replace(/'/g, "\\'")}')" title="Delete Equipment (Admin Only)" style="margin-left: 4px;">
                            <i class="fa-solid fa-trash-can"></i> Delete
                        </button>
                    ` : `
                        <span style="font-size: 0.75rem; color: #64748b; font-style: italic;">View Only</span>
                    `}
                </td>
            </tr>
        `;
    });

    tableBody.innerHTML = html;
}

function openRelocateModal(assetId, currRoom) {
    if (window.CURRENT_USER && window.CURRENT_USER.role !== 'ADMIN') {
        showToast("Access Denied: Only Administrator has permission to manually move equipment.", "error");
        return;
    }
    const sel = document.getElementById('modal-asset-select');
    const roomSel = document.getElementById('modal-room-select');
    if (sel) sel.value = assetId;
    if (roomSel) roomSel.value = currRoom;
    openDemoModal();
}

async function confirmDeleteAsset(assetId, assetName) {
    if (window.CURRENT_USER && window.CURRENT_USER.role !== 'ADMIN') {
        showToast("Access Denied: Only Administrator has permission to delete equipment.", "error");
        return;
    }

    const confirmMsg = `Are you sure you want to permanently delete '${assetName}' (${assetId}) from the hospital equipment fleet?\n\nThis will remove it from active tracking, live floor map, and equipment lists while preserving historical audit logs.`;
    if (!confirm(confirmMsg)) {
        return;
    }

    try {
        const res = await fetch(`/api/equipment/${encodeURIComponent(assetId)}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
        });

        const contentType = res.headers.get('content-type') || '';
        let data;
        if (contentType.includes('application/json')) {
            data = await res.json();
        } else {
            throw new Error(`Server returned HTTP ${res.status}`);
        }

        if (res.ok && data.status === 'success') {
            showToast(data.message || `Equipment ${assetId} deleted successfully.`, "success");
            playHospitalAlertChime('INFO');
            await loadInventory();
            if (window.fetchRealtimeState) window.fetchRealtimeState();
        } else {
            showToast("Failed to delete equipment: " + (data.error || data.message || "Unknown error"), "error");
        }
    } catch (e) {
        showToast("Error deleting equipment: " + e.message, "error");
    }
}

