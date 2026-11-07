/**
 * Smart Hospital Asset Tracking System
 * Manage Equipment Movement: Manual Controller & Movement History Logger
 */

let movementAssets = [];
let selectedAsset = null;

document.addEventListener('DOMContentLoaded', () => {
    initMovementPage();
});

async function initMovementPage() {
    await loadEquipmentList();
    await loadMovementHistory();
}

// 1. Load All Registered Equipment into Dropdown
async function loadEquipmentList(targetAssetIdToSelect = null) {
    try {
        const res = await fetch('/api/assets');
        if (!res.ok) return;
        movementAssets = await res.json();

        const select = document.getElementById('manage-equipment-select');
        if (!select) return;

        select.innerHTML = '<option value="">-- Choose Equipment to Relocate --</option>';
        movementAssets.forEach(a => {
            const opt = document.createElement('option');
            opt.value = a.asset_id;
            opt.textContent = `[${a.asset_id}] ${a.name} · Location: ${a.current_room_name}`;
            select.appendChild(opt);
        });

        // Determine which asset to select:
        // 1) Explicit target asset requested (e.g. after move)
        // 2) Previously selected asset ID
        // 3) Default to first asset in list
        let assetIdToSelect = targetAssetIdToSelect;
        if (!assetIdToSelect && selectedAsset) {
            assetIdToSelect = selectedAsset.asset_id;
        }
        if (!assetIdToSelect && movementAssets.length > 0) {
            assetIdToSelect = movementAssets[0].asset_id;
        }

        if (assetIdToSelect && movementAssets.some(a => a.asset_id === assetIdToSelect)) {
            select.value = assetIdToSelect;
        } else if (movementAssets.length > 0) {
            select.value = movementAssets[0].asset_id;
        }

        onEquipmentSelected();
    } catch (e) {
        console.error("Failed loading equipment list:", e);
    }
}

// 2. Handle Equipment Dropdown Change
function onEquipmentSelected() {
    const select = document.getElementById('manage-equipment-select');
    if (!select) return;
    const assetId = select.value;
    selectedAsset = movementAssets.find(a => a.asset_id === assetId);

    const infoCard = document.getElementById('selected-equipment-info');
    if (!selectedAsset) {
        if (infoCard) infoCard.classList.add('hidden');
        return;
    }

    if (infoCard) infoCard.classList.remove('hidden');

    document.getElementById('display-asset-name').innerText = selectedAsset.name;
    document.getElementById('display-asset-id').innerText = selectedAsset.asset_id;
    document.getElementById('display-asset-category').innerText = selectedAsset.category;
    document.getElementById('display-asset-model').innerText = selectedAsset.model;
    document.getElementById('display-asset-tag').innerText = `${selectedAsset.tag_id} (${selectedAsset.tag_mac})`;
    
    // Highlight Current Physical Location (Authoritative source of truth)
    const currLocEl = document.getElementById('display-current-location');
    if (currLocEl) {
        currLocEl.innerText = selectedAsset.current_room_name || selectedAsset.current_location;
    }

    // Display Assigned Base Department / Ward
    const assignedLocEl = document.getElementById('display-assigned-location');
    if (assignedLocEl) {
        assignedLocEl.innerText = selectedAsset.assigned_room_name || selectedAsset.assigned_location;
    }

    document.getElementById('display-battery').innerText = `${selectedAsset.battery}%`;
    document.getElementById('display-status').innerText = selectedAsset.status;

    // Default "Move To" destination to an available room different from current room
    const destSelect = document.getElementById('manage-destination-select');
    if (destSelect) {
        const availableOptions = Array.from(destSelect.options).filter(o => o.value && o.value !== selectedAsset.current_room_id);
        if (availableOptions.length > 0) {
            destSelect.value = availableOptions[0].value;
        }
    }
}

