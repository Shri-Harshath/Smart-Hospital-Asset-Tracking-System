# Smart Hospital Asset Tracking System (RTLS)
### Real-Time Location Tracking Using IoT and Computer Networks

---

## 1. Project Overview

This is a **fully working, locally executable application** engineered specifically for classroom demonstration in **Computer Networks**. It directly implements the architecture, network topology, protocols, and security models outlined in the PowerPoint presentation:

```
+---------------------------------------------------------------------------------------------------------+
|                                    FOUR-LAYER SYSTEM ARCHITECTURE (Slide 3)                             |
+---------------------------------------------------------------------------------------------------------+
| Layer 1: Sensing Layer    | BLE 5.0 Beacon Tags broadcasting periodic radio advertisements              |
| Layer 2: Gateway Layer    | ESP32 / Raspberry Pi PoE Gateways converting BLE radio frames to IP packets |
| Layer 3: Network Layer    | Three-Tier LAN, 802.1Q VLANs (VLAN 20: 10.20.0.0/22), MQTT Broker (Port 1883)|
| Layer 4: Application Layer| Trilateration Location Engine, SQLite Database & Live Web Dashboard         |
+---------------------------------------------------------------------------------------------------------+
```

---

## 2. Key Features

1. **Live Hospital Floor Map & Asset Positioning:**
   - 7 Wards across Floor 3 (ICU, Emergency & Trauma, Operation Theatre, General Ward A, General Ward B, Biomedical Depot, Perimeter Exit Gate 3).
   - Real-time asset markers with live category icons (Ventilators, Defibrillators, Monitors, Pumps, ECG, Wheelchairs, Mobile X-Ray).
   - Animated Wi-Fi / BLE radar ripples showing active gateway scanning.

2. **End-to-End Live Data Flow Visualizer:**
   - Animated visual path: `BLE Tag` $\rightarrow$ `ESP32 Gateway` $\rightarrow$ `Access PoE Switch` $\rightarrow$ `Core Switch & Firewall` $\rightarrow$ `MQTT Broker` $\rightarrow$ `Location Engine & DB` $\rightarrow$ `Live Dashboard`.
   - Real-time packet ticker showing Tag ID, Gateway ID, RSSI, Distance, Topic, and Port.

3. **Live Network Wire Packet Terminal:**
   - Dark-mode scrolling packet capture terminal streaming genuine MQTT/TCP frames with QoS 1, hex payload inspection, and firewall drop logs.

4. **Dedicated Computer Networks Architecture Page (`/network`):**
   - **Three-Tier Hierarchical Network Topology:** Core Layer (VRRP redundant 10G switches), Distribution Layer (Block A & B aggregators), Access Layer (802.3af PoE switches in a star topology).
   - **IP Subnetting Breakdown for IoT VLAN 20 (`10.20.0.0/22`):** Mask `255.255.252.0`, 1,022 usable hosts, binary bit breakdown, and interactive subnet IP validator.
   - **Interactive Firewall ACL Simulator:** Test inter-VLAN packet flow (e.g. Guest Wi-Fi VLAN 40 to IoT VLAN 20 is dropped by firewall rule `ACL-GUEST-ISOLATE`).
   - **Protocol Stack Deep Dive:** 5-layer model, TCP vs. UDP comparison, and MQTT topic hierarchy.
   - **Network Security:** WPA3-Enterprise, 802.1X/RADIUS authentication flow, and MQTT TLS 1.3 on port 8883.

5. **Geofencing & Security Alerts:**
   - **Ward Restriction Violation:** Life-support equipment (e.g. ICU ventilator) leaving assigned ward triggers an emergency alarm.
   - **Perimeter Theft Prevention:** Equipment approaching Exit Gate 3 triggers an urgent security breach alarm.
   - **Battery Health Monitor:** BLE tags dropping $\le 20\%$ trigger warning notifications.
   - **Audio Chime:** High-tech synthesized hospital chime alerts via Web Audio API.

6. **Interactive Classroom Demo Controls:**
   - 1-click classroom demonstration buttons: ICU Ventilator Breach, Emergency Trauma Transfer, Low Battery Event, Gateway Link Failover, and Baseline Reset.
   - Manual equipment relocation dropdown tool.

---

## 3. Quick Start Guide (Windows)

### Option A: 1-Click Launch (Recommended for Presentation)
Simply double-click the **`start.bat`** script in the project root:
```bat
start.bat
```
This automatically verifies Python, installs dependencies from `requirements.txt`, launches the backend with the embedded MQTT broker, and opens `http://127.0.0.1:5000/` in your default browser.

