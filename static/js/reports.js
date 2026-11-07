/**
 * Feature 5: Reports and Analytics Controller
 * Visual analytics charts, movement leaderboards, and CSV exports.
 */

let reportsData = {};

document.addEventListener('DOMContentLoaded', () => {
    loadReportsData();
    setInterval(loadReportsData, 4000);
});

// Fetch reports data
async function loadReportsData() {
    try {
        const res = await fetch('/api/reports/summary');
        if (!res.ok) return;
        reportsData = await res.json();

        renderKPIs();
        renderDistributionCharts();
        renderRequestsMetrics();
        renderMaintenanceMetrics();
        renderTopMovedLeaderboard();
    } catch (e) {
        console.warn("Failed loading reports data:", e);
    }
}

// Render Top KPI cards
function renderKPIs() {
    if (!reportsData) return;

    document.getElementById('rep-total-assets').innerText = reportsData.total_equipment || 0;
    document.getElementById('rep-total-movements').innerText = reportsData.total_movements || 0;

    const reqs = reportsData.requests || {};
    document.getElementById('rep-approval-rate').innerText = `${reqs.approval_rate || 0}%`;
    document.getElementById('rep-requests-subtext').innerText = `${reqs.approved || 0} / ${reqs.total || 0} Requests Approved`;

    const maint = reportsData.maintenance || {};
    const attentionNeeded = (maint['Due Soon'] || 0) + (maint['Under Maintenance'] || 0) + (maint['Needs Repair'] || 0);
    document.getElementById('rep-maint-attention').innerText = attentionNeeded;
}

// Render horizontal bar charts for Department and Room distribution
function renderDistributionCharts() {
    // 1. Department Distribution
    const deptContainer = document.getElementById('chart-dept-container');
    if (deptContainer && reportsData.dept_distribution) {
        const total = reportsData.total_equipment || 1;
        let html = '';
        reportsData.dept_distribution.forEach(d => {
            const pct = Math.round((d.count / total) * 100);
            html += `
                <div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 0.25rem;">
                        <span style="font-weight: 600; color: #f1f5f9;">${d.name}</span>
                        <span style="color: #94a3b8; font-family: var(--font-mono);">${d.count} devices (${pct}%)</span>
                    </div>
                    <div style="background: #090e1a; height: 10px; border-radius: 5px; overflow: hidden;">
                        <div style="background: linear-gradient(90deg, #0284c7, #38bdf8); height: 100%; width: ${pct}%; transition: width 0.6s ease; border-radius: 5px;"></div>
                    </div>
                </div>
            `;
        });
        deptContainer.innerHTML = html;
    }

    // 2. Current Physical Room Distribution
    const roomContainer = document.getElementById('chart-room-container');
    if (roomContainer && reportsData.room_distribution) {
        const total = reportsData.total_equipment || 1;
        let html = '';
        reportsData.room_distribution.forEach(r => {
            const pct = Math.round((r.count / total) * 100);
            const color = r.color || '#10b981';
            html += `
                <div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 0.25rem;">
                        <span style="font-weight: 600; color: #f1f5f9;">${r.name}</span>
                        <span style="color: #94a3b8; font-family: var(--font-mono);">${r.count} devices (${pct}%)</span>
                    </div>
                    <div style="background: #090e1a; height: 10px; border-radius: 5px; overflow: hidden;">
                        <div style="background: ${color}; height: 100%; width: ${pct}%; transition: width 0.6s ease; border-radius: 5px;"></div>
                    </div>
                </div>
            `;
        });
        roomContainer.innerHTML = html;
    }
}

