/**
 * Smart Hospital Asset Tracking System
 * Demo Controller, Simulation Management & Audio Notification Engine
 */

// Audio Synthesizer via Web Audio API (No external sound files required)
let audioCtx = null;
let soundEnabled = true;

function initAudio() {
    if (!audioCtx) {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        audioCtx = new AudioContext();
    }
}

function playHospitalAlertChime(severity = 'CRITICAL') {
    if (!soundEnabled) return;
    try {
        initAudio();
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }

        const now = audioCtx.currentTime;
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();

        osc.connect(gain);
        gain.connect(audioCtx.destination);

        if (severity === 'CRITICAL') {
            // Urgent dual-tone alert (Hospital Code Blue / Security Alarm)
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(880, now); // A5
            osc.frequency.setValueAtTime(587.33, now + 0.15); // D5
            osc.frequency.setValueAtTime(880, now + 0.3);
            gain.gain.setValueAtTime(0.2, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.55);
            osc.start(now);
            osc.stop(now + 0.55);
        } else if (severity === 'WARNING') {
            // Amber warning chime
            osc.type = 'sine';
            osc.frequency.setValueAtTime(659.25, now); // E5
            osc.frequency.setValueAtTime(523.25, now + 0.2); // C5
            gain.gain.setValueAtTime(0.18, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);
            osc.start(now);
            osc.stop(now + 0.45);
        } else {
            // Gentle telemetry ping
            osc.type = 'triangle';
            osc.frequency.setValueAtTime(1046.5, now); // C6
            gain.gain.setValueAtTime(0.08, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
            osc.start(now);
            osc.stop(now + 0.2);
        }
    } catch (e) {
        console.warn("Audio chime failed:", e);
    }
}

function toggleAudioChime() {
    soundEnabled = !soundEnabled;
    const btn = document.getElementById('audio-icon');
    if (btn) {
        if (soundEnabled) {
            btn.className = "fa-solid fa-volume-high";
            showToast("Sound alerts ENABLED", "success");
            playHospitalAlertChime('INFO');
        } else {
            btn.className = "fa-solid fa-volume-xmark";
            showToast("Sound alerts MUTED", "warning");
        }
    }
}

