/**
 * Feature 3: Maintenance Management Controller
 * Handles maintenance logging, due date calculations, overdue alerts, and history.
 */

let maintenanceRecords = [];
let maintenanceSummary = {};

document.addEventListener('DOMContentLoaded', () => {
    initDefaultDates();
    loadMaintenanceData();
    setInterval(loadMaintenanceData, 4000);
});

// Set sensible initial dates
function initDefaultDates() {
    const today = new Date();
    const todayStr = today.toISOString().split('T')[0];

    // +90 days for due date
    const dueDate = new Date();
    dueDate.setDate(dueDate.getDate() + 90);
    const dueDateStr = dueDate.toISOString().split('T')[0];

    const lastDateInput = document.getElementById('maint-last-date');
    const dueDateInput = document.getElementById('maint-due-date');
    if (lastDateInput && !lastDateInput.value) lastDateInput.value = todayStr;
    if (dueDateInput && !dueDateInput.value) dueDateInput.value = dueDateStr;
}

// Fetch maintenance data from backend
async function loadMaintenanceData() {
    try {
        const res = await fetch('/api/maintenance');
        if (!res.ok) return;
        const data = await res.json();

        maintenanceRecords = data.records || [];
        maintenanceSummary = data.summary || {};

        // Dynamically synchronize equipment select dropdown options
        const assetRes = await fetch('/api/assets');
        if (assetRes.ok) {
            const assets = await assetRes.json();
            const select = document.getElementById('maint-asset-select');
            if (select) {
                const currentVal = select.value;
                select.innerHTML = '<option value="">-- Choose Equipment Asset --</option>';
                assets.forEach(a => {
                    const opt = document.createElement('option');
                    opt.value = a.asset_id;
                    opt.setAttribute('data-status', a.maintenance_status);
                    opt.setAttribute('data-room', a.current_room_name);
                    opt.textContent = `[${a.asset_id}] ${a.name} • Current: ${a.current_room_name} (${a.maintenance_status})`;
                    select.appendChild(opt);
                });
                if (currentVal && assets.some(a => a.asset_id === currentVal)) {
                    select.value = currentVal;
                }
            }
        }

        updateKPIs();
        renderOverdueSection();
        renderHistoryTable();
    } catch (e) {
        console.warn("Error fetching maintenance data:", e);
    }
}

// Update KPI cards
function updateKPIs() {
    if (!maintenanceSummary) return;

    document.getElementById('kpi-good').innerText = maintenanceSummary.good || 0;
    document.getElementById('kpi-due-soon').innerText = maintenanceSummary.due_soon || 0;
    document.getElementById('kpi-under-maint').innerText = maintenanceSummary.under_maintenance || 0;
    document.getElementById('kpi-needs-repair').innerText = maintenanceSummary.needs_repair || 0;
    document.getElementById('kpi-overdue').innerText = maintenanceSummary.overdue_count || 0;

    const overdueBadge = document.getElementById('overdue-badge-count');
    if (overdueBadge) {
        overdueBadge.innerText = `${maintenanceSummary.overdue_count || 0} Alerts`;
    }
}

// Auto-fill status when an asset is selected
function onAssetSelectedForMaint() {
    const select = document.getElementById('maint-asset-select');
    const selectedOption = select.options[select.selectedIndex];
    if (!selectedOption || !selectedOption.value) return;

    const currentStatus = selectedOption.getAttribute('data-status');
    const statusSelect = document.getElementById('maint-status');
    if (statusSelect && currentStatus) {
        statusSelect.value = currentStatus;
    }
}

