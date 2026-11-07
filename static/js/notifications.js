/**
 * Feature 4: Notifications and Alerts Center Controller
 * Manages notification streaming, category filtering, unread status, and read marks.
 */

let activeCategory = 'ALL';
let unreadOnly = false;
let currentNotifications = [];

const CATEGORY_META = {
    'EQUIPMENT_REQUEST': { icon: 'fa-clipboard-question', label: 'Equipment Request', color: '#fbbf24' },
    'GEOFENCE_BREACH': { icon: 'fa-triangle-exclamation', label: 'Geofence Breach', color: '#ef4444' },
    'MAINTENANCE_DUE': { icon: 'fa-wrench', label: 'Maintenance Due', color: '#f59e0b' },
    'NEEDS_REPAIR': { icon: 'fa-triangle-exclamation', label: 'Needs Repair', color: '#ef4444' },
    'NEW_EQUIPMENT': { icon: 'fa-square-plus', label: 'New Device', color: '#38bdf8' },
    'SYSTEM': { icon: 'fa-shield-halved', label: 'System Notice', color: '#94a3b8' }
};

document.addEventListener('DOMContentLoaded', () => {
    loadNotificationsData();
    setInterval(loadNotificationsData, 3000);
});

// Category Tab Switcher
function setNotifCategory(cat, btn) {
    activeCategory = cat;

    // Update active tab style
    const tabs = document.querySelectorAll('#notif-category-tabs button');
    tabs.forEach(t => {
        t.className = 'btn btn-sm btn-secondary';
    });
    btn.className = 'btn btn-sm btn-cyan active-tab';

    loadNotificationsData();
}

function toggleUnreadOnly() {
    unreadOnly = document.getElementById('notif-unread-only').checked;
    loadNotificationsData();
}

// Fetch notifications from server
async function loadNotificationsData() {
    try {
        let url = `/api/notifications?limit=100`;
        if (activeCategory !== 'ALL') {
            url += `&category=${encodeURIComponent(activeCategory)}`;
        }
        if (unreadOnly) {
            url += `&unread=true`;
        }

        const res = await fetch(url);
        if (!res.ok) return;
        currentNotifications = await res.json();

        renderNotificationsList();
    } catch (e) {
        console.warn("Failed loading notifications:", e);
    }
}