// Toast Notifications
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let icon = 'fa-circle-info';
    if (type === 'error' || type === 'critical') icon = 'fa-triangle-exclamation';
    if (type === 'success') icon = 'fa-circle-check';
    if (type === 'warning') icon = 'fa-battery-quarter';

    toast.innerHTML = `
        <i class="fa-solid ${icon}"></i>
        <div style="flex: 1; font-size: 0.82rem;">${message}</div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4500);
}

// Demo Modal Controls
async function openDemoModal() {
    const modal = document.getElementById('demo-modal');
    if (modal) {
        modal.classList.remove('hidden');
        await populateDemoAssetSelect();
    }
}

async function populateDemoAssetSelect() {
    const select = document.getElementById('modal-asset-select');
    if (!select) return;
    try {
        const res = await fetch('/api/assets');
        if (!res.ok) return;
        const assets = await res.json();
        const currentVal = select.value;
        select.innerHTML = '<option value="">Select Asset...</option>';
        assets.forEach(a => {
            const opt = document.createElement('option');
            opt.value = a.asset_id;
            opt.textContent = `[${a.asset_id}] ${a.name} · Location: ${a.current_room_name}`;
            select.appendChild(opt);
        });
        if (currentVal && assets.some(a => a.asset_id === currentVal)) {
            select.value = currentVal;
        }
    } catch (e) {
        console.warn("Failed populating demo asset dropdown:", e);
    }
}

function closeDemoModal() {
    const modal = document.getElementById('demo-modal');
    if (modal) modal.classList.add('hidden');
}

// Simulation Toggle
async function toggleSimulation() {
    try {
        const res = await fetch('/api/simulation/toggle', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
        const data = await res.json();
        updateSimButton(data.simulation_running);
        showToast(data.message, data.simulation_running ? 'success' : 'warning');
    } catch (err) {
        showToast("Error updating simulation: " + err, "error");
    }
}

function updateSimButton(isRunning) {
    const icon = document.getElementById('sim-icon');
    const text = document.getElementById('sim-text');
    if (icon && text) {
        if (isRunning) {
            icon.className = "fa-solid fa-pause";
            text.innerText = "Simulation: ON";
        } else {
            icon.className = "fa-solid fa-play";
            text.innerText = "Simulation: PAUSED";
        }
    }
}

// Manual Relocation Execution
async function executeManualMove() {
    if (window.CURRENT_USER && window.CURRENT_USER.role !== 'ADMIN') {
        showToast(`Access Denied: Only Administrator has permission to manually move equipment. (Current role: ${window.CURRENT_USER.role})`, "error");
        return;
    }

    const assetSelect = document.getElementById('modal-asset-select');
    const roomSelect = document.getElementById('modal-room-select');
    const assetId = assetSelect ? assetSelect.value : '';
    const roomId = roomSelect ? roomSelect.value : '';

    if (!assetId || !roomId) {
        showToast("Please choose both an Asset and a Target Ward", "warning");
        return;
    }

    try {
        const res = await fetch('/api/move', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ asset_id: assetId, room_id: roomId })
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

            // Refresh all relevant views immediately
            if (window.fetchRealtimeState) window.fetchRealtimeState();
            if (window.loadEquipmentList) window.loadEquipmentList();
            if (window.loadMovementHistory) window.loadMovementHistory();
            if (window.loadInventory) window.loadInventory();
            if (window.loadFloorMapData) window.loadFloorMapData();
            if (window.loadMaintenanceData) window.loadMaintenanceData();
            if (window.loadNotificationsData) window.loadNotificationsData();
            if (window.loadReportsData) window.loadReportsData();
            updateNotificationsNavbar();

            closeDemoModal();
        } else {
            showToast("Failed to move asset: " + (data.error || data.message || "Unknown error"), "error");
        }
    } catch (e) {
        showToast("Error executing move: " + e.message, "error");
    }
}

// Preset Scenario Execution
async function runDemoScenario(action) {
    if (window.CURRENT_USER && window.CURRENT_USER.role !== 'ADMIN') {
        showToast(`Access Denied: Demonstration actions and reset are restricted to Administrator. (Current role: ${window.CURRENT_USER.role})`, "error");
        return;
    }

    try {
        const res = await fetch(`/api/demo/${action}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        let data;
        const contentType = res.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            data = await res.json();
        } else {
            const errorText = await res.text();
            throw new Error(`HTTP ${res.status} response from server (${errorText.substring(0, 50)}...)`);
        }

        if (res.ok && data.status === 'success') {
            if (action === 'icu_breach') {
                playHospitalAlertChime('CRITICAL');
                showToast("🚨 CRITICAL: ICU Ventilator Geofence Breach triggered! Relocated to Storage.", "error");
            } else if (action === 'emergency_transfer') {
                playHospitalAlertChime('INFO');
                showToast("⚡ Emergency Trauma Transfer: Defibrillator moved to Operation Theatre!", "success");
            } else if (action === 'low_battery') {
                playHospitalAlertChime('WARNING');
                showToast("🪫 Tag battery dropped to 12% critical threshold!", "warning");
            } else if (action === 'link_failover') {
                playHospitalAlertChime('WARNING');
                showToast(data.message, "warning");
            } else if (action === 'reset') {
                playHospitalAlertChime('INFO');
                showToast(data.message || "Demonstration environment reset to pristine baseline.", "success");
            }

            // Immediately synchronize all active pages & components
            if (window.fetchRealtimeState) window.fetchRealtimeState();
            if (window.loadEquipmentList) window.loadEquipmentList();
            if (window.loadMovementHistory) window.loadMovementHistory();
            if (window.loadInventory) window.loadInventory();
            if (window.loadFloorMapData) window.loadFloorMapData();
            if (window.loadMaintenanceData) window.loadMaintenanceData();
            if (window.loadNotificationsData) window.loadNotificationsData();
            if (window.loadReportsData) window.loadReportsData();
            updateNotificationsNavbar();

            closeDemoModal();
        } else {
            showToast("Scenario failed: " + (data.error || data.message || "Unknown error"), "error");
        }
    } catch (e) {
        showToast("Error executing scenario: " + e.message, "error");
    }
}

function scrollToAlerts() {
    const el = document.getElementById('alerts-section');
    if (el) el.scrollIntoView({ behavior: 'smooth' });
}

// Close modal on Escape
window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDemoModal();
});

// Real-Time Pending Requests Notification Poller
async function updatePendingRequestsNavbar() {
    try {
        const res = await fetch('/api/requests/pending_count');
        if (!res.ok) return;
        const data = await res.json();
        const count = data.count || 0;

        const badge = document.getElementById('nav-pending-badge');
        if (badge) {
            badge.innerText = count;
            if (count > 0) {
                badge.classList.remove('hidden');
                badge.classList.add('has-pending');
            } else {
                badge.classList.add('hidden');
                badge.classList.remove('has-pending');
            }
        }

        const pill = document.getElementById('nav-requests-pill');
        const countEl = document.getElementById('nav-requests-count');
        if (pill && countEl) {
            countEl.innerText = count;
            if (count > 0) {
                pill.classList.remove('hidden');
            } else {
                pill.classList.add('hidden');
            }
        }
    } catch (e) {
        // Silently ignore polling failure
    }
}

// Real-Time Unread Notifications Badge Poller
async function updateNotificationsNavbar() {
    try {
        const res = await fetch('/api/notifications/unread_count');
        if (!res.ok) return;
        const data = await res.json();
        const count = data.count || 0;

        const badge = document.getElementById('nav-notif-badge');
        if (badge) {
            badge.innerText = count;
            if (count > 0) {
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        }

        const pillCount = document.getElementById('nav-notif-pill-count');
        if (pillCount) {
            pillCount.innerText = count;
        }
    } catch (e) {
        // Silently ignore polling failure
    }
}

document.addEventListener('DOMContentLoaded', () => {
    updatePendingRequestsNavbar();
    updateNotificationsNavbar();
    setInterval(updatePendingRequestsNavbar, 3000);
    setInterval(updateNotificationsNavbar, 3000);
});

