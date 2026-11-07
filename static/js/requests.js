/**
 * Smart Hospital Asset Tracking System
 * Equipment Request Management: Department Requisitions & Admin Dispatch Controller
 */

let allRequests = [];
let allAssets = [];
let currentTab = 'Pending';
let selectedRejectRequestId = null;
let pendingApprovalRequestId = null;

document.addEventListener('DOMContentLoaded', () => {
    initRequestsPage();
});

async function initRequestsPage() {
    await loadAssetsForRequests();
    await loadAllRequests();
    
    // Auto-refresh requests table & badges every 3 seconds
    setInterval(async () => {
        await loadAllRequests(true);
    }, 3000);
}

// 1. Load Registered Assets into Dropdown
async function loadAssetsForRequests() {
    try {
        const res = await fetch('/api/assets');
        if (!res.ok) return;
        allAssets = await res.json();

        const select = document.getElementById('req-equipment-select');
        if (!select) return;

        const currentVal = select.value;
        select.innerHTML = '<option value="">-- Choose Medical Equipment --</option>';

        allAssets.forEach(a => {
            const opt = document.createElement('option');
            opt.value = a.asset_id;
            opt.textContent = `[${a.asset_id}] ${a.name} · Current: ${a.current_room_name}`;
            select.appendChild(opt);
        });

        if (currentVal && allAssets.some(a => a.asset_id === currentVal)) {
            select.value = currentVal;
        } else if (allAssets.length > 0) {
            select.value = allAssets[0].asset_id;
        }

        onAssetSelectedForRequest();
    } catch (e) {
        console.error("Failed loading assets for request form:", e);
    }
}

// 2. Automatically Identify Current Equipment Location & Update Route Preview
function onAssetSelectedForRequest() {
    const select = document.getElementById('req-equipment-select');
    const assetId = select ? select.value : '';
    const asset = allAssets.find(a => a.asset_id === assetId);

    const fromLocEl = document.getElementById('preview-from-location');
    const fromMetaEl = document.getElementById('preview-from-meta');
    const toLocEl = document.getElementById('preview-to-location');
    const destSelect = document.getElementById('req-destination-select');
    const targetRoomId = destSelect ? destSelect.value : '';
    const targetRoomName = destSelect ? destSelect.options[destSelect.selectedIndex]?.text : '';

    const validationBanner = document.getElementById('route-validation-banner');
    const validationIcon = document.getElementById('route-validation-icon');
    const validationText = document.getElementById('route-validation-text');
    const submitBtn = document.getElementById('btn-submit-request');

    if (!asset) {
        if (fromLocEl) fromLocEl.innerText = "Select equipment to detect location...";
        if (fromMetaEl) fromMetaEl.innerText = "";
        return;
    }

    // Auto-detected current physical location (strictly from DB)
    if (fromLocEl) {
        fromLocEl.innerText = `${asset.current_room_name}`;
    }
    if (fromMetaEl) {
        fromMetaEl.innerText = `Tag: ${asset.tag_id} · Gateway: ${asset.gateway_name || asset.current_gateway_id} (${asset.gateway_ip || 'VLAN 20'})`;
    }

    if (toLocEl) {
        toLocEl.innerText = targetRoomName || targetRoomId;
    }

    // Route Validation Rules:
    // Rule 1: Equipment cannot be requested if already in destination ward
    if (asset.current_room_id === targetRoomId) {
        if (validationBanner && validationText && validationIcon) {
            validationBanner.className = "alert-banner-warning";
            validationBanner.style.background = "rgba(245, 158, 11, 0.15)";
            validationBanner.style.border = "1px solid rgba(245, 158, 11, 0.4)";
            validationBanner.style.color = "#fbbf24";
            validationBanner.classList.remove('hidden');
            validationIcon.className = "fa-solid fa-triangle-exclamation";
            validationText.innerHTML = `<strong>Invalid Transfer:</strong> '${asset.name}' is already physically located in <strong>${asset.current_room_name}</strong>. Choose another destination or equipment.`;
        }
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.classList.add('disabled');
        }
        return;
    }

    // Rule 2: Check for existing pending request
    const existingPending = allRequests.find(r => r.asset_id === asset.asset_id && r.destination_room_id === targetRoomId && r.status === 'Pending');
    if (existingPending) {
        if (validationBanner && validationText && validationIcon) {
            validationBanner.className = "alert-banner-warning";
            validationBanner.style.background = "rgba(245, 158, 11, 0.15)";
            validationBanner.style.border = "1px solid rgba(245, 158, 11, 0.4)";
            validationBanner.style.color = "#fbbf24";
            validationBanner.classList.remove('hidden');
            validationIcon.className = "fa-solid fa-clock";
            validationText.innerHTML = `<strong>Duplicate Request:</strong> A pending request (#REQ-${existingPending.id}) for this equipment to <strong>${targetRoomName}</strong> is already awaiting admin approval.`;
        }
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.classList.add('disabled');
        }
        return;
    }

    // Valid Route:
    if (validationBanner && validationText && validationIcon) {
        validationBanner.className = "alert-banner-success";
        validationBanner.style.background = "rgba(16, 185, 129, 0.12)";
        validationBanner.style.border = "1px solid rgba(16, 185, 129, 0.35)";
        validationBanner.style.color = "#34d399";
        validationBanner.classList.remove('hidden');
        validationIcon.className = "fa-solid fa-circle-check";
        validationText.innerHTML = `<strong>Route Verified:</strong> Ready to request transfer of '${asset.name}' from ${asset.current_room_name} to ${targetRoomName}.`;
    }
    if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.classList.remove('disabled');
    }
}

