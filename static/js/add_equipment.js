/**
 * Feature 1: Add New Equipment Controller
 * Handles interactive registration, unique ID suggestion, live preview, and API dispatch.
 */

const CATEGORY_MAP = {
    'Ventilator': { prefix: 'VENT', icon: 'fa-lungs', color: '#38bdf8' },
    'Defibrillator': { prefix: 'DEFIB', icon: 'fa-heart-pulse', color: '#f87171' },
    'Patient Monitor': { prefix: 'MON', icon: 'fa-wave-square', color: '#34d399' },
    'Infusion Pump': { prefix: 'PUMP', icon: 'fa-syringe', color: '#fbbf24' },
    'ECG Machine': { prefix: 'ECG', icon: 'fa-file-waveform', color: '#a78bfa' },
    'Wheelchair': { prefix: 'WCHR', icon: 'fa-wheelchair', color: '#2dd4bf' },
    'Portable X-Ray': { prefix: 'XRAY', icon: 'fa-radiation', color: '#f43f5e' },
    'Ultrasound': { prefix: 'ULTRA', icon: 'fa-satellite-dish', color: '#60a5fa' },
    'Dialysis Machine': { prefix: 'DIAL', icon: 'fa-flask', color: '#c084fc' },
    'Syringe Pump': { prefix: 'SYR', icon: 'fa-syringe', color: '#f59e0b' },
    'Medical Device': { prefix: 'DEV', icon: 'fa-kit-medical', color: '#94a3b8' }
};

document.addEventListener('DOMContentLoaded', () => {
    generateSuggestedId();
    updateLivePreview();
});

// Category selection changed
function onCategoryChanged() {
    generateSuggestedId();
    updateLivePreview();
}

// Assigned department changed -> sync initial physical location
function onAssignedRoomChanged() {
    const assigned = document.getElementById('eq-assigned-room').value;
    const currentSelect = document.getElementById('eq-current-room');
    if (currentSelect && assigned) {
        currentSelect.value = assigned;
    }
    updateLivePreview();
}

// Generate next available suggested Equipment ID
async function generateSuggestedId() {
    const category = document.getElementById('eq-category').value || 'Ventilator';
    const info = CATEGORY_MAP[category] || { prefix: 'DEV', icon: 'fa-kit-medical', color: '#94a3b8' };
    
    try {
        const res = await fetch('/api/assets');
        if (res.ok) {
            const assets = await res.json();
            const existingIds = new Set(assets.map(a => a.asset_id));
            let index = 1;
            let candidate = `AST-${info.prefix}-${String(index).padStart(2, '0')}`;
            while (existingIds.has(candidate)) {
                index++;
                candidate = `AST-${info.prefix}-${String(index).padStart(2, '0')}`;
            }
            document.getElementById('eq-id').value = candidate;
            updateLivePreview();
            return;
        }
    } catch (e) {
        console.warn("Could not query assets for ID generation:", e);
    }
    
    // Fallback ID
    const randomSuffix = Math.floor(10 + Math.random() * 90);
    document.getElementById('eq-id').value = `AST-${info.prefix}-${randomSuffix}`;
    updateLivePreview();
}

// Update the real-time live preview badge card
function updateLivePreview() {
    const name = document.getElementById('eq-name').value.trim() || 'Hamilton-T1 Transport Ventilator';
    const id = document.getElementById('eq-id').value.trim().toUpperCase() || 'AST-VENT-03';
    const category = document.getElementById('eq-category').value;
    const model = document.getElementById('eq-model').value.trim() || `${category} Standard Unit`;
    const roomSelect = document.getElementById('eq-current-room');
    const roomName = roomSelect.options[roomSelect.selectedIndex] ? roomSelect.options[roomSelect.selectedIndex].text : 'Intensive Care Unit';
    const status = document.getElementById('eq-status').value;

    const info = CATEGORY_MAP[category] || { prefix: 'DEV', icon: 'fa-kit-medical', color: '#38bdf8' };

    document.getElementById('preview-name').innerText = name;
    document.getElementById('preview-id').innerText = id;
    document.getElementById('preview-model').innerText = model;
    document.getElementById('preview-room').innerText = roomName;

    // Status badge
    const statusEl = document.getElementById('preview-status');
    statusEl.innerText = status;
    statusEl.className = 'status-badge';
    if (status === 'Available') {
        statusEl.classList.add('status-badge-available');
        statusEl.style.background = 'rgba(16, 185, 129, 0.15)';
        statusEl.style.color = '#34d399';
    } else if (status === 'In Use') {
        statusEl.classList.add('status-badge-in-use');
        statusEl.style.background = 'rgba(59, 130, 246, 0.15)';
        statusEl.style.color = '#60a5fa';
    } else {
        statusEl.classList.add('status-badge-maintenance');
        statusEl.style.background = 'rgba(245, 158, 11, 0.15)';
        statusEl.style.color = '#fbbf24';
    }

    // Icon & Color
    const iconEl = document.getElementById('preview-icon');
    const iconBox = document.getElementById('preview-icon-box');
    iconEl.className = `fa-solid ${info.icon}`;
    iconBox.style.color = info.color;
    iconBox.style.borderColor = info.color;
    iconBox.style.background = `${info.color}22`;

    // BLE credentials preview
    const hash = Math.abs(id.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0));
    document.getElementById('preview-tag-id').innerText = `TAG-BLE-${700 + (hash % 100)}`;
    document.getElementById('preview-tag-mac').innerText = `AC:23:3F:8A:71:${(hash % 90 + 10).toString(16).toUpperCase()}`;
}

function resetFormPreview() {
    setTimeout(() => {
        generateSuggestedId();
        updateLivePreview();
    }, 50);
}

// Form submission handler
async function submitNewEquipment(e) {
    e.preventDefault();

    if (window.CURRENT_USER && window.CURRENT_USER.role !== 'ADMIN') {
        showToast(`Access Denied: Only Administrator has permission to add new equipment. (Current role: ${window.CURRENT_USER.role})`, "error");
        return;
    }

    const submitBtn = document.getElementById('btn-submit-eq');
    const originalBtnHtml = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Provisioning Device...';

    const payload = {
        name: document.getElementById('eq-name').value.trim(),
        asset_id: document.getElementById('eq-id').value.trim().toUpperCase(),
        category: document.getElementById('eq-category').value,
        model: document.getElementById('eq-model').value.trim(),
        assigned_room_id: document.getElementById('eq-assigned-room').value,
        current_room_id: document.getElementById('eq-current-room').value,
        status: document.getElementById('eq-status').value,
        quantity: parseInt(document.getElementById('eq-quantity').value || '1', 10)
    };

    try {
        const res = await fetch('/api/equipment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();

        if (res.ok && data.status === 'success') {
            playHospitalAlertChime('INFO');
            showToast(`Equipment <strong>${payload.name}</strong> (${payload.asset_id}) registered successfully!`, 'success');
            
            // Clear inputs and regenerate new unique ID
            document.getElementById('eq-name').value = '';
            document.getElementById('eq-model').value = '';
            await generateSuggestedId();
            updateLivePreview();
        } else {
            playHospitalAlertChime('WARNING');
            showToast(`Registration failed: ${data.error || 'Server rejected equipment record.'}`, 'error');
            const idFeedback = document.getElementById('id-feedback');
            if (idFeedback && data.error && data.error.includes('already exists')) {
                idFeedback.style.color = '#f87171';
                idFeedback.innerText = data.error;
            }
        }
    } catch (err) {
        showToast(`Network error: ${err.message}`, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnHtml;
    }
}