### Option B: Manual Command Line
1. Open PowerShell or Command Prompt in the project folder.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the Flask application:
   ```bash
   python app.py
   ```
4. Open your browser and navigate to:
   - **Live Tracking Dashboard:** [http://127.0.0.1:5000/](http://127.0.0.1:5000/)
   - **Hospital Floor Map (Feature 2):** [http://127.0.0.1:5000/map](http://127.0.0.1:5000/map)
   - **Manage Equipment Movement:** [http://127.0.0.1:5000/movement](http://127.0.0.1:5000/movement)
   - **Equipment Request Management:** [http://127.0.0.1:5000/requests](http://127.0.0.1:5000/requests)
   - **Add New Equipment (Feature 1):** [http://127.0.0.1:5000/equipment/add](http://127.0.0.1:5000/equipment/add)
   - **Maintenance Management (Feature 3):** [http://127.0.0.1:5000/maintenance](http://127.0.0.1:5000/maintenance)
   - **Notifications & Alerts Center (Feature 4):** [http://127.0.0.1:5000/notifications](http://127.0.0.1:5000/notifications)
   - **Reports & Analytics (Feature 5):** [http://127.0.0.1:5000/reports](http://127.0.0.1:5000/reports)
   - **User Login & Roles (Feature 6):** [http://127.0.0.1:5000/login](http://127.0.0.1:5000/login)
   - **Network Architecture Page:** [http://127.0.0.1:5000/network](http://127.0.0.1:5000/network)
   - **Asset Inventory & Health:** [http://127.0.0.1:5000/assets](http://127.0.0.1:5000/assets)

---

## 4. Codebase Architecture & File Descriptions

| File / Folder | Purpose & Implementation Details |
| :--- | :--- |
| **`app.py`** | Main Flask server. Coordinates routes, REST API endpoints (`/api/state`, `/api/move`, `/api/network/test_vlan`), Server-Sent Events (SSE) packet stream, and CSV inventory export. |
| **`mqtt_service.py`** | Dual-mode MQTT subsystem. Contains an embedded RFC-compliant MQTT 3.1.1 broker running on TCP port 1883, Paho-MQTT client for publishing/subscribing to `hospital/#`, packet hex inspector, and in-memory fallback. |
| **`simulator.py`** | Physical simulation engine. Implements the Log-Distance Path Loss Model ($d = 10^{(\text{TxPower} - \text{RSSI})/(10 \cdot n)}$), gateway multilateration, autonomous movement, geofencing rules, and demo actions. |
| **`database.py`** | SQLite abstraction layer (`hospital_assets.db`). Defines persistent schemas for `assets`, `gateways`, `rooms`, `alerts`, `location_history`, and `network_logs`. |
| **`templates/base.html`** | Global navigation bar, live MQTT status badge, sound chime synthesizer, and classroom demo control modal. |
| **`templates/dashboard.html`** | Interactive SVG floor plan across 7 wards, KPI cards, end-to-end data flow pipeline, scrolling network terminal, and active alerts panel. |
| **`templates/movement.html`** | Dedicated "Manage Equipment Movement" page with equipment selector, target ward selector, Move button, and persistent movement history log. |
| **`templates/network.html`** | Dedicated Computer Networks page: 3-tier topology diagram, subnet calculator (`10.20.0.0/22`), interactive VLAN firewall tester, and protocol stack explorer. |
| **`templates/assets.html`** | Medical equipment inventory, search/filter toolbar, battery health indicators, and CSV export button. |
| **`static/css/style.css`** | Modern medical UI styling, dark terminal styles, radar ripple animations, glowing alert pulses, and responsive layout. |
| **`static/js/dashboard.js`** | Real-time map rendering, asset positioning, SSE packet streaming, and drawer controls. |
| **`static/js/network.js`** | Interactive subnet calculator logic and interactive VLAN firewall packet traversal test engine. |
| **`static/js/demo.js`** | Web Audio API sound synthesizer, preset classroom scenario triggers, and toast notifications. |
| **`static/js/inventory.js`**| Asset table searching, filtering, and instant relocation actions. |
| **`requirements.txt`** | Python dependencies (`flask>=3.0.0`, `paho-mqtt>=2.0.0`). |
| **`start.bat`** | Windows 1-click startup automation script. |

---

## 5. Step-by-Step Live Classroom Demonstration Guide

Follow this **5-minute walkthrough** when presenting to your teacher:

1. **Step 1: Introduction (Slide 1–3)**
   - Open [http://127.0.0.1:5000/](http://127.0.0.1:5000/).
   - State the problem: Medical equipment like ventilators and defibrillators goes missing, leading to delayed patient care and unnecessary hospital over-buying.
   - Explain the 4 layers: Sensing (BLE tags) $\rightarrow$ Gateway (ESP32 PoE readers) $\rightarrow$ Network (Three-tier LAN with isolated IoT VLAN 20 and MQTT broker) $\rightarrow$ Application (Location engine and dashboard).

2. **Step 2: Demonstrate the Live Dashboard & Data Flow (Slide 7)**
   - Point to the **Floor Map**: show the 7 rooms and the 12 medical assets.
   - Point to the **Top Pipeline**: show how packets travel across the 7 stages in real time.
   - Point to the **Live Wire Capture Terminal**: show actual incoming MQTT messages on topic `hospital/blockA/floor3/gwXX` with RSSI and distance calculated via the log-distance path loss model:
     $$d = 10^{\frac{\text{TxPower} - \text{RSSI}}{10 \cdot n}}$$

3. **Step 3: Trigger a Live Geofence Breach (Slide 2 & 8)**
   - Click the **"Demo Controls"** button in the navbar.
   - Click **"1. ICU Ventilator Geofence Breach"**.
   - Notice:
     - The Hamilton Ventilator is moved from the ICU to Perimeter Exit Gate 3.
     - The Exit zone flashes red on the floor plan.
     - A loud hospital security alert chimes.
     - An alert is logged: *"PERIMETER SECURITY BREACH: Hamilton-C6 Mechanical Ventilator is within 1.8m of Exit Gate 3!"*

4. **Step 4: Demonstrate the Dedicated Computer Networks Page (Slide 5 & 6)**
   - Navigate to the **"Network Architecture"** tab (`/network`).
   - Explain the **Three-Tier Topology**: Redundant Core Switches (`CORE-SW-01` & `CORE-SW-02`) running VRRP over 10G fiber, Distribution Switches (`DIST-SW-BLKA` & `DIST-SW-BLKB`), and Access Switches (`ACC-SW-FL3`) powering ceiling gateways via 802.3af PoE.
   - Explain the **Subnetting (`10.20.0.0/22`)**: 22 network bits, 10 host bits, mask `255.255.252.0`, 1,022 usable hosts (`10.20.0.1` to `10.20.3.254`). Type `10.20.1.15` in the interactive subnet validator to show it belongs to the gateway pool.
   - Run the **Interactive Firewall ACL Tester**:
     - Source: VLAN 40 (Guest Wi-Fi) $\rightarrow$ Destination: VLAN 20 (IoT Gateway) $\rightarrow$ Result: **DROP** (`ACL-GUEST-ISOLATE`).
     - Source: VLAN 20 (IoT Gateway) $\rightarrow$ Destination: VLAN 30 (Broker) on Port 1883 $\rightarrow$ Result: **PERMIT** (`ACL-IOT-BROKER-PERMIT`).

5. **Step 5: Explain the Protocol Stack & Viva Points (Slide 6 & 8)**
   - Point to the 5-layer Protocol Stack table.
   - Explain why MQTT runs on **TCP over Port 1883/8883** (guaranteed ordered delivery with QoS 1) rather than UDP.
   - Explain how WPA3-Enterprise 802.1X and TLS 1.3 prevent rogue gateways and MITM eavesdropping on patient floors.

---

## 6. Computer Networks Concepts Summary

- **Hierarchical Network Design:** Core, Distribution, and Access layers; eliminates single points of failure.
- **VLAN Segmentation (IEEE 802.1Q):** VLAN 10 (Clinical), VLAN 20 (IoT RTLS), VLAN 30 (Servers), VLAN 40 (Guest Wi-Fi).
- **IP Addressing & Subnetting:** Class A private block (`10.0.0.0/8`), CIDR `/22`, Subnet Mask `255.255.252.0`, total 1,024 addresses, usable 1,022 hosts.
- **Transport Layer:** TCP 3-way handshake, sequence numbers, reliability vs. UDP connectionless delivery.
- **Application Layer Protocols:** MQTT v3.1.1 (publish/subscribe, topic hierarchy, QoS 1), HTTP/REST, HL7 FHIR.
- **Network Security:** Stateful firewall ACLs, WPA3-Enterprise with 802.1X/RADIUS (EAP-TLS certificates), TLS 1.3 payload encryption on port 8883.
- **Radio Propagation Physics:** Friis / Log-distance path loss indoors with multipath Gaussian noise.

#   S m a r t - H o s p i t a l - A s s e t - T r a c k i n g - S y s t e m  
 