// 3. Handle Requesting Department Change
function onRequestingDepartmentChanged() {
    const deptSelect = document.getElementById('req-department-select');
    const destSelect = document.getElementById('req-destination-select');
    if (deptSelect && destSelect) {
        // By default, requested destination is the requesting department
        destSelect.value = deptSelect.value;
    }
    onAssetSelectedForRequest();
}

function onDestinationRoomChanged() {
    onAssetSelectedForRequest();
}

// 4. Submit Equipment Request Handler
async function handleSubmitEquipmentRequest() {
    const deptSelect = document.getElementById('req-department-select');
    const equipSelect = document.getElementById('req-equipment-select');
    const destSelect = document.getElementById('req-destination-select');
    const qtyInput = document.getElementById('req-quantity-input');
    const reasonInput = document.getElementById('req-reason-input');

    const assetId = equipSelect ? equipSelect.value : '';
    const requestingRoomId = deptSelect ? deptSelect.value : '';
    const destinationRoomId = destSelect ? destSelect.value : requestingRoomId;
    const quantity = parseInt(qtyInput ? qtyInput.value : 1) || 1;
    const reason = reasonInput ? reasonInput.value.trim() : '';

    if (!assetId) {
        showToast("Please choose an equipment item to request", "warning");
        return;
    }

    if (!requestingRoomId) {
        showToast("Please choose the requesting department", "warning");
        return;
    }

    const submitBtn = document.getElementById('btn-submit-request');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Submitting Request...';
    }

    try {
        const res = await fetch('/api/requests', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                asset_id: assetId,
                requesting_room_id: requestingRoomId,
                destination_room_id: destinationRoomId,
                quantity: quantity,
                reason: reason
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

            // Reset reason input
            if (reasonInput) reasonInput.value = '';

            // Reload requests registry and refresh navbar notification badge
            await loadAllRequests();
            if (window.updatePendingRequestsNavbar) window.updatePendingRequestsNavbar();
        } else {
            showToast(data.error || "Failed to submit request", "error");
        }
    } catch (e) {
        showToast("Error submitting request: " + e.message, "error");
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Submit Requisition';
        }
        onAssetSelectedForRequest();
    }
}

// 5. Load All Equipment Requests from API
async function loadAllRequests(silent = false) {
    try {
        const res = await fetch('/api/requests?limit=100');
        if (!res.ok) return;
        allRequests = await res.json();

        updateRequestKPIs();
        renderRequestsTable();

        // Also refresh assets list in background to ensure location freshness
        const assetRes = await fetch('/api/assets');
        if (assetRes.ok) {
            allAssets = await assetRes.json();
            if (!silent) {
                onAssetSelectedForRequest();
            }
        }
    } catch (e) {
        if (!silent) console.error("Failed loading requests:", e);
    }
}

