"""
Database module for Smart Hospital Asset Tracking System.
Uses SQLite for persistent storage of assets, gateways, alerts, location history, and network packets.
"""

import sqlite3
import os
import json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hospital_assets.db')


def get_db_connection():
    """Returns a SQLite connection with dict-like row access."""
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(force_reset=False):
    """Initializes the database schema and populates initial seed data."""
    if force_reset and os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
        except Exception:
            pass

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Rooms / Wards table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            room_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            floor INTEGER DEFAULT 3,
            block TEXT DEFAULT 'Block A',
            is_exit_zone INTEGER DEFAULT 0,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL,
            color TEXT DEFAULT '#0d9488',
            allowed_categories TEXT DEFAULT '[]'
        )
    ''')

    # 2. Gateways table (Layer 2: IoT Gateway Simulation)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gateways (
            gateway_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            room_id TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            mac_address TEXT NOT NULL,
            vlan_id INTEGER DEFAULT 20,
            switch_port TEXT NOT NULL,
            tx_power INTEGER DEFAULT -59,
            status TEXT DEFAULT 'ONLINE',
            packets_forwarded INTEGER DEFAULT 0,
            last_heartbeat TEXT,
            FOREIGN KEY (room_id) REFERENCES rooms(room_id)
        )
    ''')

    # 3. Assets table (Layer 1: BLE Asset Tags)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assets (
            asset_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            model TEXT NOT NULL,
            tag_id TEXT UNIQUE NOT NULL,
            tag_mac TEXT NOT NULL,
            assigned_room_id TEXT NOT NULL,
            current_room_id TEXT NOT NULL,
            current_gateway_id TEXT NOT NULL,
            rssi INTEGER DEFAULT -65,
            distance_m REAL DEFAULT 1.5,
            battery INTEGER DEFAULT 95,
            status TEXT DEFAULT 'Available',
            maintenance_status TEXT DEFAULT 'Good',
            is_deleted INTEGER DEFAULT 0,
            last_updated TEXT,
            FOREIGN KEY (assigned_room_id) REFERENCES rooms(room_id),
            FOREIGN KEY (current_room_id) REFERENCES rooms(room_id),
            FOREIGN KEY (current_gateway_id) REFERENCES gateways(gateway_id)
        )
    ''')

    # 4. Alerts table (Geofencing, Boundary, Low Battery)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT NOT NULL,
            asset_name TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            room_id TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            acknowledged INTEGER DEFAULT 0,
            FOREIGN KEY (asset_id) REFERENCES assets(asset_id),
            FOREIGN KEY (room_id) REFERENCES rooms(room_id)
        )
    ''')

    # 5. Location History table (Movement History with previous and new locations)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS location_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT NOT NULL,
            previous_room_id TEXT,
            room_id TEXT NOT NULL,
            gateway_id TEXT NOT NULL,
            rssi INTEGER NOT NULL,
            distance_m REAL NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
        )
    ''')

    # 6. Network Logs table (Layer 3 & 4 Packet Transmissions)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS network_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            source_ip TEXT NOT NULL,
            dest_ip TEXT NOT NULL,
            protocol TEXT NOT NULL,
            port INTEGER NOT NULL,
            vlan INTEGER NOT NULL,
            topic TEXT NOT NULL,
            packet_summary TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL
        )
    ''')

    # 7. Equipment Requests table (Department Request & Admin Approval System)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipment_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT NOT NULL,
            requesting_room_id TEXT NOT NULL,
            current_room_id_at_request TEXT NOT NULL,
            destination_room_id TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            reason TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            admin_decision TEXT DEFAULT 'Pending',
            decision_at TEXT,
            rejection_reason TEXT DEFAULT '',
            FOREIGN KEY (asset_id) REFERENCES assets(asset_id),
            FOREIGN KEY (requesting_room_id) REFERENCES rooms(room_id),
            FOREIGN KEY (destination_room_id) REFERENCES rooms(room_id)
        )
    ''')

    # 8. Maintenance Records table (Feature 3: Preventative & Corrective Maintenance)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS maintenance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT NOT NULL,
            maintenance_status TEXT NOT NULL,
            last_service_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            technician_name TEXT DEFAULT 'BioMed Engineering',
            description TEXT DEFAULT '',
            cost REAL DEFAULT 0.0,
            recorded_at TEXT NOT NULL,
            FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
        )
    ''')

    # 9. Notifications & Alerts table (Feature 4: Centralized Notification System)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            severity TEXT NOT NULL,
            asset_id TEXT,
            room_id TEXT,
            created_at TEXT NOT NULL,
            is_read INTEGER DEFAULT 0
        )
    ''')

    # 10. Users table (Feature 6: Role-Based Access Control)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL,
            department TEXT DEFAULT 'Central Admin',
            created_at TEXT NOT NULL
        )
    ''')

    # Safe schema migration for is_deleted column & status normalization
    try:
        cursor.execute('ALTER TABLE assets ADD COLUMN is_deleted INTEGER DEFAULT 0')
    except Exception:
        pass
    try:
        cursor.execute("UPDATE assets SET maintenance_status = 'Good' WHERE maintenance_status = 'OK'")
        cursor.execute("UPDATE assets SET maintenance_status = 'Needs Repair' WHERE maintenance_status = 'Overdue'")
    except Exception:
        pass

    conn.commit()

    # Check if seed data exists or needs re-seed
    cursor.execute('SELECT COUNT(*) FROM rooms')
    if cursor.fetchone()[0] == 0:
        seed_data(cursor)
        conn.commit()

    # Ensure users and initial sample records exist even on existing database files
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        seed_users_and_samples(cursor)
        conn.commit()

    conn.close()