// Render notification cards feed
function renderNotificationsList() {
    const container = document.getElementById('notifications-feed-container');
    if (!container) return;

    document.getElementById('notif-count-pill').innerText = `${currentNotifications.length} Events`;

    if (currentNotifications.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; color: #64748b; padding: 3.5rem 1rem; background: #090e1a; border-radius: 8px; border: 1px dashed #1e293b;">
                <i class="fa-solid fa-bell-slash" style="font-size: 2.2rem; color: #475569; margin-bottom: 0.75rem;"></i>
                <div style="font-weight: 600; color: #94a3b8; font-size: 0.95rem;">No Notifications Found</div>
                <div style="font-size: 0.78rem; color: #64748b; margin-top: 0.35rem;">
                    There are no events matching category "${activeCategory}"${unreadOnly ? ' with unread status' : ''}.
                </div>
            </div>
        `;
        return;
    }

    let html = '';
    currentNotifications.forEach(n => {
        const meta = CATEGORY_META[n.category] || { icon: 'fa-bell', label: n.category, color: '#38bdf8' };
        
        let severityClass = 'border-info';
        let severityColor = '#38bdf8';
        if (n.severity === 'WARNING') { severityClass = 'border-warning'; severityColor = '#fbbf24'; }
        if (n.severity === 'CRITICAL') { severityClass = 'border-danger'; severityColor = '#ef4444'; }

        const isUnread = (n.is_read === 0);
        const cardBg = isUnread ? '#0d1526' : '#090e1a';
        const cardOpacity = isUnread ? '1' : '0.85';

        html += `
            <div class="notif-card" style="background: ${cardBg}; opacity: ${cardOpacity}; border: 1px solid ${isUnread ? severityColor : '#1e293b'}; border-left: 4px solid ${severityColor}; border-radius: 8px; padding: 1rem 1.25rem; display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; transition: all 0.2s;">
                <div style="display: flex; gap: 0.9rem; align-items: flex-start; flex: 1;">
                    <div style="width: 38px; height: 38px; border-radius: 8px; background: ${severityColor}18; border: 1px solid ${severityColor}44; display: flex; align-items: center; justify-content: center; color: ${severityColor}; font-size: 1.1rem; flex-shrink: 0; margin-top: 0.15rem;">
                        <i class="fa-solid ${meta.icon}"></i>
                    </div>
                    <div style="flex: 1;">
                        <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.25rem;">
                            <span style="font-weight: 700; font-size: 0.92rem; color: #f8fafc;">${n.title}</span>
                            <span style="background: ${severityColor}22; color: ${severityColor}; border: 1px solid ${severityColor}44; padding: 1px 6px; border-radius: 4px; font-size: 0.68rem; font-weight: 700;">
                                ${n.severity}
                            </span>
                            <span style="font-size: 0.72rem; color: #64748b; font-family: var(--font-mono);">${meta.label}</span>
                            ${isUnread ? '<span style="width: 8px; height: 8px; border-radius: 50%; background: #38bdf8; display: inline-block;" title="Unread Event"></span>' : ''}
                        </div>
                        <div style="font-size: 0.82rem; color: #cbd5e1; line-height: 1.5; margin-bottom: 0.4rem;">
                            ${n.description}
                        </div>
                        <div style="display: flex; gap: 0.85rem; align-items: center; font-size: 0.72rem; color: #64748b; font-family: var(--font-mono); flex-wrap: wrap;">
                            <span><i class="fa-solid fa-clock"></i> ${n.created_at}</span>
                            ${n.asset_id ? `<span><i class="fa-solid fa-tag text-cyan"></i> Asset: <strong style="color: #93c5fd;">${n.asset_id}</strong></span>` : ''}
                            ${n.room_id ? `<span><i class="fa-solid fa-door-closed text-cyan"></i> Room: <strong style="color: #93c5fd;">${n.room_id}</strong></span>` : ''}
                        </div>
                    </div>
                </div>

                <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 0.4rem;">
                    ${isUnread ? `
                        <button class="btn btn-secondary btn-sm" onclick="markNotificationAsRead(${n.id})" title="Mark as read" style="font-size: 0.72rem; padding: 0.25rem 0.6rem; white-space: nowrap;">
                            <i class="fa-solid fa-check"></i> Mark Read
                        </button>
                    ` : `
                        <span style="font-size: 0.72rem; color: #475569; display: flex; align-items: center; gap: 0.25rem;">
                            <i class="fa-solid fa-check-double text-success"></i> Read
                        </span>
                    `}
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

// Mark single notification as read
async function markNotificationAsRead(notifId) {
    try {
        const res = await fetch(`/api/notifications/${notifId}/read`, { method: 'POST' });
        if (res.ok) {
            playHospitalAlertChime('INFO');
            await loadNotificationsData();
            if (window.updateNotificationsNavbar) window.updateNotificationsNavbar();
        }
    } catch (e) {
        showToast("Error updating notification: " + e.message, "error");
    }
}

// Mark all as read
async function markAllNotificationsAsRead() {
    try {
        const res = await fetch('/api/notifications/mark_all_read', { method: 'POST' });
        if (res.ok) {
            playHospitalAlertChime('INFO');
            showToast("All notifications marked as read.", "success");
            await loadNotificationsData();
            if (window.updateNotificationsNavbar) window.updateNotificationsNavbar();
        }
    } catch (e) {
        showToast("Error marking all read: " + e.message, "error");
    }
}

