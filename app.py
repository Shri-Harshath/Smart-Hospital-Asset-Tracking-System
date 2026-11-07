"""
Flask Application for Smart Hospital Asset Tracking System.
Real-Time Location Tracking Using IoT and Computer Networks.
SRM Institute of Science and Technology - Dept. of Computational Intelligence.
"""

import os
import json
import time
import logging
from datetime import datetime
from flask import Flask, render_template, jsonify, request, Response, make_response, session, redirect, url_for

import database
from mqtt_service import mqtt_manager, register_packet_listener
from simulator import simulator, TX_POWER_1M, PATH_LOSS_EXPONENT

logger = logging.getLogger("RTLS_APP")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'srm-hospital-rtls-secret-key-2026'

# Ensure database is initialized
database.init_db()

@app.context_processor
def inject_current_user():
    """Provides user session and notification badges across all templates."""
    user = session.get('user')
    if not user:
        user = {
            'username': 'admin',
            'full_name': 'Administrator',
            'role': 'ADMIN',
            'department': 'Hospital Administration'
        }
    unread_count = 0
    try:
        unread_count = database.get_unread_notification_count()
    except Exception:
        pass
    return dict(current_user=user, unread_notifications_count=unread_count)

def get_active_user():
    """Returns currently authenticated user from session or default Admin."""
    user = session.get('user')
    if not user:
        user = {
            'username': 'admin',
            'full_name': 'Administrator',
            'role': 'ADMIN',
            'department': 'Hospital Administration'
        }
    return user

def check_admin_permission():
    """
    Enforces Role-Based Permissions (Requirement 1):
    Only Admin can move equipment, add/delete/edit equipment,
    approve/reject requests, and manage maintenance records.
    Returns (True, None, None) or (False, error_response, 403).
    """
    user = get_active_user()
    if user.get('role') != 'ADMIN':
        return False, jsonify({
            'status': 'error',
            'error': f"Access Denied: Only Administrator has permission to perform this operation. Your current role is {user.get('role')}."
        }), 403
    return True, None, None

# Wire MQTT message handler to simulator location engine
def on_mqtt_message_received(topic, payload):
    """Callback when a valid MQTT message arrives at the broker."""
    try:
        asset_id = payload.get('asset_id')
        room_id = payload.get('room_id')
        gw_id = payload.get('gw_id')
        rssi = payload.get('rssi', -65)
        dist = payload.get('distance_m', 1.5)
        battery = payload.get('battery')
        if asset_id and room_id and gw_id:
            simulator.process_location_update(asset_id, room_id, gw_id, rssi, dist, battery)
    except Exception as e:
        print(f"Error handling incoming MQTT telemetry: {e}")

mqtt_manager.set_message_handler(on_mqtt_message_received)

# Initialize MQTT subsystem
mqtt_mode = mqtt_manager.initialize()

# Manual Control Mode: Automatic and random equipment movement is disabled by design.
print("[*] Movement Mode : MANUAL CONTROL (Automatic movements disabled)")


# =====================================================================
# HTML Page Routes
# =====================================================================

@app.route('/')
def index():
    """Live Hospital Dashboard: SVG floor plan, live asset tracking, packet flow."""
    return render_template('dashboard.html', active_page='dashboard')


@app.route('/movement')
def movement_page():
    """Manage Equipment Movement: Manual control & relocation history."""
    return render_template('movement.html', active_page='movement')


@app.route('/network')
def network_page():
    """Dedicated Computer Networks Architecture Page."""
    return render_template('network.html', active_page='network')


@app.route('/assets')
def assets_page():
    """Asset Inventory, Maintenance Management, and Battery Health."""
    return render_template('assets.html', active_page='assets')


@app.route('/requests')
def requests_page():
    """Equipment Request Management: Department Requests & Admin Approval."""
    rooms = database.get_all_rooms()
    assets = database.get_all_assets()
    stats = database.get_dashboard_stats()
    return render_template('requests.html', 
                           active_page='requests',
                           rooms=rooms,
                           assets=assets,
                           stats=stats)


@app.route('/equipment/add')
def add_equipment_page():
    """Feature 1: Add New Equipment registration page."""
    rooms = database.get_all_rooms()
    return render_template('add_equipment.html', active_page='add_equipment', rooms=rooms)


@app.route('/map')
def map_page():
    """Feature 2: Hospital Floor Map dedicated positioning & room inspection page."""
    rooms = database.get_all_rooms()
    gateways = database.get_all_gateways()
    return render_template('map.html', active_page='map', rooms=rooms, gateways=gateways)


@app.route('/maintenance')
def maintenance_page():
    """Feature 3: Maintenance Management preventative & corrective service scheduler."""
    assets = database.get_all_assets()
    rooms = database.get_all_rooms()
    return render_template('maintenance.html', active_page='maintenance', assets=assets, rooms=rooms)