// Render Requests statistics
function renderRequestsMetrics() {
    const reqs = reportsData.requests || { total: 0, pending: 0, approved: 0, rejected: 0 };

    document.getElementById('stat-req-approved').innerText = reqs.approved || 0;
    document.getElementById('stat-req-pending').innerText = reqs.pending || 0;
    document.getElementById('stat-req-rejected').innerText = reqs.rejected || 0;

    const total = reqs.total || 1;
    const appPct = (reqs.approved / total) * 100;
    const penPct = (reqs.pending / total) * 100;
    const rejPct = (reqs.rejected / total) * 100;

    document.getElementById('bar-approved').style.width = `${appPct}%`;
    document.getElementById('bar-pending').style.width = `${penPct}%`;
    document.getElementById('bar-rejected').style.width = `${rejPct}%`;
}

// Render Maintenance health breakdown
function renderMaintenanceMetrics() {
    const maint = reportsData.maintenance || {};
    const good = maint['Good'] || 0;
    const due = maint['Due Soon'] || 0;
    const under = maint['Under Maintenance'] || 0;
    const repair = maint['Needs Repair'] || 0;

    document.getElementById('stat-maint-good').innerText = good;
    document.getElementById('stat-maint-due').innerText = due;
    document.getElementById('stat-maint-under').innerText = under;
    document.getElementById('stat-maint-repair').innerText = repair;

    const total = reportsData.total_equipment || (good + due + under + repair) || 1;
    document.getElementById('bar-maint-good').style.width = `${(good / total) * 100}%`;
    document.getElementById('bar-maint-due').style.width = `${(due / total) * 100}%`;
    document.getElementById('bar-maint-under').style.width = `${(under / total) * 100}%`;
    document.getElementById('bar-maint-repair').style.width = `${(repair / total) * 100}%`;
}

// Render Top Moved Leaderboard
function renderTopMovedLeaderboard() {
    const tbody = document.getElementById('top-moved-tbody');
    if (!tbody) return;

    const topMoved = reportsData.top_moved || [];

    if (topMoved.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; padding: 2rem; color: #64748b;">
                    No movement events recorded yet. Use the "Manage Movement" tab to relocate assets.
                </td>
            </tr>
        `;
        return;
    }

    const maxMoves = topMoved[0] ? topMoved[0].move_count : 1;
    let html = '';

    topMoved.forEach((item, idx) => {
        const rank = idx + 1;
        let rankBadge = `<span style="display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 50%; background: #334155; color: #fff; font-weight: 700; font-size: 0.75rem;">${rank}</span>`;
        if (rank === 1) rankBadge = `<span style="display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 50%; background: #f59e0b; color: #0f172a; font-weight: 800; font-size: 0.75rem;">🥇</span>`;
        if (rank === 2) rankBadge = `<span style="display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 50%; background: #94a3b8; color: #0f172a; font-weight: 800; font-size: 0.75rem;">🥈</span>`;
        if (rank === 3) rankBadge = `<span style="display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 50%; background: #d97706; color: #0f172a; font-weight: 800; font-size: 0.75rem;">🥉</span>`;

        const pct = Math.round((item.move_count / maxMoves) * 100);

        html += `
            <tr style="border-bottom: 1px solid #1e293b; font-size: 0.82rem;">
                <td style="padding: 0.75rem 1rem;">${rankBadge}</td>
                <td style="padding: 0.75rem 1rem; font-family: var(--font-mono); font-weight: 600; color: #38bdf8;">${item.asset_id}</td>
                <td style="padding: 0.75rem 1rem; font-weight: 600; color: #f8fafc;">${item.name}</td>
                <td style="padding: 0.75rem 1rem; color: #94a3b8;">${item.category}</td>
                <td style="padding: 0.75rem 1rem; font-weight: 700; color: #34d399;">${item.move_count} moves</td>
                <td style="padding: 0.75rem 1rem; width: 200px;">
                    <div style="background: #090e1a; height: 8px; border-radius: 4px; overflow: hidden;">
                        <div style="background: linear-gradient(90deg, #3b82f6, #38bdf8); height: 100%; width: ${pct}%; border-radius: 4px;"></div>
                    </div>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}