// Render the Overdue / Attention Required sidebar
function renderOverdueSection() {
    const container = document.getElementById('overdue-items-container');
    if (!container) return;

    const overdueItems = maintenanceSummary.overdue_items || [];

    if (overdueItems.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; color: #64748b; padding: 2.5rem 1rem; background: #090e1a; border-radius: 8px; border: 1px dashed #1e293b;">
                <i class="fa-solid fa-shield-heart" style="font-size: 2rem; color: #10b981; margin-bottom: 0.75rem;"></i>
                <div style="font-weight: 600; color: #34d399; font-size: 0.88rem;">All Systems Compliant</div>
                <div style="font-size: 0.75rem; color: #64748b; margin-top: 0.25rem;">No equipment currently has overdue maintenance deadlines.</div>
            </div>
        `;
        return;
    }

    let html = '';
    overdueItems.forEach(item => {
        let badgeColor = '#f59e0b';
        if (item.maintenance_status === 'Needs Repair') badgeColor = '#ef4444';
        if (item.maintenance_status === 'Under Maintenance') badgeColor = '#c084fc';

        const isAdmin = window.CURRENT_USER && window.CURRENT_USER.role === 'ADMIN';
        let actionBtnHtml = '';
        if (isAdmin) {
            if (item.maintenance_status === 'Needs Repair') {
                actionBtnHtml = `
                    <button class="btn btn-sm" style="background: rgba(139, 92, 246, 0.25); color: #c084fc; border: 1px solid rgba(139, 92, 246, 0.5); padding: 4px 10px; font-size: 0.75rem; border-radius: 4px; cursor: pointer; margin-top: 0.5rem; display: inline-flex; align-items: center; gap: 4px;" onclick="quickUpdateStatus('${item.asset_id}', 'Under Maintenance', 'Sent to BioMed workshop for corrective repair')">
                        <i class="fa-solid fa-screwdriver-wrench"></i> Send for Repair
                    </button>
                `;
            } else if (item.maintenance_status === 'Under Maintenance') {
                actionBtnHtml = `
                    <button class="btn btn-sm" style="background: rgba(16, 185, 129, 0.25); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.5); padding: 4px 10px; font-size: 0.75rem; border-radius: 4px; cursor: pointer; margin-top: 0.5rem; display: inline-flex; align-items: center; gap: 4px;" onclick="quickUpdateStatus('${item.asset_id}', 'Good', 'Repair completed, calibrated and certified operational')">
                        <i class="fa-solid fa-circle-check"></i> Mark as Repaired (Good)
                    </button>
                `;
            } else if (item.maintenance_status === 'Due Soon') {
                actionBtnHtml = `
                    <button class="btn btn-sm" style="background: rgba(16, 185, 129, 0.25); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.5); padding: 4px 10px; font-size: 0.75rem; border-radius: 4px; cursor: pointer; margin-top: 0.5rem; display: inline-flex; align-items: center; gap: 4px;" onclick="quickUpdateStatus('${item.asset_id}', 'Good', 'Routine preventative service and safety inspection completed')">
                        <i class="fa-solid fa-circle-check"></i> Certify as Good
                    </button>
                `;
            }
        }

        html += `
            <div style="background: #090e1a; border: 1px solid rgba(239, 68, 68, 0.35); border-left: 4px solid ${badgeColor}; border-radius: 6px; padding: 0.85rem; margin-bottom: 0.75rem;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <div style="font-weight: 700; font-size: 0.88rem; color: #fff;">${item.asset_name}</div>
                        <div style="font-size: 0.72rem; color: #94a3b8; font-family: var(--font-mono);">${item.asset_id} &bull; ${item.current_room_name}</div>
                    </div>
                    <span style="background: ${badgeColor}22; color: ${badgeColor}; border: 1px solid ${badgeColor}55; padding: 1px 6px; border-radius: 4px; font-size: 0.68rem; font-weight: 700;">
                        ${item.maintenance_status}
                    </span>
                </div>
                <div style="font-size: 0.75rem; color: #f87171; margin-top: 0.4rem;">
                    <i class="fa-solid fa-calendar-xmark"></i> Deadline / Status: <strong>${item.due_date}</strong>
                </div>
                <div style="font-size: 0.72rem; color: #94a3b8; margin-top: 0.25rem;">
                    ${item.description || 'Requires inspection.'}
                </div>
                ${actionBtnHtml}
            </div>
        `;
    });

    container.innerHTML = html;
}

// Render the historical table of maintenance records
function renderHistoryTable() {
    const tbody = document.getElementById('maintenance-history-tbody');
    if (!tbody) return;

    const filter = document.getElementById('maint-history-filter').value;
    const filtered = maintenanceRecords.filter(r => (filter === 'ALL' || r.maintenance_status === filter));

    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" style="text-align: center; padding: 2rem; color: #64748b;">
                    No maintenance records found matching current filter.
                </td>
            </tr>
        `;
        return;
    }

    let html = '';
    filtered.forEach(r => {
        let statusBadge = '<span class="status-badge status-badge-available">Good</span>';
        if (r.maintenance_status === 'Due Soon') statusBadge = '<span class="status-badge status-badge-pending">Due Soon</span>';
        if (r.maintenance_status === 'Under Maintenance') statusBadge = '<span class="status-badge" style="background: rgba(139, 92, 246, 0.15); color: #c084fc; border: 1px solid rgba(139, 92, 246, 0.35);">Under Maint</span>';
        if (r.maintenance_status === 'Needs Repair') statusBadge = '<span class="status-badge status-badge-rejected">Needs Repair</span>';

        html += `
            <tr style="border-bottom: 1px solid #1e293b; font-size: 0.8rem;">
                <td style="padding: 0.75rem 1rem; font-family: var(--font-mono); color: #38bdf8;">#MNT-${r.id}</td>
                <td style="padding: 0.75rem 1rem;">
                    <div style="font-weight: 600; color: #f8fafc;">${r.asset_name}</div>
                    <div style="font-size: 0.7rem; color: #94a3b8; font-family: var(--font-mono);">${r.asset_id}</div>
                </td>
                <td style="padding: 0.75rem 1rem; color: #cbd5e1;">${r.current_room_name || 'N/A'}</td>
                <td style="padding: 0.75rem 1rem;">${statusBadge}</td>
                <td style="padding: 0.75rem 1rem; font-family: var(--font-mono); color: #94a3b8;">${r.last_service_date}</td>
                <td style="padding: 0.75rem 1rem; font-family: var(--font-mono); color: #e2e8f0; font-weight: 600;">${r.due_date}</td>
                <td style="padding: 0.75rem 1rem; color: #94a3b8;">${r.technician_name || 'BioMed'}</td>
                <td style="padding: 0.75rem 1rem; color: #94a3b8; max-width: 250px;">${r.description || 'Routine service'}</td>
                <td style="padding: 0.75rem 1rem; font-family: var(--font-mono); font-size: 0.7rem; color: #64748b;">${r.recorded_at.split(' ')[0]}</td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}

// Form submission handler
async function submitMaintenanceRecord(e) {
    e.preventDefault();

    if (window.CURRENT_USER && window.CURRENT_USER.role !== 'ADMIN') {
        showToast(`Access Denied: Only Administrator has permission to save maintenance records. (Current role: ${window.CURRENT_USER.role})`, "error");
        return;
    }

    const submitBtn = document.getElementById('btn-save-maint');
    const originalText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving Record...';

    const payload = {
        asset_id: document.getElementById('maint-asset-select').value,
        maintenance_status: document.getElementById('maint-status').value,
        last_service_date: document.getElementById('maint-last-date').value,
        due_date: document.getElementById('maint-due-date').value,
        technician_name: document.getElementById('maint-technician').value.trim(),
        description: document.getElementById('maint-description').value.trim(),
        cost: parseFloat(document.getElementById('maint-cost').value || '0')
    };

    try {
        const res = await fetch('/api/maintenance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();

        if (res.ok && data.status === 'success') {
            playHospitalAlertChime('INFO');
            showToast(`Maintenance record saved for <strong>${payload.asset_id}</strong>!`, 'success');
            
            document.getElementById('maint-description').value = '';
            await loadMaintenanceData();
            if (window.fetchRealtimeState) window.fetchRealtimeState();
        } else {
            playHospitalAlertChime('WARNING');
            showToast(`Failed: ${data.error || 'Server rejected maintenance record.'}`, 'error');
        }
    } catch (err) {
        showToast(`Network error: ${err.message}`, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
    }
}

// Quick status change helper for Repair Workflow (Needs Repair -> Under Maintenance -> Good)
async function quickUpdateStatus(assetId, targetStatus, defaultDesc) {
    if (window.CURRENT_USER && window.CURRENT_USER.role !== 'ADMIN') {
        showToast(`Access Denied: Only Administrator has permission to update repair status. (Current role: ${window.CURRENT_USER.role})`, "error");
        return;
    }

    const today = new Date();
    const todayStr = today.toISOString().split('T')[0];
    const dueDate = new Date();
    dueDate.setDate(dueDate.getDate() + 90);
    const dueDateStr = dueDate.toISOString().split('T')[0];

    const payload = {
        asset_id: assetId,
        maintenance_status: targetStatus,
        last_service_date: todayStr,
        due_date: dueDateStr,
        technician_name: 'BioMed Engineering Team',
        description: defaultDesc,
        cost: targetStatus === 'Good' ? 120.0 : 0.0
    };

    try {
        const res = await fetch('/api/maintenance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (res.ok && data.status === 'success') {
            playHospitalAlertChime('INFO');
            showToast(data.message || `Status updated to ${targetStatus} for ${assetId}!`, 'success');
            await loadMaintenanceData();
            if (window.fetchRealtimeState) window.fetchRealtimeState();
        } else {
            showToast("Failed to update status: " + (data.error || "Unknown error"), "error");
        }
    } catch (err) {
        showToast("Network error: " + err.message, "error");
    }
}