@app.route('/notifications')
def notifications_page():
    """Feature 4: Centralized Notifications and Alerts Center."""
    return render_template('notifications.html', active_page='notifications')


@app.route('/reports')
def reports_page():
    """Feature 5: Reports and Analytics intelligence dashboard & data export."""
    return render_template('reports.html', active_page='reports')


@app.route('/login')
def login_page():
    """Feature 6: User Login & Role-Based Access Control page."""
    return render_template('login.html', active_page='login')


@app.route('/logout')
def logout_page():
    """Feature 6: Logout route to clear session and return to login."""
    session.pop('user', None)
    return redirect(url_for('login_page'))


# =====================================================================
# REST API Endpoints
# =====================================================================

@app.route('/api/state')
def get_state():
    """Returns complete real-time snapshot for the live dashboard."""
    assets = database.get_all_assets()
    gateways = database.get_all_gateways()
    rooms = database.get_all_rooms()
    alerts = database.get_active_alerts(limit=25)
    stats = database.get_dashboard_stats()
    mqtt_status = mqtt_manager.get_status()
    recent_packets = mqtt_manager.get_recent_packets(limit=15)
    pending_requests_count = database.get_pending_requests_count()

    return jsonify({
        'assets': assets,
        'gateways': gateways,
        'rooms': rooms,
        'alerts': alerts,
        'stats': stats,
        'simulation_running': simulator.is_running(),
        'mqtt_status': mqtt_status,
        'recent_packets': recent_packets,
        'pending_requests_count': pending_requests_count,
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route('/api/assets')
def get_assets():
    """Returns all assets with optional filtering."""
    category = request.args.get('category')
    room = request.args.get('room')
    status = request.args.get('status')
    
    assets = database.get_all_assets()
    if category:
        assets = [a for a in assets if a['category'].lower() == category.lower()]
    if room:
        assets = [a for a in assets if a['current_room_id'] == room]
    if status:
        assets = [a for a in assets if a['status'].lower() == status.lower()]
        
    return jsonify(assets)


@app.route('/api/asset/<asset_id>')
def get_asset_detail(asset_id):
    """Returns detailed asset profile and recent movement history."""
    asset = database.get_asset_by_id(asset_id)
    if not asset:
        return jsonify({'error': 'Asset not found'}), 404
    return jsonify(asset)


@app.route('/api/move', methods=['POST'])
def move_asset():
    """Manually move an asset between rooms (Explicit User Control - Admin Only)."""
    is_admin, err_resp, code = check_admin_permission()
    if not is_admin:
        return err_resp, code

    try:
        data = request.get_json(silent=True) or {}
        asset_id = data.get('asset_id')
        room_id = data.get('room_id')
        sync_assigned = bool(data.get('sync_assigned', False))

        if not asset_id or not room_id:
            return jsonify({'status': 'error', 'error': 'asset_id and room_id are required'}), 400

        success, message, movement = simulator.manual_move_asset(asset_id, room_id, sync_assigned=sync_assigned)
        if success:
            return jsonify({
                'status': 'success', 
                'message': message, 
                'movement': movement
            })
        return jsonify({'status': 'error', 'error': message}), 400
    except Exception as e:
        logger.error(f"Error moving asset: {e}", exc_info=True)
        return jsonify({'status': 'error', 'error': f'Server error moving asset: {str(e)}'}), 500


@app.route('/api/movement/history')
def get_movement_history():
    """Returns equipment relocation history with previous and new locations."""
    limit = int(request.args.get('limit', 50))
    history = database.get_movement_history(limit=limit)
    return jsonify(history)


@app.route('/api/simulation/toggle', methods=['POST'])
def toggle_simulation():
    """Manual mode enforcement."""
    return jsonify({
        'status': 'success',
        'simulation_running': False,
        'message': 'Manual Control Mode is enforced. Automatic random movement is disabled.'
    })


@app.route('/api/reset', methods=['POST', 'GET'])
def reset_system():
    """
    Direct reset endpoint for restoring initial baseline state (Admin Only).
    Always returns strict JSON (never HTML).
    """
    is_admin, err_resp, code = check_admin_permission()
    if not is_admin:
        return err_resp, code

    try:
        ok, msg = simulator.reset_demo_state()
        return jsonify({
            'status': 'success' if ok else 'error',
            'message': msg
        }), 200 if ok else 500
    except Exception as e:
        logger.error(f"Error during system reset: {e}", exc_info=True)
        return jsonify({'status': 'error', 'error': f'Failed to reset system: {str(e)}'}), 500


@app.route('/api/demo/<action>', methods=['POST'])
def trigger_demo_action(action):
    """Preset classroom demonstration actions (Admin Only). Always returns JSON."""
    is_admin, err_resp, code = check_admin_permission()
    if not is_admin:
        return err_resp, code

    try:
        if action == 'icu_breach':
            ok, msg = simulator.trigger_icu_breach_demo()
        elif action == 'emergency_transfer':
            ok, msg = simulator.trigger_emergency_transfer_demo()
        elif action == 'low_battery':
            ok, msg = simulator.trigger_low_battery_demo()
        elif action == 'link_failover':
            ok, msg = simulator.trigger_network_link_failover_demo()
        elif action == 'reset':
            ok, msg = simulator.reset_demo_state()
        else:
            return jsonify({'status': 'error', 'error': f"Unknown demo action: {action}"}), 400

        return jsonify({'status': 'success' if ok else 'error', 'message': msg}), 200 if ok else 500
    except Exception as e:
        logger.error(f"Error executing demo action {action}: {e}", exc_info=True)
        return jsonify({'status': 'error', 'error': f'Internal error executing {action}: {str(e)}'}), 500


@app.route('/api/alerts/acknowledge/<int:alert_id>', methods=['POST'])
def ack_alert(alert_id):
    """Acknowledge an active alert."""
    database.acknowledge_alert(alert_id)
    return jsonify({'status': 'success', 'message': f'Alert {alert_id} acknowledged'})


@app.route('/api/alerts/clear', methods=['POST'])
def clear_alerts():
    """Clear acknowledged alerts."""
    database.clear_all_alerts()
    return jsonify({'status': 'success', 'message': 'Acknowledged alerts cleared'})


# =====================================================================
# Equipment Request Management Endpoints
# =====================================================================

@app.route('/api/requests', methods=['GET'])
def get_requests():
    """Returns equipment requests with optional status and room filtering."""
    status = request.args.get('status')
    room = request.args.get('room')
    limit = int(request.args.get('limit', 100))
    requests_list = database.get_all_equipment_requests(status=status, room=room, limit=limit)
    return jsonify(requests_list)


@app.route('/api/requests/pending_count', methods=['GET'])
def get_pending_requests_count_api():
    """Returns pending requests count for dynamic notification badge polling."""
    count = database.get_pending_requests_count()
    return jsonify({'count': count})


@app.route('/api/requests', methods=['POST'])
def create_request():
    """
    Submits a new equipment transfer request from a hospital department.
    Validates asset, ensures it's not already in target room, and prevents duplicate pending requests.
    """
    try:
        data = request.get_json(silent=True) or {}
        asset_id = data.get('asset_id')
        requesting_room_id = data.get('requesting_room_id')
        destination_room_id = data.get('destination_room_id') or requesting_room_id
        quantity = int(data.get('quantity', 1))
        reason = data.get('reason', '').strip()

        if not asset_id or not requesting_room_id:
            return jsonify({'status': 'error', 'error': 'Both Equipment and Requesting Department are required.'}), 400

        ok, msg, req_id = database.create_equipment_request(
            asset_id=asset_id,
            requesting_room_id=requesting_room_id,
            destination_room_id=destination_room_id,
            quantity=quantity,
            reason=reason
        )

        if ok:
            created_req = database.get_equipment_request_by_id(req_id)
            return jsonify({
                'status': 'success',
                'message': msg,
                'request': created_req,
                'pending_count': database.get_pending_requests_count()
            }), 201

        return jsonify({'status': 'error', 'error': msg}), 400
    except Exception as e:
        logger.error(f"Error creating equipment request: {e}", exc_info=True)
        return jsonify({'status': 'error', 'error': f"Failed to submit request: {str(e)}"}), 500


@app.route('/api/requests/<int:request_id>/approve', methods=['POST'])
def approve_request(request_id):
    """
    Administrator approves an equipment request:
    - Verifies current equipment position
    - Executes movement to the requested destination room via simulator.manual_move_asset
    - Updates SQLite assets table, emits MQTT telemetry packet, logs movement history
    - Marks request status as Approved
    """
    is_admin, err_resp, code = check_admin_permission()
    if not is_admin:
        return err_resp, code

    try:
        req = database.get_equipment_request_by_id(request_id)
        if not req:
            return jsonify({'status': 'error', 'error': f'Request #{request_id} not found.'}), 404

        if req['status'] != 'Pending':
            return jsonify({'status': 'error', 'error': f"Request #{request_id} has already been {req['status'].lower()}."}), 400

        asset = database.get_asset_by_id(req['asset_id'])
        if not asset:
            return jsonify({'status': 'error', 'error': f"Asset {req['asset_id']} not found in database."}), 404

        data = request.get_json(silent=True) or {}
        force = bool(data.get('force', False))

        # Check if equipment moved since request creation
        if not force and asset['current_room_id'] != req['current_room_id_at_request']:
            if asset['current_room_id'] == req['destination_room_id']:
                database.update_equipment_request(request_id, status='Completed', admin_decision='Approved')
                return jsonify({
                    'status': 'success',
                    'message': f"Request #{request_id} approved: '{asset['name']}' is already in {req['destination_room_name']}.",
                    'already_there': True,
                    'pending_count': database.get_pending_requests_count()
                })
            else:
                return jsonify({
                    'status': 'warning',
                    'needs_confirmation': True,
                    'message': f"Notice: '{asset['name']}' has moved to {asset['current_room_name']} since this request was created (was in {req['current_room_name_at_request']}). Confirm transfer to {req['destination_room_name']}?",
                    'current_location': asset['current_room_name']
                })

        # Relocate equipment via central movement engine
        ok, move_msg, movement = simulator.manual_move_asset(req['asset_id'], req['destination_room_id'])
        if not ok:
            return jsonify({'status': 'error', 'error': f"Transfer failed: {move_msg}"}), 500

        # Mark request as Approved
        database.update_equipment_request(request_id, status='Approved', admin_decision='Approved')

        # Add alert for requesting department
        database.add_alert(
            asset_id=req['asset_id'],
            asset_name=asset['name'],
            alert_type='REQUEST_APPROVED',
            severity='INFO',
            room_id=req['destination_room_id'],
            message=f"REQUEST APPROVED: Admin approved transfer of '{asset['name']}' to {req['destination_room_name']} for {req['requesting_room_name']}."
        )

        return jsonify({
            'status': 'success',
            'message': f"Request #{request_id} approved. '{asset['name']}' successfully transferred to {req['destination_room_name']}.",
            'movement': movement,
            'pending_count': database.get_pending_requests_count()
        })
    except Exception as e:
        logger.error(f"Error approving request {request_id}: {e}", exc_info=True)
        return jsonify({'status': 'error', 'error': f"Error approving request: {str(e)}"}), 500


@app.route('/api/requests/<int:request_id>/reject', methods=['POST'])
def reject_request(request_id):
    """
    Administrator rejects an equipment request:
    - Does NOT change the equipment location
    - Records admin decision and optional rejection reason
    - Marks request status as Rejected
    """
    is_admin, err_resp, code = check_admin_permission()
    if not is_admin:
        return err_resp, code

    try:
        req = database.get_equipment_request_by_id(request_id)
        if not req:
            return jsonify({'status': 'error', 'error': f'Request #{request_id} not found.'}), 404

        if req['status'] != 'Pending':
            return jsonify({'status': 'error', 'error': f"Request #{request_id} has already been {req['status'].lower()}."}), 400

        data = request.get_json(silent=True) or {}
        rejection_reason = data.get('rejection_reason', '').strip()

        database.update_equipment_request(
            request_id=request_id,
            status='Rejected',
            admin_decision='Rejected',
            rejection_reason=rejection_reason
        )

        reason_text = f" Reason: {rejection_reason}" if rejection_reason else ""
        database.add_alert(
            asset_id=req['asset_id'],
            asset_name=req['asset_name'],
            alert_type='REQUEST_REJECTED',
            severity='WARNING',
            room_id=req['requesting_room_id'],
            message=f"REQUEST REJECTED: Admin declined transfer of '{req['asset_name']}' to {req['destination_room_name']}.{reason_text}"
        )

        return jsonify({
            'status': 'success',
            'message': f"Request #{request_id} rejected.{reason_text}",
            'pending_count': database.get_pending_requests_count()
        })
    except Exception as e:
        logger.error(f"Error rejecting request {request_id}: {e}", exc_info=True)
        return jsonify({'status': 'error', 'error': f"Error rejecting request: {str(e)}"}), 500


@app.route('/api/network/packets')
def get_network_packets():
    """Returns recent network packets for wire inspection."""
    limit = int(request.args.get('limit', 30))
    packets = mqtt_manager.get_recent_packets(limit=limit)
    return jsonify(packets)


@app.route('/api/network/calc_subnet')
def calc_subnet():
    """
    Returns Computer Networks subnetting calculations for IoT VLAN 20.
    Subnet: 10.20.0.0/22
    """
    return jsonify({
        'vlan_id': 20,
        'vlan_name': 'IoT & Medical RTLS Devices',
        'network_address': '10.20.0.0',
        'cidr_prefix': '/22',
        'subnet_mask': '255.255.252.0',
        'wildcard_mask': '0.0.3.255',
        'binary_mask': '11111111.11111111.11111100.00000000',
        'total_ip_addresses': 1024,
        'usable_ip_addresses': 1022,
        'first_usable_ip': '10.20.0.1 (Default Gateway / Core Switch)',
        'last_usable_ip': '10.20.3.254',
        'broadcast_address': '10.20.3.255',
        'dhcp_gateway_pool': '10.20.1.1 - 10.20.1.100 (Static DHCP Reservations for BLE Gateways)',
        'dhcp_tag_pool': '10.20.2.1 - 10.20.3.254 (Dynamic IP pool for future Wi-Fi / UWB tags)'
    })


@app.route('/api/network/test_vlan', methods=['POST'])
def test_vlan():
    """
    Interactive VLAN Firewall ACL Packet Routing Simulator.
    Tests whether traffic is allowed or blocked between VLANs.
    """
    data = request.get_json(silent=True) or {}
    src_vlan = int(data.get('src_vlan', 40))
    dst_vlan = int(data.get('dst_vlan', 20))
    port = int(data.get('port', 1883))

    # ACL Rules Table
    # VLAN 10: Clinical, VLAN 20: IoT, VLAN 30: Servers, VLAN 40: Guest
    if src_vlan == 40 and dst_vlan in [10, 20, 30]:
        action = 'DROP'
        reason = f'Firewall ACL Rule 104 [DENY]: Guest Wi-Fi (VLAN 40) is isolated from internal Hospital VLAN {dst_vlan}. Internet access only.'
        rule_id = 'ACL-GUEST-ISOLATE'
    elif src_vlan == 20 and dst_vlan == 30 and port in [1883, 8883]:
        action = 'PERMIT'
        reason = f'Firewall ACL Rule 201 [PERMIT]: IoT Gateways (VLAN 20) allowed MQTT/TLS communication to Location Server/Broker (VLAN 30) on port {port}.'
        rule_id = 'ACL-IOT-BROKER-PERMIT'
    elif src_vlan == 20 and dst_vlan == 10:
        action = 'DROP'
        reason = f'Firewall ACL Rule 208 [DENY]: Direct lateral connection between IoT devices (VLAN 20) and Clinical Workstations (VLAN 10) prohibited for patient safety.'
        rule_id = 'ACL-IOT-CLINICAL-DROP'
    elif src_vlan == 30 and dst_vlan in [10, 20]:
        action = 'PERMIT'
        reason = f'Firewall ACL Rule 301 [PERMIT]: Management and Server VLAN 30 has administrative access to VLAN {dst_vlan}.'
        rule_id = 'ACL-MGMT-ALL-PERMIT'
    elif src_vlan == 10 and dst_vlan == 30 and port in [80, 443, 5000]:
        action = 'PERMIT'
        reason = f'Firewall ACL Rule 102 [PERMIT]: Clinical Workstations (VLAN 10) permitted HTTPS/REST access to Hospital Dashboard on port {port}.'
        rule_id = 'ACL-CLINICAL-WEB-PERMIT'
    else:
        action = 'DROP'
        reason = f'Default Implicit Deny: Inter-VLAN traffic from VLAN {src_vlan} to VLAN {dst_vlan} on port {port} is dropped.'
        rule_id = 'ACL-DEFAULT-IMPLICIT-DENY'

    return jsonify({
        'src_vlan': src_vlan,
        'dst_vlan': dst_vlan,
        'port': port,
        'action': action,
        'rule_id': rule_id,
        'reason': reason
    })


@app.route('/api/stream')
def stream():
    """Server-Sent Events (SSE) endpoint for real-time live packet streaming."""
    def event_stream():
        import queue
        q = queue.Queue(maxsize=30)
        
        def on_packet(pkt):
            try:
                q.put_nowait(pkt)
            except Exception:
                pass

        register_packet_listener(on_packet)

        # Send initial ping
        yield f"data: {json.dumps({'type': 'INIT', 'message': 'Connected to live packet stream'})}\n\n"

        while True:
            try:
                packet = q.get(timeout=2.0)
                yield f"data: {json.dumps({'type': 'PACKET', 'packet': packet})}\n\n"
            except queue.Empty:
                # Keep-alive heartbeat
                yield f": keep-alive\n\n"

    return Response(event_stream(), mimetype="text/event-stream")


# =====================================================================
# Feature 1: Add New Equipment API
# =====================================================================

@app.route('/api/equipment', methods=['POST'])
def add_equipment_api():
    """
    Feature 1: Add New Equipment (Admin Only).
    Registers a new asset into SQLite, sets up BLE tag and gateway,
    and updates live dashboard / requests list.
    """
    is_admin, err_resp, code = check_admin_permission()
    if not is_admin:
        return err_resp, code

    try:
        data = request.get_json(silent=True) or {}
        asset_id = (data.get('asset_id') or '').strip().upper()
        name = (data.get('name') or '').strip()
        category = (data.get('category') or 'Medical Device').strip()
        assigned_room_id = (data.get('assigned_room_id') or 'GEN').strip()
        current_room_id = (data.get('current_room_id') or assigned_room_id).strip()
        model = (data.get('model') or f"{name} Std").strip()
        quantity = int(data.get('quantity', 1))
        status = data.get('status', 'Available')

        if not asset_id or not name:
            return jsonify({'status': 'error', 'error': 'Both Equipment ID and Name are required.'}), 400

        ok, msg, created_asset = database.add_equipment(
            asset_id=asset_id,
            name=name,
            category=category,
            assigned_room_id=assigned_room_id,
            current_room_id=current_room_id,
            model=model,
            quantity=quantity,
            status=status
        )

        if ok:
            return jsonify({
                'status': 'success',
                'message': msg,
                'asset': created_asset
            }), 201
        return jsonify({'status': 'error', 'error': msg}), 400
    except Exception as e:
        logger.error(f"Error adding equipment: {e}", exc_info=True)
        return jsonify({'status': 'error', 'error': f"Failed to register equipment: {str(e)}"}), 500


@app.route('/api/equipment/<asset_id>', methods=['DELETE'])
@app.route('/api/equipment/<asset_id>/delete', methods=['POST', 'DELETE'])
def delete_equipment_api(asset_id):
    """
    Requirement 3: Safely deletes equipment from active fleet (Admin Only).
    """
    is_admin, err_resp, code = check_admin_permission()
    if not is_admin:
        return err_resp, code

    try:
        ok, msg = database.delete_equipment(asset_id)
        if ok:
            return jsonify({'status': 'success', 'message': msg}), 200
        return jsonify({'status': 'error', 'error': msg}), 400
    except Exception as e:
        logger.error(f"Error deleting equipment {asset_id}: {e}", exc_info=True)
        return jsonify({'status': 'error', 'error': f"Failed to delete equipment: {str(e)}"}), 500


@app.route('/api/equipment/<asset_id>/edit', methods=['POST', 'PUT'])
def edit_equipment_api(asset_id):
    """
    Requirement 1: Edit equipment details (Admin Only).
    """
    is_admin, err_resp, code = check_admin_permission()
    if not is_admin:
        return err_resp, code

    try:
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        category = (data.get('category') or '').strip()
        model = (data.get('model') or '').strip()
        assigned_room_id = (data.get('assigned_room_id') or '').strip()
        status = (data.get('status') or '').strip()

        ok, msg = database.update_equipment(
            asset_id=asset_id,
            name=name if name else None,
            category=category if category else None,
            model=model if model else None,
            assigned_room_id=assigned_room_id if assigned_room_id else None,
            status=status if status else None
        )
        if ok:
            return jsonify({'status': 'success', 'message': msg}), 200
        return jsonify({'status': 'error', 'error': msg}), 400
    except Exception as e:
        logger.error(f"Error updating equipment {asset_id}: {e}", exc_info=True)
        return jsonify({'status': 'error', 'error': f"Failed to update equipment: {str(e)}"}), 500


# =====================================================================
# Feature 3: Maintenance Management API
# =====================================================================

@app.route('/api/maintenance', methods=['GET', 'POST'])
def maintenance_api():
    """
    Feature 3: Maintenance Records & Scheduler API.
    GET: Returns maintenance history log and aggregated summary KPIs.
    POST: Saves a new preventative or corrective maintenance record (Admin Only).
    """
    if request.method == 'GET':
        records = database.get_all_maintenance_records(limit=100)
        summary = database.get_maintenance_summary()
        return jsonify({'records': records, 'summary': summary})

    # POST: Save maintenance record (Admin Only)
    is_admin, err_resp, code = check_admin_permission()
    if not is_admin:
        return err_resp, code

    try:
        data = request.get_json(silent=True) or {}
        asset_id = (data.get('asset_id') or '').strip()
        maintenance_status = data.get('maintenance_status', 'Good')
        last_service_date = data.get('last_service_date', datetime.now().strftime("%Y-%m-%d"))
        due_date = data.get('due_date', datetime.now().strftime("%Y-%m-%d"))
        technician_name = data.get('technician_name', 'BioMed Engineering')
        description = data.get('description', '').strip()
        cost = float(data.get('cost', 0.0) or 0.0)

        if not asset_id:
            return jsonify({'status': 'error', 'error': 'Equipment selection is required.'}), 400

        ok, msg, rec_id = database.save_maintenance_record(
            asset_id=asset_id,
            maintenance_status=maintenance_status,
            last_service_date=last_service_date,
            due_date=due_date,
            description=description,
            technician_name=technician_name,
            cost=cost
        )

        if ok:
            return jsonify({'status': 'success', 'message': msg, 'record_id': rec_id}), 201
        return jsonify({'status': 'error', 'error': msg}), 400
    except Exception as e:
        logger.error(f"Error saving maintenance record: {e}", exc_info=True)
        return jsonify({'status': 'error', 'error': f"Failed to save maintenance record: {str(e)}"}), 500


# =====================================================================
# Feature 4: Centralized Notifications & Alerts API
# =====================================================================

@app.route('/api/notifications', methods=['GET'])
def get_notifications_api():
    """Feature 4: Returns list of persistent notifications with category and unread filters."""
    category = request.args.get('category')
    unread_only = request.args.get('unread') == 'true'
    limit = int(request.args.get('limit', 100))
    notifs = database.get_all_notifications(category=category, unread_only=unread_only, limit=limit)
    return jsonify(notifs)


@app.route('/api/notifications/unread_count', methods=['GET'])
def get_unread_notif_count_api():
    """Feature 4: Returns current count of unread notifications for badge."""
    count = database.get_unread_notification_count()
    return jsonify({'count': count})


@app.route('/api/notifications/<int:notif_id>/read', methods=['POST'])
def mark_notif_read_api(notif_id):
    """Feature 4: Marks a single notification as read."""
    database.mark_notification_as_read(notif_id)
    return jsonify({'status': 'success', 'message': f'Notification {notif_id} marked as read', 'unread_count': database.get_unread_notification_count()})


@app.route('/api/notifications/mark_all_read', methods=['POST'])
def mark_all_notifs_read_api():
    """Feature 4: Marks all notifications as read."""
    database.mark_all_notifications_as_read()
    return jsonify({'status': 'success', 'message': 'All notifications marked as read', 'unread_count': 0})


# =====================================================================
# Feature 5: Reports and Analytics API & CSV Exports
# =====================================================================

@app.route('/api/reports/summary', methods=['GET'])
def reports_summary_api():
    """Feature 5: Aggregated hospital intelligence summary from actual database."""
    summary = database.get_reports_analytics_data()
    return jsonify(summary)


@app.route('/api/reports/export/<export_type>', methods=['GET'])
def export_reports_csv(export_type):
    """
    Feature 5: Generates downloadable CSV exports for inventory, movements, requests, and maintenance.
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    if export_type == 'inventory':
        assets = database.get_all_assets()
        output = "Asset ID,Name,Category,Model,Tag ID,Tag MAC,Assigned Ward,Current Ward,Current Gateway,RSSI (dBm),Distance (m),Battery (%),Status,Maintenance Status,Last Seen\n"
        for a in assets:
            output += f'"{a["asset_id"]}","{a["name"]}","{a["category"]}","{a["model"]}","{a["tag_id"]}","{a["tag_mac"]}","{a["assigned_room_name"]}","{a["current_room_name"]}","{a["current_gateway_id"]}",{a["rssi"]},{a["distance_m"]},{a["battery"]},"{a["status"]}","{a["maintenance_status"]}","{a["last_updated"]}"\n'
        filename = f"hospital_inventory_{timestamp}.csv"

    elif export_type == 'movements':
        history = database.get_movement_history(limit=500)
        output = "ID,Asset ID,Asset Name,Category,Previous Room,New Room,Gateway,RSSI (dBm),Distance (m),Timestamp\n"
        for h in history:
            output += f'{h["id"]},"{h["asset_id"]}","{h.get("asset_name","")}","{h.get("category","")}","{h.get("previous_room_name","Initial Base")}","{h.get("new_room_name","")}","{h.get("gateway_name","Gateway")}",{h.get("rssi", -65)},{h.get("distance_m", 1.5)},"{h.get("timestamp","")}"\n'
        filename = f"equipment_movements_{timestamp}.csv"

    elif export_type == 'requests':
        requests_list = database.get_all_equipment_requests(limit=500)
        output = "Request ID,Asset ID,Asset Name,Category,Requesting Department,Origin Location,Destination Location,Quantity,Status,Admin Decision,Rejection Reason,Created At,Decision At\n"
        for r in requests_list:
            output += f'{r["id"]},"{r["asset_id"]}","{r["asset_name"]}","{r["category"]}","{r["requesting_room_name"]}","{r["current_room_name_at_request"]}","{r["destination_room_name"]}",{r["quantity"]},"{r["status"]}","{r["admin_decision"]}","{r.get("rejection_reason","")}","{r["created_at"]}","{r.get("decision_at","")}"\n'
        filename = f"equipment_requests_{timestamp}.csv"

    elif export_type == 'maintenance':
        records = database.get_all_maintenance_records(limit=500)
        output = "Record ID,Asset ID,Asset Name,Category,Model,Location,Maintenance Status,Last Service Date,Due Date,Technician,Cost ($),Description,Recorded At\n"
        for m in records:
            output += f'{m["id"]},"{m["asset_id"]}","{m["asset_name"]}","{m["category"]}","{m["model"]}","{m["current_room_name"]}","{m["maintenance_status"]}","{m["last_service_date"]}","{m["due_date"]}","{m["technician_name"]}",{m["cost"]},"{m.get("description","")}","{m["recorded_at"]}"\n'
        filename = f"maintenance_records_{timestamp}.csv"

    else:
        return jsonify({'status': 'error', 'error': f"Unknown export type: {export_type}"}), 400

    response = make_response(output)
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    return response


# =====================================================================
# Feature 6: User Authentication & Role Management API
# =====================================================================

@app.route('/api/auth/login', methods=['POST'])
def auth_login_api():
    """Feature 6: User Authentication endpoint verifying username and password hash."""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'status': 'error', 'error': 'Username and password are required.'}), 400

    user = database.verify_user_credentials(username, password)
    if not user:
        return jsonify({'status': 'error', 'error': 'Invalid username or password.'}), 401

    session['user'] = user
    return jsonify({'status': 'success', 'message': f'Welcome back, {user["full_name"]}!', 'user': user})


@app.route('/api/auth/logout', methods=['POST'])
def auth_logout_api():
    """Feature 6: Clears session user."""
    session.pop('user', None)
    return jsonify({'status': 'success', 'message': 'Logged out successfully.'})


@app.route('/api/auth/current_user', methods=['GET'])
def auth_current_user_api():
    """Feature 6: Returns currently authenticated user."""
    user = session.get('user')
    if not user:
        user = {
            'username': 'admin',
            'full_name': 'Administrator',
            'role': 'ADMIN',
            'department': 'Hospital Administration'
        }
    return jsonify({'user': user})


@app.route('/api/auth/switch_role', methods=['POST'])
def auth_switch_role_api():
    """Feature 6: Fast role switch for classroom live demonstration."""
    data = request.get_json(silent=True) or {}
    role = (data.get('role') or 'ADMIN').upper()
    role_map = {
        'ADMIN': ('admin', 'Administrator', 'Hospital Administration'),
        'DOCTOR': ('dr_sharma', 'Dr. A. Sharma (MD)', 'ICU / Critical Care'),
        'STAFF': ('nurse_priya', 'Nurse Priya Patel (RN)', 'General Ward & Inpatient')
    }
    if role not in role_map:
        return jsonify({'status': 'error', 'error': f'Unsupported role: {role}'}), 400

    uname, fname, dept = role_map[role]
    user_record = database.get_user_by_username(uname) or {
        'id': 1, 'username': uname, 'full_name': fname, 'role': role, 'department': dept
    }
    session['user'] = user_record
    return jsonify({'status': 'success', 'message': f'Active role switched to {role}', 'user': user_record})


@app.route('/api/export/csv')
def export_csv():
    """Generates downloadable CSV report of hospital asset inventory."""
    assets = database.get_all_assets()
    output = "Asset ID,Name,Category,Model,Tag ID,Tag MAC,Assigned Ward,Current Ward,Current Gateway,RSSI (dBm),Distance (m),Battery (%),Status,Maintenance Status,Last Seen\n"
    for a in assets:
        output += f'"{a["asset_id"]}","{a["name"]}","{a["category"]}","{a["model"]}","{a["tag_id"]}","{a["tag_mac"]}","{a["assigned_room_name"]}","{a["current_room_name"]}","{a["current_gateway_id"]}",{a["rssi"]},{a["distance_m"]},{a["battery"]},"{a["status"]}","{a["maintenance_status"]}","{a["last_updated"]}"\n'

    response = make_response(output)
    response.headers["Content-Disposition"] = f"attachment; filename=hospital_assets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response.headers["Content-Type"] = "text/csv"
    return response


@app.errorhandler(500)
def handle_500(e):
    """Guarantees API routes always return JSON even on unhandled exceptions."""
    if request.path.startswith('/api/'):
        return jsonify({'status': 'error', 'error': f'Internal Server Error: {str(e)}'}), 500
    return "<h1>500 Internal Server Error</h1>", 500


@app.errorhandler(404)
def handle_404(e):
    """Guarantees API routes always return JSON for missing endpoints."""
    if request.path.startswith('/api/'):
        return jsonify({'status': 'error', 'error': 'Endpoint not found'}), 404
    return "<h1>404 Not Found</h1>", 404


if __name__ == '__main__':
    print("=" * 70)
    print("SMART HOSPITAL ASSET TRACKING SYSTEM (RTLS)")
    print("Real-Time Location Tracking Using IoT and Computer Networks")
    print("=" * 70)
    print(f"[*] Web Server URL : http://127.0.0.1:5000")
    print(f"[*] Network Page   : http://127.0.0.1:5000/network")
    print(f"[*] Assets Page    : http://127.0.0.1:5000/assets")
    print(f"[*] MQTT Broker    : {mqtt_mode}")
    print(f"[*] Simulation     : Running (4s cycle)")
    print("=" * 70)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

