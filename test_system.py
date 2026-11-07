"""
Comprehensive Integration Test Suite for Smart Hospital Asset Tracking System.
Validates all routes, REST endpoints, database queries, manual equipment movements,
and movement history persistence.
"""

import sys
import json
import app
import database

def run_tests():
    print("=" * 70)
    print("STARTING SMART HOSPITAL RTLS SYSTEM TESTS (MANUAL MOVEMENT)")
    print("=" * 70)

    # Ensure clean baseline
    database.reset_database()

    client = app.app.test_client()
    passed = 0
    total = 0

    def assert_test(name, condition, extra=""):
        nonlocal passed, total
        total += 1
        if condition:
            passed += 1
            print(f"[PASS] {name} {extra}")
        else:
            print(f"[FAIL] {name} - FAILED! {extra}")
            sys.exit(1)

    # 1. Test HTML Pages
    print("\n--- 1. Testing HTML Web Pages ---")
    pages = [
        ('/', 'Dashboard Page', 'Floor 3 Hospital Layout'),
        ('/movement', 'Manage Equipment Movement Page', 'Manage Equipment Movement'),
        ('/network', 'Network Architecture Page', 'Three-Tier Hierarchical Network Topology'),
        ('/assets', 'Asset Inventory Page', 'Hospital Medical Asset Inventory')
    ]
    for url, label, expected_keyword in pages:
        res = client.get(url)
        assert_test(f"GET {url} ({label})", res.status_code == 200 and expected_keyword in res.get_data(as_text=True))

    # 2. Test REST API Endpoints
    print("\n--- 2. Testing REST API Endpoints ---")
    
    # State API
    res = client.get('/api/state')
    data = res.json
    assert_test("GET /api/state status 200", res.status_code == 200)
    assert_test("Total assets equals 12", len(data['assets']) == 12)
    assert_test("Total gateways equals 7", len(data['gateways']) == 7)
    assert_test("Total rooms equals 7", len(data['rooms']) == 7)
    assert_test("MQTT Status contains connected", data['mqtt_status']['connected'] is True)
    assert_test("Simulation is NOT running (Manual Mode)", data['simulation_running'] is False)

    # Subnet Calculator API
    res = client.get('/api/network/calc_subnet')
    sub = res.json
    assert_test("Subnet calculation API returns 10.20.0.0/22", sub['network_address'] == '10.20.0.0' and sub['cidr_prefix'] == '/22')
    assert_test("Subnet usable hosts is 1022", sub['usable_ip_addresses'] == 1022)
    assert_test("Subnet mask is 255.255.252.0", sub['subnet_mask'] == '255.255.252.0')

    # VLAN Firewall ACL Tester API
    res = client.post('/api/network/test_vlan', json={'src_vlan': 40, 'dst_vlan': 20, 'port': 1883})
    assert_test("Firewall ACL drops VLAN 40 to VLAN 20", res.json['action'] == 'DROP')

    res = client.post('/api/network/test_vlan', json={'src_vlan': 20, 'dst_vlan': 30, 'port': 1883})
    assert_test("Firewall ACL permits VLAN 20 to VLAN 30 on port 1883", res.json['action'] == 'PERMIT')

    # Single Asset API
    res = client.get('/api/asset/AST-VENT-01')
    assert_test("GET /api/asset/AST-VENT-01", res.status_code == 200 and res.json['category'] == 'Ventilator')

    # 3. Test Manual Equipment Movement & History Persistence
    print("\n--- 3. Testing Manual Equipment Movement & History ---")
    
    # Step A: Move Ventilator from ICU to Emergency Room
    res = client.post('/api/move', json={'asset_id': 'AST-VENT-01', 'room_id': 'ER'})
    assert_test("Move AST-VENT-01 to Emergency Room succeeds", res.status_code == 200 and res.json['status'] == 'success')
    
    # Verify in Database
    asset = database.get_asset_by_id('AST-VENT-01')
    assert_test("Asset current room is now Emergency Room", asset['current_room_id'] == 'ER')

    # Step B: Move Ventilator from Emergency Room to Cardiology
    res = client.post('/api/move', json={'asset_id': 'AST-VENT-01', 'room_id': 'CARDIO'})
    assert_test("Move AST-VENT-01 to Cardiology succeeds", res.status_code == 200 and res.json['status'] == 'success')
    
    # Step C: Move Wheelchair to Pharmacy
    res = client.post('/api/move', json={'asset_id': 'AST-WCHR-01', 'room_id': 'PHARM'})
    assert_test("Move AST-WCHR-01 to Pharmacy succeeds", res.status_code == 200 and res.json['status'] == 'success')

    # Step D: Move Defibrillator to Storage
    res = client.post('/api/move', json={'asset_id': 'AST-DEFIB-01', 'room_id': 'STORAGE'})
    assert_test("Move AST-DEFIB-01 to Storage succeeds", res.status_code == 200 and res.json['status'] == 'success')

    # Step E: Verify Movement History API
    res = client.get('/api/movement/history')
    assert_test("GET /api/movement/history status 200", res.status_code == 200)
    history = res.json
    assert_test("History has recorded movements", len(history) >= 4)
    latest = history[0]
    assert_test("Latest history item has previous and new room", 'previous_room_name' in latest and 'new_room_name' in latest)
    assert_test("Latest history record has timestamp", 'timestamp' in latest and len(latest['timestamp']) > 0)

    # 4. Test Reset & Demo Scenarios (Bug 1 & Bug 2 Verification)
    print("\n--- 4. Testing Reset Button & Demo Scenarios (Bug 1 & 2) ---")
    
    # Test POST /api/demo/reset
    res = client.post('/api/demo/reset')
    assert_test("POST /api/demo/reset returns 200 JSON", res.status_code == 200 and res.is_json and res.json.get('status') == 'success')
    
    # Test POST /api/reset direct route
    res = client.post('/api/reset')
    assert_test("POST /api/reset returns 200 JSON", res.status_code == 200 and res.is_json and res.json.get('status') == 'success')
    
    # Verify baseline restored
    vent = database.get_asset_by_id('AST-VENT-01')
    assert_test("After Reset: AST-VENT-01 is back in ICU", vent['current_room_id'] == 'ICU' and vent['current_room_name'] == 'ICU')
    assert_test("Asset record has location aliases", vent.get('current_location') == 'ICU' and vent.get('location') == 'ICU')

    # Test Move AST-VENT-01 to Emergency Room and verify synchronization
    res = client.post('/api/move', json={'asset_id': 'AST-VENT-01', 'room_id': 'ER'})
    assert_test("Move Ventilator to ER returns 200", res.status_code == 200 and res.json.get('status') == 'success')
    vent_after_move = database.get_asset_by_id('AST-VENT-01')
    assert_test("Synchronized physical location is ER", vent_after_move['current_room_id'] == 'ER' and vent_after_move['current_room_name'] == 'Emergency Room')
    assert_test("Aliases reflect ER", vent_after_move['current_location'] == 'Emergency Room' and vent_after_move['location'] == 'Emergency Room')
    assert_test("Assigned ward remains ICU base", vent_after_move['assigned_room_id'] == 'ICU')

    # Test Demo Scenarios
    scenarios = ['icu_breach', 'emergency_transfer', 'low_battery', 'link_failover']
    for sc in scenarios:
        res = client.post(f'/api/demo/{sc}')
        assert_test(f"POST /api/demo/{sc} returns 200 JSON", res.status_code == 200 and res.is_json and res.json.get('status') == 'success')

    # Test Invalid Action returns JSON 400 (NOT HTML)
    res = client.post('/api/demo/invalid_scenario')
    assert_test("Invalid scenario returns 400 JSON (No HTML)", res.status_code == 400 and res.is_json and res.json.get('status') == 'error')

    # Reset back to pristine baseline
    res = client.post('/api/reset')
    assert_test("Final reset back to pristine baseline", res.status_code == 200)

    # 5. Test Equipment Request Management (NEW FEATURE)
    print("\n--- 5. Testing Equipment Request Management ---")

    # 5.1 Test Page Access
    res = client.get('/requests')
    assert_test("GET /requests (Equipment Requests Page)", res.status_code == 200 and 'Equipment Request Management' in res.get_data(as_text=True))

    # Step A: Setup Ventilator AST-VENT-01 in Pharmacy
    res = client.post('/api/move', json={'asset_id': 'AST-VENT-01', 'room_id': 'PHARM'})
    assert_test("Setup: Ventilator moved to Pharmacy", res.status_code == 200)
    vent_pharm = database.get_asset_by_id('AST-VENT-01')
    assert_test("Ventilator is currently in Pharmacy", vent_pharm['current_room_id'] == 'PHARM')

    # Step A.2: Submit request from ICU for Ventilator currently in Pharmacy
    res = client.post('/api/requests', json={
        'asset_id': 'AST-VENT-01',
        'requesting_room_id': 'ICU',
        'destination_room_id': 'ICU',
        'quantity': 1,
        'reason': 'Urgent ICU respiratory distress patient transfer'
    })
    assert_test("Submit request from ICU for Ventilator succeeds", res.status_code == 201 and res.json['status'] == 'success')
    req1 = res.json['request']
    req1_id = req1['id']
    assert_test("Request recorded from Pharmacy to ICU", req1['current_room_id_at_request'] == 'PHARM' and req1['destination_room_id'] == 'ICU')

    # Step B: Verify Admin Notification & Pending Count
    res = client.get('/api/requests/pending_count')
    assert_test("Pending requests count is at least 1", res.json['count'] >= 1)
    
    # Verify Alert was created in database
    alerts = database.get_active_alerts(limit=10)
    has_alert = any(a['alert_type'] == 'EQUIPMENT_REQUEST' for a in alerts)
    assert_test("Admin alert generated for new request", has_alert)

    # Step C: Accept / Approve Request
    res = client.post(f'/api/requests/{req1_id}/approve')
    assert_test(f"Approve Request #{req1_id} succeeds", res.status_code == 200 and res.json['status'] == 'success')

    # Step D: Verify Ventilator Location Changed from Pharmacy to ICU Everywhere
    vent_icu = database.get_asset_by_id('AST-VENT-01')
    assert_test("Ventilator physical location is now ICU", vent_icu['current_room_id'] == 'ICU' and vent_icu['current_room_name'] == 'ICU')
    assert_test("Ventilator location alias is ICU", vent_icu['location'] == 'ICU' and vent_icu['current_location'] == 'ICU')

    # Verify in History Log
    history = database.get_movement_history(limit=5)
    latest_move = history[0]
    assert_test("Movement history records transfer to ICU", latest_move['asset_id'] == 'AST-VENT-01' and latest_move['new_room_id'] == 'ICU')

    # Step E: Verify Requester Sees Accepted / Approved Status
    res = client.get('/api/requests')
    reqs_after_approve = res.json
    approved_req = next((r for r in reqs_after_approve if r['id'] == req1_id), None)
    assert_test("Requester sees Approved status", approved_req is not None and approved_req['status'] == 'Approved')

    # Step F: Submit Another Request & Reject It
    # Request Philips Defibrillator AST-DEFIB-02 (currently in OT) for General Ward
    defib_ot = database.get_asset_by_id('AST-DEFIB-02')
    original_defib_room = defib_ot['current_room_id']

    res = client.post('/api/requests', json={
        'asset_id': 'AST-DEFIB-02',
        'requesting_room_id': 'GEN',
        'destination_room_id': 'GEN',
        'quantity': 1,
        'reason': 'Ward backup resuscitation unit request'
    })
    assert_test("Submit second request for Defibrillator succeeds", res.status_code == 201)
    req2_id = res.json['request']['id']

    # Reject with specific reason
    rejection_msg = "Currently allocated to OT surgical schedule"
    res = client.post(f'/api/requests/{req2_id}/reject', json={
        'rejection_reason': rejection_msg
    })
    assert_test(f"Reject Request #{req2_id} succeeds", res.status_code == 200 and res.json['status'] == 'success')

    # Step G: Verify Equipment Location Did NOT Change After Rejection
    defib_after_reject = database.get_asset_by_id('AST-DEFIB-02')
    assert_test("Defibrillator location unchanged after rejection", defib_after_reject['current_room_id'] == original_defib_room)

    # Verify Rejection Status and Reason saved
    rejected_req = database.get_equipment_request_by_id(req2_id)
    assert_test("Status is Rejected", rejected_req['status'] == 'Rejected' and rejected_req['rejection_reason'] == rejection_msg)

    # Step H: Test Validations
    # Validation 1: Cannot request equipment already in room
    res = client.post('/api/requests', json={
        'asset_id': 'AST-VENT-01',
        'requesting_room_id': 'ICU',
        'destination_room_id': 'ICU'
    })
    assert_test("Validation: Cannot request equipment already in room", res.status_code == 400 and 'already physically located' in res.json['error'])

    # Validation 2: Cannot create duplicate pending request
    # Create valid request for ECG machine
    res = client.post('/api/requests', json={
        'asset_id': 'AST-ECG-01',
        'requesting_room_id': 'ER',
        'destination_room_id': 'ER'
    })
    assert_test("Create valid request for ECG machine", res.status_code == 201)
    
    # Try creating duplicate pending request
    res_dup = client.post('/api/requests', json={
        'asset_id': 'AST-ECG-01',
        'requesting_room_id': 'ER',
        'destination_room_id': 'ER'
    })
    assert_test("Validation: Duplicate pending request blocked", res_dup.status_code == 400 and 'already awaiting' in res_dup.json['error'])

    # Clean up and reset back to baseline
    res = client.post('/api/reset')
    assert_test("Reset clears all requests back to pristine baseline", res.status_code == 200)
    assert_test("Pending count is 0 after reset", database.get_pending_requests_count() == 0)

    # 6. Test CSV Export
    print("\n--- 6. Testing CSV Export ---")
    res = client.get('/api/export/csv')
    assert_test("GET /api/export/csv status 200", res.status_code == 200)
    assert_test("CSV contains header", 'Asset ID,Name,Category' in res.get_data(as_text=True))

    # 7. Testing 6 NEW FEATURES
    print("\n--- 7. Testing 6 NEW FEATURES ---")

    # FEATURE 1: Add New Equipment
    print("  -> Testing Feature 1: Add New Equipment")
    res = client.get('/equipment/add')
    assert_test("GET /equipment/add status 200", res.status_code == 200 and 'Register New Hospital Equipment' in res.get_data(as_text=True))

    # Add a new Ultrasound device
    res = client.post('/api/equipment', json={
        'asset_id': 'AST-ULTRA-01',
        'name': 'Mindray Resona Ultrasound',
        'category': 'Ultrasound',
        'assigned_room_id': 'CARDIO',
        'current_room_id': 'CARDIO',
        'model': 'Resona 7 Pro',
        'quantity': 1,
        'status': 'Available'
    })
    assert_test("POST /api/equipment creates new device", res.status_code == 201 and res.json['status'] == 'success')
    new_asset = database.get_asset_by_id('AST-ULTRA-01')
    assert_test("New asset persisted in database", new_asset is not None and new_asset['name'] == 'Mindray Resona Ultrasound')
    assert_test("New asset has BLE Tag ID and MAC", new_asset['tag_id'].startswith('TAG-BLE-') and len(new_asset['tag_mac']) == 17)

    # Prevent duplicate equipment ID
    res_dup = client.post('/api/equipment', json={
        'asset_id': 'AST-ULTRA-01',
        'name': 'Duplicate Ultrasound',
        'category': 'Ultrasound',
        'assigned_room_id': 'ICU'
    })
    assert_test("Prevent duplicate equipment ID", res_dup.status_code == 400 and 'already exists' in res_dup.json['error'])

    # FEATURE 2: Hospital Floor Map
    print("  -> Testing Feature 2: Hospital Floor Map")
    res = client.get('/map')
    assert_test("GET /map status 200", res.status_code == 200 and 'Hospital Floor Map' in res.get_data(as_text=True))
    assert_test("Map contains ICU and Emergency Room", 'ICU' in res.get_data(as_text=True) and 'Emergency Room' in res.get_data(as_text=True))

    # FEATURE 3: Maintenance Management
    print("  -> Testing Feature 3: Maintenance Management")
    res = client.get('/maintenance')
    assert_test("GET /maintenance status 200", res.status_code == 200 and 'Hospital Equipment Maintenance Management' in res.get_data(as_text=True))

    res = client.get('/api/maintenance')
    assert_test("GET /api/maintenance status 200", res.status_code == 200 and 'records' in res.json and 'summary' in res.json)

    # Save a maintenance record
    res = client.post('/api/maintenance', json={
        'asset_id': 'AST-ULTRA-01',
        'maintenance_status': 'Good',
        'last_service_date': '2026-11-01',
        'due_date': '2027-02-01',
        'description': 'Initial acceptance safety testing & transducer check',
        'technician_name': 'BioMed Engineering',
        'cost': 150.0
    })
    assert_test("POST /api/maintenance saves record", res.status_code == 201 and res.json['status'] == 'success')

    # FEATURE 4: Notifications & Alerts
    print("  -> Testing Feature 4: Notifications & Alerts")
    res = client.get('/notifications')
    assert_test("GET /notifications status 200", res.status_code == 200 and 'Notifications & Alerts Center' in res.get_data(as_text=True))

    res = client.get('/api/notifications')
    assert_test("GET /api/notifications returns list", res.status_code == 200 and isinstance(res.json, list) and len(res.json) > 0)

    res_unread = client.get('/api/notifications/unread_count')
    assert_test("GET /api/notifications/unread_count status 200", res_unread.status_code == 200 and 'count' in res_unread.json)

    # Mark single notification as read
    first_notif_id = res.json[0]['id']
    res_mark = client.post(f'/api/notifications/{first_notif_id}/read')
    assert_test(f"POST /api/notifications/{first_notif_id}/read succeeds", res_mark.status_code == 200 and res_mark.json['status'] == 'success')

    # Mark all notifications as read
    res_all_read = client.post('/api/notifications/mark_all_read')
    assert_test("POST /api/notifications/mark_all_read succeeds", res_all_read.status_code == 200 and res_all_read.json['unread_count'] == 0)

    # FEATURE 5: Reports & Analytics
    print("  -> Testing Feature 5: Reports & Analytics")
    res = client.get('/reports')
    assert_test("GET /reports status 200", res.status_code == 200 and 'Hospital Asset Tracking Intelligence' in res.get_data(as_text=True))

    res = client.get('/api/reports/summary')
    assert_test("GET /api/reports/summary returns intelligence data", res.status_code == 200 and 'total_equipment' in res.json and 'dept_distribution' in res.json)

    # Test all 4 CSV exports
    for exp_type in ['inventory', 'movements', 'requests', 'maintenance']:
        res_csv = client.get(f'/api/reports/export/{exp_type}')
        assert_test(f"Export CSV ({exp_type}) status 200", res_csv.status_code == 200 and 'text/csv' in res_csv.headers.get('Content-Type', ''))

    # FEATURE 6: User Login & Role Management
    print("  -> Testing Feature 6: User Login & Roles")
    res = client.get('/login')
    assert_test("GET /login status 200", res.status_code == 200 and 'Hospital Information System Authentication' in res.get_data(as_text=True))

    # Authenticate valid admin credentials
    res = client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
    assert_test("Login with admin/admin123 succeeds", res.status_code == 200 and res.json['status'] == 'success' and res.json['user']['role'] == 'ADMIN')

    # Reject invalid password
    res_bad = client.post('/api/auth/login', json={'username': 'admin', 'password': 'wrongpassword'})
    assert_test("Reject wrong password with 401", res_bad.status_code == 401)

    # 6. TESTING THE 5 NEW REQUIREMENTS SPECIFICALLY
    print("\n--- 6. Testing The 5 Strict Corrections & Requirements ---")

    # REQUIREMENT 1: Role-Based Permissions (Admin, Doctor, Staff)
    print("  -> Testing Requirement 1: Role-Based Permissions")

    # Switch to Doctor
    res = client.post('/api/auth/switch_role', json={'role': 'DOCTOR'})
    assert_test("Switch role to DOCTOR", res.status_code == 200 and res.json['user']['role'] == 'DOCTOR')

    # Doctor can view equipment and locations
    res_assets = client.get('/api/assets')
    assert_test("Doctor CAN view all equipment", res_assets.status_code == 200 and len(res_assets.json) > 0)

    # Doctor CAN submit equipment request
    res_doc_req = client.post('/api/requests', json={
        'asset_id': 'AST-VENT-02',
        'requesting_room_id': 'ICU',
        'destination_room_id': 'ICU',
        'reason': 'Emergency ventilator requisition by Doctor'
    })
    # If it is already in ICU, pick another destination or check error
    test_asset = database.get_asset_by_id('AST-VENT-02')
    target_room = 'ICU' if test_asset['current_room_id'] != 'ICU' else 'ER'
    res_doc_req = client.post('/api/requests', json={
        'asset_id': 'AST-VENT-02',
        'requesting_room_id': target_room,
        'destination_room_id': target_room,
        'reason': 'Emergency requisition by Doctor'
    })
    assert_test("Doctor CAN submit equipment request", res_doc_req.status_code == 201)
    doc_req_id = res_doc_req.json['request']['id']

    # Doctor CANNOT move equipment (HTTP 403 Forbidden)
    res_doc_move = client.post('/api/move', json={'asset_id': 'AST-VENT-02', 'room_id': 'STORAGE'})
    assert_test("Doctor CANNOT move equipment (403)", res_doc_move.status_code == 403 and 'Access Denied' in res_doc_move.json.get('error', ''))

    # Doctor CANNOT add equipment (HTTP 403 Forbidden)
    res_doc_add = client.post('/api/equipment', json={'asset_id': 'AST-UNAUTH-01', 'name': 'Unauthorized Device'})
    assert_test("Doctor CANNOT add equipment (403)", res_doc_add.status_code == 403 and 'Access Denied' in res_doc_add.json.get('error', ''))

    # Doctor CANNOT delete equipment (HTTP 403 Forbidden)
    res_doc_del = client.delete('/api/equipment/AST-VENT-02')
    assert_test("Doctor CANNOT delete equipment (403)", res_doc_del.status_code == 403 and 'Access Denied' in res_doc_del.json.get('error', ''))

    # Doctor CANNOT edit equipment (HTTP 403 Forbidden)
    res_doc_edit = client.post('/api/equipment/AST-VENT-02/edit', json={'name': 'Hacked Ventilator'})
    assert_test("Doctor CANNOT edit equipment (403)", res_doc_edit.status_code == 403 and 'Access Denied' in res_doc_edit.json.get('error', ''))

    # Doctor CANNOT accept equipment request (HTTP 403 Forbidden)
    res_doc_appr = client.post(f'/api/requests/{doc_req_id}/approve')
    assert_test("Doctor CANNOT approve request (403)", res_doc_appr.status_code == 403 and 'Access Denied' in res_doc_appr.json.get('error', ''))

    # Doctor CANNOT reject equipment request (HTTP 403 Forbidden)
    res_doc_rej = client.post(f'/api/requests/{doc_req_id}/reject', json={'rejection_reason': 'Doctor attempt'})
    assert_test("Doctor CANNOT reject request (403)", res_doc_rej.status_code == 403 and 'Access Denied' in res_doc_rej.json.get('error', ''))

    # Doctor CANNOT save maintenance records (HTTP 403 Forbidden)
    res_doc_maint = client.post('/api/maintenance', json={'asset_id': 'AST-VENT-02', 'maintenance_status': 'Good'})
    assert_test("Doctor CANNOT perform maintenance (403)", res_doc_maint.status_code == 403 and 'Access Denied' in res_doc_maint.json.get('error', ''))

    # Switch to Staff
    res = client.post('/api/auth/switch_role', json={'role': 'STAFF'})
    assert_test("Switch role to STAFF", res.status_code == 200 and res.json['user']['role'] == 'STAFF')

    # Staff CANNOT move equipment (HTTP 403 Forbidden)
    res_staff_move = client.post('/api/move', json={'asset_id': 'AST-VENT-02', 'room_id': 'STORAGE'})
    assert_test("Staff CANNOT move equipment (403)", res_staff_move.status_code == 403)

    # Staff CANNOT delete equipment (HTTP 403 Forbidden)
    res_staff_del = client.delete('/api/equipment/AST-VENT-02')
    assert_test("Staff CANNOT delete equipment (403)", res_staff_del.status_code == 403)

    # Switch back to Admin
    res = client.post('/api/auth/switch_role', json={'role': 'ADMIN'})
    assert_test("Switch back to ADMIN role", res.status_code == 200 and res.json['user']['role'] == 'ADMIN')

    # Admin CAN approve the pending request
    res_admin_appr = client.post(f'/api/requests/{doc_req_id}/approve')
    assert_test("Admin CAN approve equipment request (200)", res_admin_appr.status_code == 200 and res_admin_appr.json['status'] == 'success')

    # REQUIREMENT 2: Fix Add New Equipment & Persistence after Reset
    print("  -> Testing Requirement 2: Exact Name Saving & Persistence After Reset")
    custom_eq_name = "Mindray Resona 7 Ultrasound System"
    custom_eq_id = "AST-CUSTOM-99"

    res_add_custom = client.post('/api/equipment', json={
        'asset_id': custom_eq_id,
        'name': custom_eq_name,
        'category': 'Ultrasound',
        'assigned_room_id': 'CARDIO',
        'current_room_id': 'CARDIO',
        'model': 'Resona 7 Premium',
        'quantity': 1,
        'status': 'Available'
    })
    assert_test("Admin adds equipment with exact name", res_add_custom.status_code == 201)
    
    # Verify exact name in database
    db_custom_asset = database.get_asset_by_id(custom_eq_id)
    assert_test("Exact name saved in database", db_custom_asset['name'] == custom_eq_name)
    assert_test("Correct ID, category, department stored", db_custom_asset['category'] == 'Ultrasound' and db_custom_asset['assigned_room_id'] == 'CARDIO')

    # Trigger System Reset (Requirement 2 Persistence check)
    res_reset = client.post('/api/reset')
    assert_test("POST /api/reset succeeds", res_reset.status_code == 200)

    # Verify custom equipment was NOT deleted by Reset!
    after_reset_asset = database.get_asset_by_id(custom_eq_id)
    assert_test("Custom equipment PERSISTS after Reset (not deleted)", after_reset_asset is not None)
    assert_test("Custom equipment retains exact name after Reset", after_reset_asset['name'] == custom_eq_name)
    assert_test("Custom equipment in all assets list after Reset", any(a['asset_id'] == custom_eq_id for a in database.get_all_assets()))

    # REQUIREMENT 3: Add Delete Equipment Option (Admin Only)
    print("  -> Testing Requirement 3: Delete Equipment Option (Admin Only)")
    # Delete the custom equipment
    res_del_custom = client.delete(f'/api/equipment/{custom_eq_id}')
    assert_test("Admin can delete equipment", res_del_custom.status_code == 200 and res_del_custom.json['status'] == 'success')

    # Verify equipment removed from active list
    assert_test("Deleted equipment removed from active fleet", not any(a['asset_id'] == custom_eq_id for a in database.get_all_assets()))
    assert_test("get_asset_by_id returns None for active lookup", database.get_asset_by_id(custom_eq_id) is None)

    # Other equipment must NOT be deleted
    assert_test("Other equipment remain intact (AST-VENT-01 exists)", database.get_asset_by_id('AST-VENT-01') is not None)

    # REQUIREMENT 4 & 5: Fix Maintenance Status After Repair & Improve Maintenance Management
    print("  -> Testing Requirement 4 & 5: Maintenance Workflow & Repair Completion")
    
    # AST-XRAY-01 initial status is 'Needs Repair'
    xray = database.get_asset_by_id('AST-XRAY-01')
    initial_room = xray['current_room_id']

    # Step 1: Send for repair -> Under Maintenance
    res_maint_step1 = client.post('/api/maintenance', json={
        'asset_id': 'AST-XRAY-01',
        'maintenance_status': 'Under Maintenance',
        'last_service_date': '2026-11-04',
        'due_date': '2026-11-15',
        'technician_name': 'BioMed Engineering',
        'description': 'Equipment sent for collimator motor overhaul',
        'cost': 450.0
    })
    assert_test("Send for repair: status becomes 'Under Maintenance'", res_maint_step1.status_code == 201)
    
    xray_step1 = database.get_asset_by_id('AST-XRAY-01')
    assert_test("Database records 'Under Maintenance'", xray_step1['maintenance_status'] == 'Under Maintenance')
    assert_test("Physical location unchanged during repair", xray_step1['current_room_id'] == initial_room)

    # Step 2: Mark repair completed -> Good
    res_maint_step2 = client.post('/api/maintenance', json={
        'asset_id': 'AST-XRAY-01',
        'maintenance_status': 'Good',
        'last_service_date': '2026-11-04',
        'due_date': '2027-02-04',
        'technician_name': 'BioMed Engineering',
        'description': 'Collimator motor overhauled, calibrated, and passed safety tests',
        'cost': 450.0
    })
    assert_test("Mark repaired: status updated to 'Good'", res_maint_step2.status_code == 201)

    xray_step2 = database.get_asset_by_id('AST-XRAY-01')
    assert_test("Asset maintenance_status is now 'Good'", xray_step2['maintenance_status'] == 'Good')
    assert_test("Asset operational status is now 'Available'", xray_step2['status'] == 'Available')
    assert_test("Physical location remains strictly unchanged", xray_step2['current_room_id'] == initial_room)

    # Verify removed from overdue / attention list
    maint_summary = database.get_maintenance_summary()
    assert_test("Asset removed from overdue/needs repair list", not any(item['asset_id'] == 'AST-XRAY-01' for item in maint_summary['overdue_items']))

    # Verify record saved in maintenance history
    records = database.get_all_maintenance_records(limit=20)
    assert_test("Repair record exists in maintenance history", any(r['asset_id'] == 'AST-XRAY-01' and r['maintenance_status'] == 'Good' for r in records))

    # Clean reset
    res = client.post('/api/reset')
    assert_test("Final reset back to pristine baseline", res.status_code == 200)

    # Stop services cleanly
    app.mqtt_manager.stop()

    print("\n" + "=" * 70)
    print(f"ALL TESTS PASSED: {passed}/{total} (100% SUCCESS)")
    print("=" * 70)

if __name__ == '__main__':
    run_tests()
