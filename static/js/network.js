/**
 * Smart Hospital Asset Tracking System
 * Network Architecture Page JavaScript:
 * Subnet calculator, VLAN Firewall ACL Tester, MQTT Topic Inspector
 */

document.addEventListener('DOMContentLoaded', () => {
    initSubnetCalculator();
});

// Interactive Subnet Calculator
async function initSubnetCalculator() {
    try {
        const res = await fetch('/api/network/calc_subnet');
        const data = await res.json();
        
        document.getElementById('net-address').innerText = data.network_address;
        document.getElementById('net-cidr').innerText = data.cidr_prefix;
        document.getElementById('net-mask').innerText = data.subnet_mask;
        document.getElementById('net-wildcard').innerText = data.wildcard_mask;
        document.getElementById('net-binary').innerText = data.binary_mask;
        document.getElementById('net-total-hosts').innerText = data.total_ip_addresses.toLocaleString();
        document.getElementById('net-usable-hosts').innerText = data.usable_ip_addresses.toLocaleString();
        document.getElementById('net-first-ip').innerText = data.first_usable_ip;
        document.getElementById('net-last-ip').innerText = data.last_usable_ip;
        document.getElementById('net-broadcast').innerText = data.broadcast_address;
    } catch (e) {
        console.warn("Failed fetching subnet metadata:", e);
    }
}

// Test custom IP in Subnet
function testIpInSubnet() {
    const input = document.getElementById('test-ip-input').value.trim();
    const resultBox = document.getElementById('test-ip-result');
    if (!input) {
        resultBox.innerHTML = '<span style="color: #94a3b8;">Please enter an IPv4 address to evaluate.</span>';
        return;
    }

    const parts = input.split('.').map(Number);
    if (parts.length !== 4 || parts.some(p => isNaN(p) || p < 0 || p > 255)) {
        resultBox.innerHTML = `<span style="color: #ef4444;"><i class="fa-solid fa-triangle-exclamation"></i> Invalid IPv4 address format.</span>`;
        return;
    }

    // 10.20.0.0/22 check
    // Network range: 10.20.0.0 to 10.20.3.255
    const isInSubnet = parts[0] === 10 && parts[1] === 20 && parts[2] >= 0 && parts[2] <= 3;

    if (isInSubnet) {
        let role = "Valid IoT VLAN 20 Host IP";
        if (parts[2] === 0 && parts[3] === 0) role = "Network ID (Cannot be assigned to host)";
        else if (parts[2] === 0 && parts[3] === 1) role = "Default Gateway (Core Switch Virtual Interface)";
        else if (parts[2] === 1 && parts[3] >= 10 && parts[3] <= 20) role = "Static BLE Gateway DHCP Reservation";
        else if (parts[2] === 3 && parts[3] === 255) role = "Directed Broadcast Address (Cannot be assigned to host)";

        resultBox.innerHTML = `
            <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; border-radius: 6px; padding: 0.6rem; color: #34d399;">
                <i class="fa-solid fa-circle-check"></i> <strong>${input}</strong> belongs to IoT VLAN 20 (10.20.0.0/22)!<br>
                <span style="font-size: 0.75rem; color: #cbd5e1;">Role: <strong>${role}</strong></span>
            </div>
        `;
    } else {
        resultBox.innerHTML = `
            <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; border-radius: 6px; padding: 0.6rem; color: #f87171;">
                <i class="fa-solid fa-circle-xmark"></i> <strong>${input}</strong> is OUTSIDE the 10.20.0.0/22 subnet boundary.<br>
                <span style="font-size: 0.75rem; color: #cbd5e1;">Valid range: 10.20.0.1 &rarr; 10.20.3.254</span>
            </div>
        `;
    }
}

// Interactive VLAN Firewall ACL Simulator
async function runVlanTest() {
    const srcVlan = document.getElementById('test-src-vlan').value;
    const dstVlan = document.getElementById('test-dst-vlan').value;
    const port = document.getElementById('test-port').value;
    const resultBox = document.getElementById('vlan-test-result');

    resultBox.innerHTML = `<span style="color: #38bdf8;"><i class="fa-solid fa-spinner fa-spin"></i> Transmitting 802.1Q tagged frame to hospital firewall...</span>`;

    try {
        const res = await fetch('/api/network/test_vlan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ src_vlan: srcVlan, dst_vlan: dstVlan, port: port })
        });
        const data = await res.json();

        const isPermit = data.action === 'PERMIT';
        const color = isPermit ? '#10b981' : '#ef4444';
        const icon = isPermit ? 'fa-shield-halved' : 'fa-hand';

        resultBox.innerHTML = `
            <div style="background: ${isPermit ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)'}; border: 1px solid ${color}; border-radius: 8px; padding: 0.85rem;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem;">
                    <span style="font-weight: 800; font-size: 0.9rem; color: ${color};">
                        <i class="fa-solid ${icon}"></i> FIREWALL VERDICT: ${data.action}
                    </span>
                    <span style="font-family: monospace; font-size: 0.75rem; background: #0f172a; padding: 0.15rem 0.5rem; border-radius: 4px; color: #94a3b8;">
                        Rule: ${data.rule_id}
                    </span>
                </div>
                <div style="font-size: 0.8rem; color: #f1f5f9; line-height: 1.4;">
                    ${data.reason}
                </div>
                <div style="font-size: 0.72rem; color: #94a3b8; font-family: monospace; margin-top: 0.4rem;">
                    Traffic Flow: VLAN ${data.src_vlan} &rarr; Hospital Core Firewall &rarr; VLAN ${data.dst_vlan} (Port: ${data.port})
                </div>
            </div>
        `;
    } catch (e) {
        resultBox.innerHTML = `<span style="color: #ef4444;">Error testing VLAN: ${e}</span>`;
    }
}