// 6. Update KPI Badges & Tab Counters
function updateRequestKPIs() {
    const total = allRequests.length;
    const pending = allRequests.filter(r => r.status === 'Pending').length;
    const approved = allRequests.filter(r => r.status === 'Approved' || r.status === 'Completed').length;
    const rejected = allRequests.filter(r => r.status === 'Rejected').length;

    // KPI Cards
    const totalEl = document.getElementById('kpi-total-requests');
    const pendingEl = document.getElementById('kpi-pending-requests');
    const approvedEl = document.getElementById('kpi-approved-requests');
    const rejectedEl = document.getElementById('kpi-rejected-requests');
    const badgeEl = document.getElementById('kpi-pending-badge');

    if (totalEl) totalEl.innerText = total;
    if (pendingEl) pendingEl.innerText = pending;
    if (approvedEl) approvedEl.innerText = approved;
    if (rejectedEl) rejectedEl.innerText = rejected;
    if (badgeEl) badgeEl.innerText = pending;

    // Tab Counters
    const tabPendingCount = document.getElementById('tab-pending-count');
    const tabAllCount = document.getElementById('tab-all-count');
    const tabApprovedCount = document.getElementById('tab-approved-count');
    const tabRejectedCount = document.getElementById('tab-rejected-count');

    if (tabPendingCount) tabPendingCount.innerText = pending;
    if (tabAllCount) tabAllCount.innerText = total;
    if (tabApprovedCount) tabApprovedCount.innerText = approved;
    if (tabRejectedCount) tabRejectedCount.innerText = rejected;

    // Pending indicator pill
    const indicator = document.getElementById('requests-pending-indicator');
    if (indicator) {
        if (pending > 0) {
            indicator.className = "status-pill status-pill-warning";
            indicator.style.display = "inline-flex";
        } else {
            indicator.className = "status-pill status-pill-success";
            indicator.innerHTML = '<i class="fa-solid fa-circle-check"></i> 0 Pending Requests';
        }
    }
}

// 7. Tab Switching
function switchTab(tabName) {
    currentTab = tabName;
    ['pending', 'all', 'approved', 'rejected'].forEach(t => {
        const btn = document.getElementById(`tab-${t}`);
        if (btn) {
            if (t.toLowerCase() === tabName.toLowerCase()) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        }
    });
    renderRequestsTable();
}