def seed_users_and_samples(cursor):
    """Populates default roles/users, sample maintenance records, and notifications."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Initial Users (Feature 6: Role-Based Access Control)
    users = [
        ('admin', generate_password_hash('admin123'), 'Administrator', 'ADMIN', 'Hospital Administration', now),
        ('dr_sharma', generate_password_hash('doctor123'), 'Dr. A. Sharma (MD)', 'DOCTOR', 'ICU / Critical Care', now),
        ('nurse_priya', generate_password_hash('staff123'), 'Priya Nair (RN)', 'STAFF', 'Emergency Room', now)
    ]
    cursor.executemany('''
        INSERT OR IGNORE INTO users (username, password_hash, full_name, role, department, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', users)

    # Initial Maintenance Records (Feature 3: Maintenance Tracking)
    maint_records = [
        ('AST-VENT-01', 'Good', '2026-10-15', '2026-11-25', 'Dräger Authorized BioMed', 'Semi-annual calibration, pressure sensor testing, HEPA filter replacement.', 150.0, now),
        ('AST-DEFIB-01', 'Good', '2026-09-20', '2026-12-15', 'Zoll Medical Support', 'Capacitor discharge test (200J shock test), ECG leads continuity checked.', 120.0, now),
        ('AST-ECG-01', 'Due Soon', '2026-05-10', '2026-11-08', 'Hospital In-House BioMed', 'Annual diagnostic accuracy calibration and lead-wire impedance certification.', 85.0, now),
        ('AST-XRAY-01', 'Needs Repair', '2026-04-12', '2026-10-20', 'Shimadzu Radiology Care', 'High-voltage collimator motor erratic feedback. Requires motor overhaul.', 650.0, now)
    ]
    cursor.executemany('''
        INSERT INTO maintenance_records (asset_id, maintenance_status, last_service_date, due_date, technician_name, description, cost, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', maint_records)

    # Initial Notifications (Feature 4: Notifications & Alerts)
    notifications = [
        ('Welcome to Smart Hospital RTLS', 'Hospital IoT asset tracking and maintenance system initialized.', 'SYSTEM', 'INFO', None, None, now, 0),
        ('Maintenance Due Soon: ECG Machine', 'GE MAC 2000 12-Lead ECG (AST-ECG-01) calibration due within 7 days.', 'MAINTENANCE_DUE', 'WARNING', 'AST-ECG-01', 'CARDIO', now, 0),
        ('Overdue Repair Notice: Mobile X-Ray', 'Shimadzu MobileDaRt (AST-XRAY-01) motor service is overdue. Please schedule repair.', 'NEEDS_REPAIR', 'CRITICAL', 'AST-XRAY-01', 'STORAGE', now, 0)
    ]
    cursor.executemany('''
        INSERT INTO notifications (title, description, category, severity, asset_id, room_id, created_at, is_read)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', notifications)


def seed_data(cursor):
    """Inserts initial hospital floor plan with the 7 required locations, gateways, and assets."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # The exact 7 hospital locations required:
    # 1. ICU
    # 2. Emergency Room
    # 3. Operation Theatre
    # 4. General Ward
    # 5. Cardiology
    # 6. Pharmacy
    # 7. Storage
    # SVG coordinates for an 800 x 480 canvas
    rooms = [
        ('ICU', 'ICU', 3, 'Block A', 0, 25, 25, 235, 200, '#0284c7', '["Ventilator", "Patient Monitor", "Defibrillator"]'),
        ('ER', 'Emergency Room', 3, 'Block A', 0, 275, 25, 250, 200, '#dc2626', '["Defibrillator", "Patient Monitor", "ECG Machine", "Wheelchair"]'),
        ('OT', 'Operation Theatre', 3, 'Block A', 0, 540, 25, 235, 200, '#059669', '["Ventilator", "Patient Monitor", "Defibrillator", "Infusion Pump"]'),
        ('GEN', 'General Ward', 3, 'Block A', 0, 25, 275, 185, 190, '#0891b2', '["Infusion Pump", "ECG Machine", "Wheelchair"]'),
        ('CARDIO', 'Cardiology', 3, 'Block B', 0, 225, 275, 185, 190, '#2563eb', '["ECG Machine", "Patient Monitor", "Defibrillator", "Infusion Pump"]'),
        ('PHARM', 'Pharmacy', 3, 'Block B', 0, 425, 275, 175, 190, '#7c3aed', '["Infusion Pump", "Wheelchair"]'),
        ('STORAGE', 'Storage', 3, 'Block B', 0, 615, 275, 160, 190, '#d97706', '["Portable X-Ray", "Wheelchair", "Ventilator", "Defibrillator"]')
    ]
    cursor.executemany('''
        INSERT INTO rooms (room_id, name, floor, block, is_exit_zone, x, y, width, height, color, allowed_categories)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', rooms)

    # Gateways for each room (VLAN 20 Subnet: 10.20.0.0/22)
    gateways = [
        ('GW-ICU-01', 'ICU Ceiling Gateway', 'ICU', '10.20.1.10', '00:1A:79:B1:01:01', 20, 'ACC-SW-FL3/Gi0/1', -59, 'ONLINE', 12, now),
        ('GW-ER-01', 'Emergency Room Gateway', 'ER', '10.20.1.11', '00:1A:79:B1:01:02', 20, 'ACC-SW-FL3/Gi0/2', -59, 'ONLINE', 15, now),
        ('GW-OT-01', 'Operation Theatre Gateway', 'OT', '10.20.1.12', '00:1A:79:B1:01:03', 20, 'ACC-SW-FL3/Gi0/3', -59, 'ONLINE', 9, now),
        ('GW-GEN-01', 'General Ward Gateway', 'GEN', '10.20.1.13', '00:1A:79:B1:01:04', 20, 'ACC-SW-FL3/Gi0/4', -59, 'ONLINE', 22, now),
        ('GW-CARDIO-01', 'Cardiology Gateway', 'CARDIO', '10.20.1.14', '00:1A:79:B1:01:05', 20, 'ACC-SW-FL3/Gi0/5', -59, 'ONLINE', 18, now),
        ('GW-PHARM-01', 'Pharmacy Gateway', 'PHARM', '10.20.1.15', '00:1A:79:B1:01:06', 20, 'ACC-SW-FL3/Gi0/6', -59, 'ONLINE', 8, now),
        ('GW-STORAGE-01', 'Storage Depot Gateway', 'STORAGE', '10.20.1.16', '00:1A:79:B1:01:07', 20, 'ACC-SW-FL3/Gi0/7', -59, 'ONLINE', 14, now)
    ]
    cursor.executemany('''
        INSERT INTO gateways (gateway_id, name, room_id, ip_address, mac_address, vlan_id, switch_port, tx_power, status, packets_forwarded, last_heartbeat)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', gateways)

    # 12 Hospital Assets
    assets = [
        ('AST-VENT-01', 'Hamilton-C6 Mechanical Ventilator', 'Ventilator', 'Hamilton Medical C6', 'TAG-BLE-701', 'AC:23:3F:8A:70:01', 'ICU', 'ICU', 'GW-ICU-01', -62, 1.3, 94, 'In Use', 'Good', 0, now),
        ('AST-VENT-02', 'Dräger Evita V800 ICU Ventilator', 'Ventilator', 'Dräger Evita V800', 'TAG-BLE-702', 'AC:23:3F:8A:70:02', 'ICU', 'ICU', 'GW-ICU-01', -68, 2.2, 88, 'Available', 'Good', 0, now),
        ('AST-DEFIB-01', 'Zoll R Series Crash Defibrillator', 'Defibrillator', 'Zoll R-Series ALS', 'TAG-BLE-703', 'AC:23:3F:8A:70:03', 'ER', 'ER', 'GW-ER-01', -58, 0.9, 91, 'Available', 'Good', 0, now),
        ('AST-DEFIB-02', 'Philips HeartStart XL+ Defibrillator', 'Defibrillator', 'Philips HeartStart XL+', 'TAG-BLE-704', 'AC:23:3F:8A:70:04', 'OT', 'OT', 'GW-OT-01', -64, 1.6, 76, 'In Use', 'Good', 0, now),
        ('AST-MON-01', 'Mindray BeneVision N17 Patient Monitor', 'Patient Monitor', 'Mindray N17 Multiparameter', 'TAG-BLE-705', 'AC:23:3F:8A:70:05', 'ICU', 'ICU', 'GW-ICU-01', -60, 1.1, 82, 'In Use', 'Good', 0, now),
        ('AST-MON-02', 'GE Carescape B650 Vital Signs Monitor', 'Patient Monitor', 'GE Carescape B650', 'TAG-BLE-706', 'AC:23:3F:8A:70:06', 'ER', 'ER', 'GW-ER-01', -63, 1.4, 69, 'Available', 'Good', 0, now),
        ('AST-PUMP-01', 'Alaris 8015 Smart Infusion Pump', 'Infusion Pump', 'BD Alaris System 8015', 'TAG-BLE-707', 'AC:23:3F:8A:70:07', 'GEN', 'GEN', 'GW-GEN-01', -67, 2.0, 85, 'In Use', 'Good', 0, now),
        ('AST-PUMP-02', 'Baxter Sigma Spectrum Infusion Pump', 'Infusion Pump', 'Baxter Sigma Spectrum 35700', 'TAG-BLE-708', 'AC:23:3F:8A:70:08', 'CARDIO', 'CARDIO', 'GW-CARDIO-01', -65, 1.7, 73, 'Available', 'Good', 0, now),
        ('AST-ECG-01', 'GE MAC 2000 12-Lead Diagnostic ECG', 'ECG Machine', 'GE Healthcare MAC 2000', 'TAG-BLE-709', 'AC:23:3F:8A:70:09', 'CARDIO', 'CARDIO', 'GW-CARDIO-01', -61, 1.2, 58, 'Available', 'Due Soon', 0, now),
        ('AST-ECG-02', 'Philips PageWriter TC70 Cardiograph', 'ECG Machine', 'Philips PageWriter TC70', 'TAG-BLE-710', 'AC:23:3F:8A:70:10', 'GEN', 'GEN', 'GW-GEN-01', -71, 2.8, 44, 'In Use', 'Good', 0, now),
        ('AST-WCHR-01', 'Stryker Prime Ergonomic Wheelchair', 'Wheelchair', 'Stryker Prime 1105', 'TAG-BLE-711', 'AC:23:3F:8A:70:11', 'ER', 'ER', 'GW-ER-01', -66, 1.9, 88, 'Available', 'Good', 0, now),
        ('AST-XRAY-01', 'Shimadzu MobileDaRt Mobile X-Ray', 'Portable X-Ray', 'Shimadzu MobileDaRt Evolution', 'TAG-BLE-712', 'AC:23:3F:8A:70:12', 'STORAGE', 'STORAGE', 'GW-STORAGE-01', -59, 1.0, 96, 'Maintenance', 'Needs Repair', 0, now)
    ]
    cursor.executemany('''
        INSERT INTO assets (asset_id, name, category, model, tag_id, tag_mac, assigned_room_id, current_room_id, current_gateway_id, rssi, distance_m, battery, status, maintenance_status, is_deleted, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', assets)

    # Initial baseline location history
    for a in assets:
        cursor.execute('''
            INSERT INTO location_history (asset_id, previous_room_id, room_id, gateway_id, rssi, distance_m, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (a[0], None, a[7], a[8], a[9], a[10], now))

    # Initial network logs
    cursor.execute('''
        INSERT INTO network_logs (timestamp, source_ip, dest_ip, protocol, port, vlan, topic, packet_summary, payload_json, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (now, '10.20.1.10', '10.30.0.15', 'MQTT/TCP', 1883, 20, 'hospital/blockA/floor3/gw-icu-01',
          'SYSTEM BOOT: All 12 medical assets registered on IoT VLAN 20',
          '{"event":"SYSTEM_READY","status":"MANUAL_MODE_ACTIVE"}', 'DELIVERED'))

    # Initial Users (Feature 6: Role-Based Access Control)
    users = [
        ('admin', generate_password_hash('admin123'), 'Administrator', 'ADMIN', 'Hospital Administration', now),
        ('dr_sharma', generate_password_hash('doctor123'), 'Dr. A. Sharma (MD)', 'DOCTOR', 'ICU / Critical Care', now),
        ('nurse_priya', generate_password_hash('staff123'), 'Priya Nair (RN)', 'STAFF', 'Emergency Room', now)
    ]
    cursor.executemany('''
        INSERT OR IGNORE INTO users (username, password_hash, full_name, role, department, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', users)

    # Initial Maintenance Records (Feature 3: Maintenance Tracking)
    maint_records = [
        ('AST-VENT-01', 'Good', '2026-10-15', '2026-11-25', 'Dräger Authorized BioMed', 'Semi-annual calibration, pressure sensor testing, HEPA filter replacement.', 150.0, now),
        ('AST-DEFIB-01', 'Good', '2026-09-20', '2026-12-15', 'Zoll Medical Support', 'Capacitor discharge test (200J shock test), ECG leads continuity checked.', 120.0, now),
        ('AST-ECG-01', 'Due Soon', '2026-05-10', '2026-11-08', 'Hospital In-House BioMed', 'Annual diagnostic accuracy calibration and lead-wire impedance certification.', 85.0, now),
        ('AST-XRAY-01', 'Needs Repair', '2026-04-12', '2026-10-20', 'Shimadzu Radiology Care', 'High-voltage collimator motor erratic feedback. Requires motor overhaul.', 650.0, now)
    ]
    cursor.executemany('''
        INSERT INTO maintenance_records (asset_id, maintenance_status, last_service_date, due_date, technician_name, description, cost, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', maint_records)

    # Initial Notifications (Feature 4: Notifications & Alerts)
    notifications = [
        ('Welcome to Smart Hospital RTLS', 'Hospital IoT asset tracking and maintenance system initialized.', 'SYSTEM', 'INFO', None, None, now, 0),
        ('Maintenance Due Soon: ECG Machine', 'GE MAC 2000 12-Lead ECG (AST-ECG-01) calibration due within 7 days.', 'MAINTENANCE_DUE', 'WARNING', 'AST-ECG-01', 'CARDIO', now, 0),
        ('Overdue Repair Notice: Mobile X-Ray', 'Shimadzu MobileDaRt (AST-XRAY-01) motor service is overdue. Please schedule repair.', 'NEEDS_REPAIR', 'CRITICAL', 'AST-XRAY-01', 'STORAGE', now, 0)
    ]
    cursor.executemany('''
        INSERT INTO notifications (title, description, category, severity, asset_id, room_id, created_at, is_read)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', notifications)


def get_all_assets(include_deleted=False):
    """Returns all active assets joined with room and gateway names."""
    conn = get_db_connection()
    cursor = conn.cursor()
    where_clause = "" if include_deleted else "WHERE COALESCE(a.is_deleted, 0) = 0"
    cursor.execute(f'''
        SELECT a.*, 
               r.name as current_room_name, r.name as current_location, r.name as location, r.is_exit_zone, r.color as room_color,
               ar.name as assigned_room_name, ar.name as assigned_location,
               g.name as gateway_name, g.ip_address as gateway_ip
        FROM assets a
        LEFT JOIN rooms r ON a.current_room_id = r.room_id
        LEFT JOIN rooms ar ON a.assigned_room_id = ar.room_id
        LEFT JOIN gateways g ON a.current_gateway_id = g.gateway_id
        {where_clause}
        ORDER BY a.asset_id ASC
    ''')
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_asset_by_id(asset_id, allow_deleted=False):
    """Returns a single asset's details with recent location history."""
    conn = get_db_connection()
    cursor = conn.cursor()
    del_clause = "" if allow_deleted else "AND COALESCE(a.is_deleted, 0) = 0"
    cursor.execute(f'''
        SELECT a.*, 
               r.name as current_room_name, r.name as current_location, r.name as location, r.is_exit_zone,
               ar.name as assigned_room_name, ar.name as assigned_location,
               g.name as gateway_name, g.ip_address as gateway_ip
        FROM assets a
        LEFT JOIN rooms r ON a.current_room_id = r.room_id
        LEFT JOIN rooms ar ON a.assigned_room_id = ar.room_id
        LEFT JOIN gateways g ON a.current_gateway_id = g.gateway_id
        WHERE a.asset_id = ? {del_clause}
    ''', (asset_id,))
    asset = cursor.fetchone()
    if not asset:
        conn.close()
        return None
    asset_dict = dict(asset)

    # Fetch movement history for this asset
    cursor.execute('''
        SELECT lh.*, 
               r.name as room_name, 
               pr.name as previous_room_name,
               g.name as gateway_name
        FROM location_history lh
        JOIN rooms r ON lh.room_id = r.room_id
        LEFT JOIN rooms pr ON lh.previous_room_id = pr.room_id
        JOIN gateways g ON lh.gateway_id = g.gateway_id
        WHERE lh.asset_id = ?
        ORDER BY lh.id DESC LIMIT 15
    ''', (asset_id,))
    asset_dict['history'] = [dict(h) for h in cursor.fetchall()]
    conn.close()
    return asset_dict


def get_all_rooms():
    """Returns all rooms with asset counts."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.*, COUNT(a.asset_id) as asset_count
        FROM rooms r
        LEFT JOIN assets a ON r.room_id = a.current_room_id
        GROUP BY r.room_id
        ORDER BY r.rowid ASC
    ''')
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_all_gateways():
    """Returns all gateways with current status and room info."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT g.*, r.name as room_name
        FROM gateways g
        JOIN rooms r ON g.room_id = r.room_id
        ORDER BY g.gateway_id ASC
    ''')
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_movement_history(limit=50):
    """Returns complete equipment movement history with previous and new locations."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT lh.id, lh.asset_id, lh.timestamp, lh.rssi, lh.distance_m,
               a.name as asset_name, a.category, a.model, a.tag_id,
               r.name as new_room_name, r.room_id as new_room_id,
               COALESCE(pr.name, 'Initial Baseline Location') as previous_room_name,
               pr.room_id as previous_room_id,
               g.name as gateway_name, g.ip_address as gateway_ip
        FROM location_history lh
        JOIN assets a ON lh.asset_id = a.asset_id
        JOIN rooms r ON lh.room_id = r.room_id
        LEFT JOIN rooms pr ON lh.previous_room_id = pr.room_id
        JOIN gateways g ON lh.gateway_id = g.gateway_id
        ORDER BY lh.id DESC LIMIT ?
    ''', (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_active_alerts(limit=50):
    """Returns active unacknowledged and recent alerts."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT al.*, r.name as room_name
        FROM alerts al
        JOIN rooms r ON al.room_id = r.room_id
        ORDER BY al.acknowledged ASC, al.id DESC LIMIT ?
    ''', (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_recent_network_logs(limit=40):
    """Returns recent network packet logs for live terminal inspection."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM network_logs
        ORDER BY id DESC LIMIT ?
    ''', (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def log_network_packet(source_ip, dest_ip, protocol, port, vlan, topic, summary, payload_dict, status='DELIVERED'):
    """Logs a simulated network packet into the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO network_logs (timestamp, source_ip, dest_ip, protocol, port, vlan, topic, packet_summary, payload_json, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (now, source_ip, dest_ip, protocol, port, vlan, topic, summary, json.dumps(payload_dict), status))
    conn.commit()
    conn.close()


def add_alert(asset_id, asset_name, alert_type, severity, room_id, message):
    """Records an alert if a similar unacknowledged alert isn't already active."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id FROM alerts
        WHERE asset_id = ? AND alert_type = ? AND acknowledged = 0
    ''', (asset_id, alert_type))
    existing = cursor.fetchone()
    if not existing:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''
            INSERT INTO alerts (asset_id, asset_name, alert_type, severity, room_id, message, timestamp, acknowledged)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        ''', (asset_id, asset_name, alert_type, severity, room_id, message, now))
        conn.commit()
    conn.close()


def acknowledge_alert(alert_id):
    """Marks an alert as acknowledged."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE alerts SET acknowledged = 1 WHERE id = ?', (alert_id,))
    conn.commit()
    conn.close()


def clear_all_alerts():
    """Clears all acknowledged alerts."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM alerts WHERE acknowledged = 1')
    conn.commit()
    conn.close()


def update_asset_telemetry(asset_id, new_room_id, new_gateway_id, rssi, distance_m, battery=None, previous_room_id=None, sync_assigned=False):
    """Updates asset location and logs the movement in location_history."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if sync_assigned:
        if battery is not None:
            cursor.execute('''
                UPDATE assets
                SET current_room_id = ?, assigned_room_id = ?, current_gateway_id = ?, rssi = ?, distance_m = ?, battery = ?, last_updated = ?
                WHERE asset_id = ?
            ''', (new_room_id, new_room_id, new_gateway_id, rssi, distance_m, battery, now, asset_id))
        else:
            cursor.execute('''
                UPDATE assets
                SET current_room_id = ?, assigned_room_id = ?, current_gateway_id = ?, rssi = ?, distance_m = ?, last_updated = ?
                WHERE asset_id = ?
            ''', (new_room_id, new_room_id, new_gateway_id, rssi, distance_m, now, asset_id))
    else:
        if battery is not None:
            cursor.execute('''
                UPDATE assets
                SET current_room_id = ?, current_gateway_id = ?, rssi = ?, distance_m = ?, battery = ?, last_updated = ?
                WHERE asset_id = ?
            ''', (new_room_id, new_gateway_id, rssi, distance_m, battery, now, asset_id))
        else:
            cursor.execute('''
                UPDATE assets
                SET current_room_id = ?, current_gateway_id = ?, rssi = ?, distance_m = ?, last_updated = ?
                WHERE asset_id = ?
            ''', (new_room_id, new_gateway_id, rssi, distance_m, now, asset_id))

    # Increment gateway packet count
    cursor.execute('''
        UPDATE gateways
        SET packets_forwarded = packets_forwarded + 1, last_heartbeat = ?
        WHERE gateway_id = ?
    ''', (now, new_gateway_id))

    # Add to movement history
    cursor.execute('''
        INSERT INTO location_history (asset_id, previous_room_id, room_id, gateway_id, rssi, distance_m, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (asset_id, previous_room_id, new_room_id, new_gateway_id, rssi, distance_m, now))

    conn.commit()
    conn.close()


def get_dashboard_stats():
    """Calculates aggregated hospital KPIs."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM assets')
    total_assets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM assets WHERE status = 'Available'")
    available_assets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM assets WHERE status = 'In Use'")
    in_use_assets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM assets WHERE status = 'Maintenance'")
    maintenance_assets = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM alerts WHERE acknowledged = 0')
    active_alerts = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM alerts WHERE acknowledged = 0 AND severity = 'CRITICAL'")
    critical_alerts = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM gateways WHERE status = "ONLINE"')
    online_gateways = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM gateways')
    total_gateways = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM location_history WHERE previous_room_id IS NOT NULL')
    total_movements = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM equipment_requests WHERE status = 'Pending'")
    pending_requests = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM equipment_requests")
    total_requests = cursor.fetchone()[0]

    conn.close()
    return {
        'total_assets': total_assets,
        'available_assets': available_assets,
        'in_use_assets': in_use_assets,
        'maintenance_assets': maintenance_assets,
        'active_alerts': active_alerts,
        'critical_alerts': critical_alerts,
        'online_gateways': online_gateways,
        'total_gateways': total_gateways,
        'total_movements': total_movements,
        'pending_requests': pending_requests,
        'total_requests': total_requests,
        'iot_subnet': '10.20.0.0/22',
        'usable_hosts': 1022
    }


def create_equipment_request(asset_id, requesting_room_id, destination_room_id, quantity=1, reason=""):
    """
    Submits a new equipment transfer request from a department.
    Validates asset existence, ensures equipment is not already in target ward,
    and prevents duplicate pending requests.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Validate asset existence
    asset = get_asset_by_id(asset_id)
    if not asset:
        conn.close()
        return False, f"Equipment ID '{asset_id}' not found.", None

    # 2. Validate rooms
    cursor.execute('SELECT name FROM rooms WHERE room_id = ?', (requesting_room_id,))
    req_room = cursor.fetchone()
    cursor.execute('SELECT name FROM rooms WHERE room_id = ?', (destination_room_id,))
    dest_room = cursor.fetchone()
    if not req_room:
        conn.close()
        return False, f"Requesting room '{requesting_room_id}' not recognized.", None
    if not dest_room:
        conn.close()
        return False, f"Destination room '{destination_room_id}' not recognized.", None

    req_room_name = req_room['name']
    dest_room_name = dest_room['name']
    current_room_id = asset['current_room_id']
    current_room_name = asset['current_room_name']

    # 3. Check if equipment is already in requested destination
    if current_room_id == destination_room_id:
        conn.close()
        return False, f"Equipment '{asset['name']}' is already physically located in {dest_room_name}.", None

    # 4. Check for duplicate pending request for same asset & destination
    cursor.execute('''
        SELECT id FROM equipment_requests 
        WHERE asset_id = ? AND destination_room_id = ? AND status = 'Pending'
    ''', (asset_id, destination_room_id))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return False, f"A pending request (ID #{existing['id']}) for '{asset['name']}' to {dest_room_name} is already awaiting admin review.", None

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO equipment_requests (
            asset_id, requesting_room_id, current_room_id_at_request, destination_room_id,
            quantity, reason, created_at, status, admin_decision
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', 'Pending')
    ''', (asset_id, requesting_room_id, current_room_id, destination_room_id, quantity, reason or '', now))
    req_id = cursor.lastrowid
    conn.commit()

    # Create admin alert
    add_alert(
        asset_id=asset_id,
        asset_name=asset['name'],
        alert_type='EQUIPMENT_REQUEST',
        severity='INFO',
        room_id=destination_room_id,
        message=f"TRANSFER REQUEST #{req_id}: {req_room_name} requested '{asset['name']}' from {current_room_name}."
    )

    conn.close()
    return True, f"Equipment request #{req_id} submitted for {asset['name']} ({current_room_name} → {dest_room_name}).", req_id


def get_all_equipment_requests(status=None, room=None, limit=100):
    """
    Returns equipment requests with joined asset, requesting room,
    destination room, and real-time live location.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = '''
        SELECT er.*,
               a.name as asset_name, a.category, a.model, a.tag_id,
               a.current_room_id as live_current_room_id,
               live_r.name as live_current_room_name,
               req_r.name as requesting_room_name,
               dest_r.name as destination_room_name,
               curr_r.name as current_room_name_at_request
        FROM equipment_requests er
        JOIN assets a ON er.asset_id = a.asset_id
        JOIN rooms req_r ON er.requesting_room_id = req_r.room_id
        JOIN rooms dest_r ON er.destination_room_id = dest_r.room_id
        JOIN rooms curr_r ON er.current_room_id_at_request = curr_r.room_id
        JOIN rooms live_r ON a.current_room_id = live_r.room_id
    '''
    params = []
    conditions = []

    if status and status.lower() != 'all':
        conditions.append('er.status = ?')
        params.append(status)

    if room and room.lower() != 'all':
        conditions.append('(er.requesting_room_id = ? OR er.destination_room_id = ?)')
        params.extend([room, room])

    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)

    query += ' ORDER BY er.id DESC LIMIT ?'
    params.append(limit)

    cursor.execute(query, tuple(params))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    for r in rows:
        r['location_changed_since_request'] = (r['live_current_room_id'] != r['current_room_id_at_request'])
    return rows


def get_equipment_request_by_id(request_id):
    """Returns a single equipment request by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT er.*,
               a.name as asset_name, a.category, a.model, a.tag_id,
               a.current_room_id as live_current_room_id,
               live_r.name as live_current_room_name,
               req_r.name as requesting_room_name,
               dest_r.name as destination_room_name,
               curr_r.name as current_room_name_at_request
        FROM equipment_requests er
        JOIN assets a ON er.asset_id = a.asset_id
        JOIN rooms req_r ON er.requesting_room_id = req_r.room_id
        JOIN rooms dest_r ON er.destination_room_id = dest_r.room_id
        JOIN rooms curr_r ON er.current_room_id_at_request = curr_r.room_id
        JOIN rooms live_r ON a.current_room_id = live_r.room_id
        WHERE er.id = ?
    ''', (request_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    r = dict(row)
    r['location_changed_since_request'] = (r['live_current_room_id'] != r['current_room_id_at_request'])
    return r


def get_pending_requests_count():
    """Returns number of requests currently pending admin review."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM equipment_requests WHERE status = 'Pending'")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def update_equipment_request(request_id, status, admin_decision, rejection_reason=''):
    """Updates status, admin decision, and rejection reason for a request."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        UPDATE equipment_requests
        SET status = ?, admin_decision = ?, decision_at = ?, rejection_reason = ?
        WHERE id = ?
    ''', (status, admin_decision, now, rejection_reason or '', request_id))
    conn.commit()
    conn.close()


# =====================================================================
# Feature 1: Add New Equipment & Equipment Management
# =====================================================================

def add_equipment(asset_id, name, category, model=None, assigned_room_id='GEN', current_room_id=None, tag_id=None, quantity=1, status='Available'):
    """
    Registers a new medical asset into the hospital RTLS database.
    Saves the EXACT equipment name entered by Admin.
    Prevents duplicate active IDs. Automatically generates BLE beacon credentials and gateway mapping.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    asset_id = (asset_id or '').strip().upper()
    name = (name or '').strip()
    category = (category or 'Medical Device').strip()
    model = (model or '').strip() or f"{name} Std"

    # 1. Check for duplicate ID
    cursor.execute('SELECT asset_id, is_deleted FROM assets WHERE asset_id = ?', (asset_id,))
    existing = cursor.fetchone()
    if existing and existing['is_deleted'] == 0:
        conn.close()
        return False, f"Equipment ID '{asset_id}' already exists in the database. Please specify a unique ID.", None

    if not current_room_id:
        current_room_id = assigned_room_id

    # 2. Validate room exists
    cursor.execute('SELECT name FROM rooms WHERE room_id = ?', (current_room_id,))
    room_row = cursor.fetchone()
    if not room_row:
        conn.close()
        return False, f"Hospital location '{current_room_id}' not found.", None
    room_name = room_row['name']

    # 3. Associate with gateway
    cursor.execute('SELECT gateway_id FROM gateways WHERE room_id = ?', (current_room_id,))
    gw_row = cursor.fetchone()
    gateway_id = gw_row['gateway_id'] if gw_row else 'GW-GEN-01'

    # 4. Generate unique BLE tag credentials if not given
    if not tag_id:
        cursor.execute('SELECT COUNT(*) FROM assets')
        idx = cursor.fetchone()[0] + 1
        tag_id = f"TAG-BLE-{700 + idx}"
        tag_mac = f"AC:23:3F:8A:{70 + (idx // 100):02X}:{idx % 100:02X}"
    else:
        tag_mac = f"AC:23:3F:8A:71:{(abs(hash(tag_id)) % 80) + 10:02X}"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if existing and existing['is_deleted'] == 1:
        # Re-activate previously deleted ID with exact new details
        cursor.execute('''
            UPDATE assets
            SET name = ?, category = ?, model = ?, tag_id = ?, tag_mac = ?,
                assigned_room_id = ?, current_room_id = ?, current_gateway_id = ?,
                rssi = -62, distance_m = 1.4, battery = 100, status = ?, maintenance_status = 'Good',
                is_deleted = 0, last_updated = ?
            WHERE asset_id = ?
        ''', (name, category, model, tag_id, tag_mac, assigned_room_id, current_room_id,
              gateway_id, status, now, asset_id))
    else:
        cursor.execute('''
            INSERT INTO assets (
                asset_id, name, category, model, tag_id, tag_mac,
                assigned_room_id, current_room_id, current_gateway_id,
                rssi, distance_m, battery, status, maintenance_status, is_deleted, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, -62, 1.4, 100, ?, 'Good', 0, ?)
        ''', (asset_id, name, category, model, tag_id, tag_mac,
              assigned_room_id, current_room_id, gateway_id, status, now))

    # Record baseline location history
    cursor.execute('''
        INSERT INTO location_history (asset_id, previous_room_id, room_id, gateway_id, rssi, distance_m, timestamp)
        VALUES (?, NULL, ?, ?, -62, 1.4, ?)
    ''', (asset_id, current_room_id, gateway_id, now))

    conn.commit()
    conn.close()

    # Automatically log a notification
    add_notification(
        title="New Equipment Registered",
        description=f"New device '{name}' ({asset_id}) was registered to {room_name}.",
        category="NEW_EQUIPMENT",
        severity="INFO",
        asset_id=asset_id,
        room_id=current_room_id
    )

    created_asset = get_asset_by_id(asset_id)
    return True, f"Equipment '{name}' ({asset_id}) successfully registered.", created_asset


def delete_equipment(asset_id):
    """
    Requirement 3: Safely deletes equipment for Admin.
    Uses archival approach (is_deleted = 1) to preserve historical movement,
    requests, and maintenance records without foreign key corruption.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM assets WHERE asset_id = ? AND COALESCE(is_deleted, 0) = 0', (asset_id,))
    asset = cursor.fetchone()
    if not asset:
        conn.close()
        return False, f"Equipment '{asset_id}' not found."

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Mark any pending requests for this equipment as Cancelled
    cursor.execute("UPDATE equipment_requests SET status = 'Cancelled', admin_decision = 'Asset Decommissioned' WHERE asset_id = ? AND status = 'Pending'", (asset_id,))

    # Acknowledge any active alerts for this asset
    cursor.execute("UPDATE alerts SET acknowledged = 1 WHERE asset_id = ?", (asset_id,))

    # Soft delete / decommission
    cursor.execute('''
        UPDATE assets 
        SET is_deleted = 1, status = 'Decommissioned', last_updated = ?
        WHERE asset_id = ?
    ''', (now, asset_id))

    conn.commit()
    conn.close()

    # Add notification for audit log
    add_notification(
        title="Equipment Deleted",
        description=f"Equipment '{asset['name']}' ({asset_id}) was decommissioned by Administrator.",
        category="SYSTEM",
        severity="WARNING",
        asset_id=asset_id,
        room_id=asset['current_room_id']
    )

    return True, f"Equipment '{asset['name']}' ({asset_id}) successfully deleted."


def update_equipment(asset_id, name=None, category=None, model=None, assigned_room_id=None, status=None):
    """
    Admin edits equipment details (name, category, model, department, status).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM assets WHERE asset_id = ? AND COALESCE(is_deleted, 0) = 0', (asset_id,))
    asset = cursor.fetchone()
    if not asset:
        conn.close()
        return False, f"Equipment '{asset_id}' not found."

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_name = name.strip() if name else asset['name']
    new_cat = category.strip() if category else asset['category']
    new_model = model.strip() if model else asset['model']
    new_assigned = assigned_room_id.strip() if assigned_room_id else asset['assigned_room_id']
    new_status = status.strip() if status else asset['status']

    cursor.execute('''
        UPDATE assets
        SET name = ?, category = ?, model = ?, assigned_room_id = ?, status = ?, last_updated = ?
        WHERE asset_id = ?
    ''', (new_name, new_cat, new_model, new_assigned, new_status, now, asset_id))

    conn.commit()
    conn.close()
    return True, f"Equipment '{new_name}' ({asset_id}) details updated."


# =====================================================================
# Feature 3: Maintenance Management
# =====================================================================

def save_maintenance_record(asset_id, maintenance_status, last_service_date, due_date, description="", technician_name="BioMed Engineering", cost=0.0):
    """
    Saves a preventative or corrective maintenance record and updates asset maintenance_status.
    Handles repair workflow:
      - 'Under Maintenance' / 'Needs Repair': asset status becomes 'Maintenance'
      - 'Good': asset maintenance_status becomes 'Good', status becomes 'Available',
                clears active repair alerts, removes from overdue/needs repair list.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM assets WHERE asset_id = ? AND COALESCE(is_deleted, 0) = 0', (asset_id,))
    asset = cursor.fetchone()
    if not asset:
        conn.close()
        return False, f"Asset '{asset_id}' not found.", None
    asset = dict(asset)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO maintenance_records (
            asset_id, maintenance_status, last_service_date, due_date,
            technician_name, description, cost, recorded_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (asset_id, maintenance_status, last_service_date, due_date, technician_name or "BioMed Engineering", description or "", cost or 0.0, now))
    rec_id = cursor.lastrowid

    # Update asset operational status
    if maintenance_status == 'Good':
        new_operational_status = 'Available'
    elif maintenance_status in ('Under Maintenance', 'Needs Repair'):
        new_operational_status = 'Maintenance'
    else: # 'Due Soon'
        new_operational_status = asset['status'] if asset['status'] != 'Maintenance' else 'Available'

    cursor.execute('''
        UPDATE assets
        SET maintenance_status = ?, status = ?, last_updated = ?
        WHERE asset_id = ?
    ''', (maintenance_status, new_operational_status, now, asset_id))

    conn.commit()
    conn.close()

    # If marked Good (repaired / certified), clear previous repair/maintenance alerts for this asset
    if maintenance_status == 'Good':
        conn_alert = get_db_connection()
        c_alert = conn_alert.cursor()
        c_alert.execute('''
            UPDATE alerts 
            SET acknowledged = 1 
            WHERE asset_id = ? AND alert_type IN ('MAINTENANCE_STATUS', 'MAINTENANCE_DUE', 'NEEDS_REPAIR')
        ''', (asset_id,))
        conn_alert.commit()
        conn_alert.close()

        add_notification(
            title=f"Repair Completed: {asset['name']}",
            description=f"{asset['name']} ({asset_id}) was certified and returned to service with status 'Good'. Next inspection: {due_date}.",
            category="MAINTENANCE_DUE",
            severity="INFO",
            asset_id=asset_id,
            room_id=asset['current_room_id']
        )
    else:
        sev = 'WARNING' if maintenance_status != 'Needs Repair' else 'CRITICAL'
        cat = 'MAINTENANCE_DUE' if maintenance_status == 'Due Soon' else ('NEEDS_REPAIR' if maintenance_status == 'Needs Repair' else 'MAINTENANCE_DUE')
        add_notification(
            title=f"Maintenance Alert: {asset['name']}",
            description=f"{asset['name']} ({asset_id}) status changed to '{maintenance_status}'. Due: {due_date}. {description}",
            category=cat,
            severity=sev,
            asset_id=asset_id,
            room_id=asset['current_room_id']
        )
        add_alert(
            asset_id=asset_id,
            asset_name=asset['name'],
            alert_type='MAINTENANCE_STATUS',
            severity=sev,
            room_id=asset['current_room_id'],
            message=f"MAINTENANCE NOTICE: '{asset['name']}' marked '{maintenance_status}' (Due: {due_date})."
        )

    return True, f"Maintenance record saved for {asset['name']}.", rec_id


def get_all_maintenance_records(limit=100):
    """Returns maintenance history joined with asset and room information."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT mr.*, 
               COALESCE(a.name, mr.asset_id) as asset_name, 
               COALESCE(a.category, 'Medical Asset') as category, 
               COALESCE(a.model, 'Standard') as model, 
               COALESCE(r.name, 'Hospital') as current_room_name
        FROM maintenance_records mr
        LEFT JOIN assets a ON mr.asset_id = a.asset_id
        LEFT JOIN rooms r ON a.current_room_id = r.room_id
        ORDER BY mr.id DESC LIMIT ?
    ''', (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_maintenance_summary():
    """
    Returns aggregated maintenance KPIs and active overdue/attention items.
    Synchronized with current assets table: once marked 'Good', items are removed from overdue list.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM assets WHERE COALESCE(is_deleted, 0) = 0 AND maintenance_status = 'Good'")
    good_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM assets WHERE COALESCE(is_deleted, 0) = 0 AND maintenance_status = 'Due Soon'")
    due_soon_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM assets WHERE COALESCE(is_deleted, 0) = 0 AND maintenance_status = 'Under Maintenance'")
    under_maint_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM assets WHERE COALESCE(is_deleted, 0) = 0 AND maintenance_status = 'Needs Repair'")
    needs_repair_count = cursor.fetchone()[0]

    today_str = datetime.now().strftime("%Y-%m-%d")

    # Find active equipment needing attention (NOT 'Good')
    # Or equipment whose latest maintenance due_date is in the past
    cursor.execute('''
        SELECT a.asset_id, a.name as asset_name, a.category, a.model, a.maintenance_status,
               r.name as current_room_name,
               COALESCE(latest_mr.due_date, 'Overdue') as due_date,
               COALESCE(latest_mr.last_service_date, 'N/A') as last_service_date,
               COALESCE(latest_mr.description, 'Requires inspection') as description
        FROM assets a
        JOIN rooms r ON a.current_room_id = r.room_id
        LEFT JOIN (
            SELECT mr.*
            FROM maintenance_records mr
            INNER JOIN (
                SELECT asset_id, MAX(id) as max_id
                FROM maintenance_records
                GROUP BY asset_id
            ) m_max ON mr.id = m_max.max_id
        ) latest_mr ON a.asset_id = latest_mr.asset_id
        WHERE COALESCE(a.is_deleted, 0) = 0
          AND (a.maintenance_status IN ('Under Maintenance', 'Needs Repair', 'Due Soon')
               OR (a.maintenance_status != 'Good' AND latest_mr.due_date < ?))
        ORDER BY 
            CASE a.maintenance_status 
                WHEN 'Needs Repair' THEN 1 
                WHEN 'Under Maintenance' THEN 2 
                WHEN 'Due Soon' THEN 3 
                ELSE 4 
            END ASC
    ''', (today_str,))
    attention_items = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {
        'good': good_count,
        'due_soon': due_soon_count,
        'under_maintenance': under_maint_count,
        'needs_repair': needs_repair_count,
        'overdue_count': len(attention_items),
        'overdue_items': attention_items
    }


# =====================================================================
# Feature 4: Notifications and Alerts
# =====================================================================

def add_notification(title, description, category, severity, asset_id=None, room_id=None):
    """Adds a persistent notification entry."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO notifications (title, description, category, severity, asset_id, room_id, created_at, is_read)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
    ''', (title, description, category, severity, asset_id, room_id, now))
    conn.commit()
    conn.close()


def get_all_notifications(category=None, unread_only=False, limit=100):
    """Returns persistent notifications with optional category filtering."""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM notifications"
    conditions = []
    params = []
    if category and category.lower() != 'all':
        conditions.append("category = ?")
        params.append(category)
    if unread_only:
        conditions.append("is_read = 0")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    cursor.execute(query, tuple(params))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_unread_notification_count():
    """Returns count of unread notifications."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM notifications WHERE is_read = 0")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def mark_notification_as_read(notif_id):
    """Marks single notification as read."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_id,))
    conn.commit()
    conn.close()


def mark_all_notifications_as_read():
    """Marks all notifications as read."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1")
    conn.commit()
    conn.close()


# =====================================================================
# Feature 5: Reports and Analytics
# =====================================================================

def get_reports_analytics_data():
    """Aggregates comprehensive hospital analytics from actual database tables."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Total equipment
    cursor.execute('SELECT COUNT(*) FROM assets')
    total_equipment = cursor.fetchone()[0]

    # 2. Department-wise count (assigned_room_id)
    cursor.execute('''
        SELECT r.name, COUNT(a.asset_id) as count
        FROM rooms r
        LEFT JOIN assets a ON r.room_id = a.assigned_room_id
        GROUP BY r.room_id
        ORDER BY count DESC
    ''')
    dept_distribution = [dict(r) for r in cursor.fetchall()]

    # 3. Room-wise current physical distribution (current_room_id)
    cursor.execute('''
        SELECT r.name, r.color, COUNT(a.asset_id) as count
        FROM rooms r
        LEFT JOIN assets a ON r.room_id = a.current_room_id
        GROUP BY r.room_id
        ORDER BY count DESC
    ''')
    room_distribution = [dict(r) for r in cursor.fetchall()]

    # 4. Category breakdown
    cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM assets
        GROUP BY category
        ORDER BY count DESC
    ''')
    category_distribution = [dict(r) for r in cursor.fetchall()]

    # 5. Equipment request statistics
    cursor.execute('SELECT COUNT(*) FROM equipment_requests')
    total_requests = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM equipment_requests WHERE status = 'Pending'")
    pending_requests = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM equipment_requests WHERE status in ('Approved', 'Completed')")
    approved_requests = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM equipment_requests WHERE status = 'Rejected'")
    rejected_requests = cursor.fetchone()[0]

    # 6. Maintenance status breakdown
    cursor.execute('''
        SELECT maintenance_status, COUNT(*) as count
        FROM assets
        GROUP BY maintenance_status
    ''')
    maint_stats = {r['maintenance_status']: r['count'] for r in [dict(row) for row in cursor.fetchall()]}

    # 7. Most frequently moved equipment (top 5 from location_history)
    cursor.execute('''
        SELECT lh.asset_id, a.name, a.category, COUNT(*) as move_count
        FROM location_history lh
        JOIN assets a ON lh.asset_id = a.asset_id
        WHERE lh.previous_room_id IS NOT NULL
        GROUP BY lh.asset_id
        ORDER BY move_count DESC LIMIT 5
    ''')
    top_moved = [dict(r) for r in cursor.fetchall()]

    # 8. Total movements logged
    cursor.execute('SELECT COUNT(*) FROM location_history WHERE previous_room_id IS NOT NULL')
    total_movements = cursor.fetchone()[0]

    conn.close()
    return {
        'total_equipment': total_equipment,
        'total_movements': total_movements,
        'dept_distribution': dept_distribution,
        'room_distribution': room_distribution,
        'category_distribution': category_distribution,
        'requests': {
            'total': total_requests,
            'pending': pending_requests,
            'approved': approved_requests,
            'rejected': rejected_requests,
            'approval_rate': round((approved_requests / total_requests * 100), 1) if total_requests > 0 else 0
        },
        'maintenance': maint_stats,
        'top_moved': top_moved
    }


# =====================================================================
# Feature 6: User Login and Roles
# =====================================================================

def create_user(username, password, full_name, role='STAFF', department='General'):
    """Creates a user account with hashed password."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
    if cursor.fetchone():
        conn.close()
        return False, f"Username '{username}' already exists."

    pwd_hash = generate_password_hash(password)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO users (username, password_hash, full_name, role, department, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (username, pwd_hash, full_name, role.upper(), department, now))
    conn.commit()
    conn.close()
    return True, f"User '{username}' created successfully."


def verify_user_credentials(username, password):
    """Verifies username and password hash. Returns user dict without password hash."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    if not user:
        return None
    user_dict = dict(user)
    if check_password_hash(user_dict['password_hash'], password):
        user_dict.pop('password_hash', None)
        return user_dict
    return None


def get_user_by_username(username):
    """Fetches user details without password hash."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, full_name, role, department, created_at FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None


def get_all_users():
    """Returns list of all registered users without password hashes."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, full_name, role, department, created_at FROM users ORDER BY id ASC')
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def reset_database():
    """
    Resets temporary simulation and tracking state back to pristine baseline.
    CRITICAL: Does NOT delete registered equipment (existing or newly added by Admin).
    Restores equipment physical positions to assigned home rooms and resets baseline telemetry.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Reset physical positions of all registered assets back to their assigned home rooms
    cursor.execute('''
        UPDATE assets
        SET current_room_id = assigned_room_id,
            current_gateway_id = (SELECT gateway_id FROM gateways WHERE gateways.room_id = assets.assigned_room_id LIMIT 1),
            rssi = -62,
            distance_m = 1.4,
            battery = CASE WHEN battery < 20 THEN 94 ELSE battery END,
            last_updated = ?
        WHERE COALESCE(is_deleted, 0) = 0
    ''', (now,))

    # 2. Clear simulation breach & temporary alerts
    cursor.execute('DELETE FROM alerts')

    # 3. Clear temporary network telemetry logs
    cursor.execute('DELETE FROM network_logs')

    # 4. Clear temporary simulation equipment requests
    cursor.execute('DELETE FROM equipment_requests')

    # 5. Clear temporary location history and insert baseline location for all registered assets
    cursor.execute('DELETE FROM location_history')
    cursor.execute('''
        INSERT INTO location_history (asset_id, previous_room_id, room_id, gateway_id, rssi, distance_m, timestamp)
        SELECT asset_id, NULL, current_room_id, current_gateway_id, rssi, distance_m, last_updated
        FROM assets
        WHERE COALESCE(is_deleted, 0) = 0
    ''')

    # 6. Insert clean baseline network log
    cursor.execute('''
        INSERT INTO network_logs (timestamp, source_ip, dest_ip, protocol, port, vlan, topic, packet_summary, payload_json, status)
        VALUES (?, '10.20.1.10', '10.30.0.15', 'MQTT/TCP', 1883, 20, 'hospital/blockA/floor3/gw-icu-01',
              'SYSTEM RESET: Simulation environment restored to baseline. All registered equipment preserved.',
              '{"event":"SYSTEM_RESET","status":"MANUAL_MODE_ACTIVE"}', 'DELIVERED')
    ''', (now,))

    conn.commit()
    conn.close()