// 3. Move Equipment Button Handler (Explicit Action)
async function handleMoveEquipment() {
    if (window.CURRENT_USER && window.CURRENT_USER.role !== 'ADMIN') {
        showToast(`Access Denied: Only Administrator has permission to manually move equipment. (Current role: ${window.CURRENT_USER.role})`, "error");
        return;
    }

    if (!selectedAsset) {
        showToast("Please select an equipment item first", "warning");
        return;
    }

    const destSelect = document.getElementById('manage-destination-select');
    const targetRoomId = destSelect.value;
    const movedAssetId = selectedAsset.asset_id;

    if (!targetRoomId) {
        showToast("Please choose a destination location", "warning");
        return;
    }

    if (targetRoomId === selectedAsset.current_room_id) {
        showToast(`'${selectedAsset.name}' is already in ${selectedAsset.current_room_name}`, "info");
        return;
    }

    const syncCheck = document.getElementById('sync-assigned-check');
    const syncAssigned = syncCheck ? syncCheck.checked : false;

    const moveBtn = document.getElementById('btn-move-equipment');
    if (moveBtn) {
        moveBtn.disabled = true;
        moveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Relocating Equipment...';
    }

    try {
        const res = await fetch('/api/move', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                asset_id: movedAssetId,
                room_id: targetRoomId,
                sync_assigned: syncAssigned
            })
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

            // Refresh local asset data and keep the moved asset selected
            await loadEquipmentList(movedAssetId);

            // Reload movement history table immediately
            await loadMovementHistory();

            // Refresh live floor map if open
            if (window.fetchRealtimeState) window.fetchRealtimeState();
        } else {
            showToast("Failed to move: " + (data.error || data.message || "Unknown error"), "error");
        }
    } catch (e) {
        showToast("Network error executing move: " + e.message, "error");
    } finally {
        if (moveBtn) {
            moveBtn.disabled = false;
            moveBtn.innerHTML = '<i class="fa-solid fa-arrows-up-down-left-right"></i> Move Equipment Now';
        }
    }
}

// 4. Load Movement History Table
async function loadMovementHistory() {
    try {
        const res = await fetch('/api/movement/history?limit=50');
        if (!res.ok) return;
        const history = await res.json();

        const tableBody = document.getElementById('movement-history-body');
        const countBadge = document.getElementById('movement-count-badge');
        if (!tableBody) return;

        if (countBadge) countBadge.innerText = `${history.length} Movements Logged`;

        if (history.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="6" style="text-align: center; padding: 2rem; color: #94a3b8;">
                        <i class="fa-solid fa-clock-rotate-left" style="font-size: 1.5rem; display: block; margin-bottom: 0.5rem; color: #475569;"></i>
                        No manual movements recorded yet. Use the controls above to move equipment.
                    </td>
                </tr>
            `;
            return;
        }

        let html = '';
        history.forEach(item => {
            const isInitial = !item.previous_room_id;
            html += `
                <tr>
                    <td style="font-family: monospace; font-size: 0.78rem; color: #64748b; white-space: nowrap;">
                        <i class="fa-regular fa-clock" style="margin-right: 4px;"></i>${item.timestamp}
                    </td>
                    <td>
                        <div style="font-weight: 700; color: #f8fafc;">${item.asset_name}</div>
                        <div style="font-size: 0.7rem; color: #38bdf8; font-family: monospace;">${item.asset_id} &middot; Tag: ${item.tag_id}</div>
                    </td>
                    <td>
                        <span style="font-size: 0.75rem; background: rgba(148, 163, 184, 0.12); color: #cbd5e1; padding: 0.2rem 0.55rem; border-radius: 4px; border: 1px solid rgba(148, 163, 184, 0.25);">
                            ${item.previous_room_name}
                        </span>
                    </td>
                    <td>
                        <span style="font-size: 0.8rem; font-weight: 700; background: rgba(16, 185, 129, 0.15); color: #34d399; padding: 0.2rem 0.65rem; border-radius: 4px; border: 1px solid rgba(16, 185, 129, 0.35); display: inline-flex; align-items: center; gap: 0.3rem;">
                            <i class="fa-solid fa-arrow-right" style="font-size: 0.65rem;"></i> ${item.new_room_name}
                        </span>
                    </td>
                    <td>
                        <div style="font-size: 0.75rem; font-weight: 600; color: #e2e8f0;">${item.gateway_name}</div>
                        <div style="font-size: 0.68rem; color: #38bdf8; font-family: monospace;">IP: ${item.gateway_ip}</div>
                    </td>
                    <td style="font-family: monospace; font-size: 0.73rem; color: #94a3b8;">
                        <span style="color: #2dd4bf;">${item.rssi} dBm</span> <span style="color: #64748b;">(~${item.distance_m}m)</span>
                    </td>
                </tr>
            `;
        });

        tableBody.innerHTML = html;
    } catch (e) {
        console.error("Failed loading movement history:", e);
    }
}