// 8. Render Requests Registry Table
function renderRequestsTable() {
    const tableBody = document.getElementById('requests-table-body');
    if (!tableBody) return;

    const searchTerm = (document.getElementById('requests-search-input')?.value || '').toLowerCase();
    const roomFilter = document.getElementById('filter-room-select')?.value || '';

    const filtered = allRequests.filter(r => {
        // Tab filter
        let matchTab = true;
        if (currentTab === 'Pending') matchTab = (r.status === 'Pending');
        else if (currentTab === 'Approved') matchTab = (r.status === 'Approved' || r.status === 'Completed');
        else if (currentTab === 'Rejected') matchTab = (r.status === 'Rejected');

        // Department filter
        let matchRoom = true;
        if (roomFilter) {
            matchRoom = (r.requesting_room_id === roomFilter || r.destination_room_id === roomFilter);
        }

        // Search filter
        let matchSearch = true;
        if (searchTerm) {
            matchSearch = r.asset_name.toLowerCase().includes(searchTerm) ||
                          r.asset_id.toLowerCase().includes(searchTerm) ||
                          r.requesting_room_name.toLowerCase().includes(searchTerm) ||
                          r.destination_room_name.toLowerCase().includes(searchTerm) ||
                          (r.reason && r.reason.toLowerCase().includes(searchTerm));
        }

        return matchTab && matchRoom && matchSearch;
    });

    if (filtered.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="9" style="text-align: center; padding: 2.5rem; color: #94a3b8;">
                    <i class="fa-solid fa-inbox text-cyan" style="font-size: 1.8rem; display: block; margin-bottom: 0.5rem; opacity: 0.5;"></i>
                    No equipment requisitions found for this view filter.
                </td>
            </tr>
        `;
        return;
    }

    let html = '';
    filtered.forEach(req => {
        const isPending = req.status === 'Pending';
        const isApproved = req.status === 'Approved' || req.status === 'Completed';
        const isRejected = req.status === 'Rejected';

        let statusBadgeClass = 'status-badge-pending';
        let statusIcon = 'fa-hourglass-half';
        if (isApproved) { statusBadgeClass = 'status-badge-approved'; statusIcon = 'fa-circle-check'; }
        if (isRejected) { statusBadgeClass = 'status-badge-rejected'; statusIcon = 'fa-circle-xmark'; }

        // Route display
        const locChanged = req.location_changed_since_request;
        const currentLiveLocation = req.live_current_room_name || req.current_room_name_at_request;

        html += `
            <tr style="${isPending ? 'background: rgba(245, 158, 11, 0.04);' : ''}">
                <td style="font-weight: 700; color: #38bdf8; font-family: monospace;">
                    #REQ-${req.id}
                </td>
                <td style="font-size: 0.78rem; color: #94a3b8; white-space: nowrap;">
                    ${req.created_at}
                </td>
                <td>
                    <div style="font-weight: 700; color: #f8fafc;">${req.asset_name}</div>
                    <div style="font-size: 0.72rem; color: #38bdf8; font-family: monospace;">
                        ${req.asset_id} &middot; <span style="color: #94a3b8;">${req.category}</span>
                    </div>
                </td>
                <td>
                    <div style="display: flex; align-items: center; gap: 0.4rem; font-size: 0.82rem; font-weight: 700;">
                        <span style="color: #22d3ee;"><i class="fa-solid fa-map-pin"></i> ${req.current_room_name_at_request}</span>
                        <i class="fa-solid fa-arrow-right" style="color: #64748b; font-size: 0.7rem;"></i>
                        <span style="color: #34d399;"><i class="fa-solid fa-hospital-user"></i> ${req.destination_room_name}</span>
                    </div>
                    ${locChanged ? `
                        <div style="font-size: 0.7rem; color: #fbbf24; margin-top: 0.2rem;">
                            <i class="fa-solid fa-triangle-exclamation"></i> Now in ${currentLiveLocation}
                        </div>
                    ` : `
                        <div style="font-size: 0.7rem; color: #64748b; margin-top: 0.2rem;">
                            Current live: ${currentLiveLocation}
                        </div>
                    `}
                </td>
                <td>
                    <div style="font-weight: 600; color: #cbd5e1;">${req.requesting_room_name}</div>
                </td>
                <td>
                    <div style="font-size: 0.8rem; color: #f1f5f9;">Qty: <strong>${req.quantity}</strong></div>
                    <div style="font-size: 0.75rem; color: #94a3b8; max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${req.reason || 'None'}">
                        ${req.reason || '<em style="color: #64748b;">No clinical reason stated</em>'}
                    </div>
                </td>
                <td>
                    <span class="status-badge ${statusBadgeClass}">
                        <i class="fa-solid ${statusIcon}"></i> ${req.status}
                    </span>
                </td>
                <td>
                    <div style="font-size: 0.78rem;">
                        ${isPending ? `
                            <span style="color: #fbbf24;"><i class="fa-solid fa-clock"></i> Awaiting Action</span>
                        ` : ''}
                        ${isApproved ? `
                            <div style="color: #34d399; font-weight: 700;">
                                <i class="fa-solid fa-check-double"></i> Approved by Admin
                            </div>
                            <div style="font-size: 0.7rem; color: #64748b;">${req.decision_at || ''}</div>
                        ` : ''}
                        ${isRejected ? `
                            <div style="color: #f87171; font-weight: 700;">
                                <i class="fa-solid fa-ban"></i> Declined
                            </div>
                            <div style="font-size: 0.7rem; color: #94a3b8; font-style: italic;">
                                ${req.rejection_reason || 'No reason provided'}
                            </div>
                        ` : ''}
                    </div>
                </td>
                <td style="text-align: right;">
                    ${isPending ? (
                        (window.CURRENT_USER && window.CURRENT_USER.role !== 'ADMIN') ? `
                            <span class="status-badge" style="background: rgba(148, 163, 184, 0.15); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.3);">
                                <i class="fa-solid fa-hourglass-half"></i> Pending Review
                            </span>
                        ` : `
                            <div style="display: inline-flex; gap: 0.4rem;">
                                <button class="btn btn-sm btn-cyan" onclick="approveRequest(${req.id})" title="Approve Request & Dispatch Equipment">
                                    <i class="fa-solid fa-check"></i> Accept
                                </button>
                                <button class="btn btn-sm btn-danger" onclick="openRejectModal(${req.id})" title="Decline Requisition">
                                    <i class="fa-solid fa-xmark"></i> Reject
                                </button>
                            </div>
                        `
                    ) : ''}
                    ${isApproved ? `
                        <span style="font-size: 0.75rem; color: #34d399; font-weight: 700;">
                            <i class="fa-solid fa-truck-ramp-box"></i> Dispatched
                        </span>
                    ` : ''}
                    ${isRejected ? `
                        <span style="font-size: 0.75rem; color: #f87171; font-weight: 700;">
                            <i class="fa-solid fa-xmark"></i> Declined
                        </span>
                    ` : ''}
                </td>
            </tr>
        `;
    });

    tableBody.innerHTML = html;
}

// 9. Administrator: Accept / Approve Request
async function approveRequest(requestId, force = false) {
    if (window.CURRENT_USER && window.CURRENT_USER.role !== 'ADMIN') {
        showToast(`Access Denied: Only Administrator has permission to accept or reject requests. (Current role: ${window.CURRENT_USER.role})`, "error");
        return;
    }

    try {
        const res = await fetch(`/api/requests/${requestId}/approve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ force: force })
        });

        let data;
        const contentType = res.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            data = await res.json();
        } else {
            throw new Error(`Server returned HTTP ${res.status}`);
        }

        // If location changed in the interim, prompt confirmation
        if (data.status === 'warning' && data.needs_confirmation) {
            pendingApprovalRequestId = requestId;
            const modalText = document.getElementById('confirm-move-modal-text');
            if (modalText) {
                modalText.innerHTML = `${data.message}`;
            }
            const modal = document.getElementById('confirm-move-modal');
            if (modal) modal.classList.remove('hidden');
            return;
        }

        if (res.ok && data.status === 'success') {
            showToast(data.message, "success");
            playHospitalAlertChime('INFO');

            // Refresh requests list, navbar badge, and live floor map
            await loadAllRequests();
            if (window.updatePendingRequestsNavbar) window.updatePendingRequestsNavbar();
            if (window.fetchRealtimeState) window.fetchRealtimeState();
        } else {
            showToast(data.error || "Failed to approve request", "error");
        }
    } catch (e) {
        showToast("Error approving request: " + e.message, "error");
    }
}

function closeConfirmMoveModal() {
    pendingApprovalRequestId = null;
    const modal = document.getElementById('confirm-move-modal');
    if (modal) modal.classList.add('hidden');
}

async function proceedForcedApproval() {
    if (!pendingApprovalRequestId) return;
    const reqId = pendingApprovalRequestId;
    closeConfirmMoveModal();
    await approveRequest(reqId, true);
}

// 10. Administrator: Reject Request
function openRejectModal(requestId) {
    if (window.CURRENT_USER && window.CURRENT_USER.role !== 'ADMIN') {
        showToast(`Access Denied: Only Administrator has permission to accept or reject requests. (Current role: ${window.CURRENT_USER.role})`, "error");
        return;
    }

    const req = allRequests.find(r => r.id === requestId);
    if (!req) return;

    selectedRejectRequestId = requestId;
    const idEl = document.getElementById('reject-modal-req-id');
    const nameEl = document.getElementById('reject-modal-asset-name');
    const reasonText = document.getElementById('reject-reason-text');

    if (idEl) idEl.innerText = req.id;
    if (nameEl) nameEl.innerText = req.asset_name;
    if (reasonText) reasonText.value = '';

    const modal = document.getElementById('reject-modal');
    if (modal) modal.classList.remove('hidden');
}

function closeRejectModal() {
    selectedRejectRequestId = null;
    const modal = document.getElementById('reject-modal');
    if (modal) modal.classList.add('hidden');
}

async function submitRejection() {
    if (!selectedRejectRequestId) return;
    const reqId = selectedRejectRequestId;
    const reasonText = document.getElementById('reject-reason-text')?.value || '';

    try {
        const res = await fetch(`/api/requests/${reqId}/reject`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rejection_reason: reasonText })
        });

        let data;
        const contentType = res.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            data = await res.json();
        } else {
            throw new Error(`Server returned HTTP ${res.status}`);
        }

        if (res.ok && data.status === 'success') {
            showToast(data.message, "warning");
            playHospitalAlertChime('WARNING');
            closeRejectModal();

            // Refresh requests list and navbar badge
            await loadAllRequests();
            if (window.updatePendingRequestsNavbar) window.updatePendingRequestsNavbar();
        } else {
            showToast(data.error || "Failed to reject request", "error");
        }
    } catch (e) {
        showToast("Error rejecting request: " + e.message, "error");
    }
}

