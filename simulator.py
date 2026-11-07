"""
Simulation and Movement Controller for Smart Hospital Asset Tracking System.
STRICT MANUAL CONTROL MODE:
- Automatic and random movements are completely disabled.
- Equipment moves ONLY when explicitly requested via the manual move interface.
- Calculates BLE RSSI physics via the log-distance path loss model:
    d = 10^((TxPower - RSSI) / (10 * n))
- Transmits genuine MQTT telemetry frames on port 1883.
- Records previous and new locations in SQLite database.
- Evaluates geofencing boundaries.
"""

import math
import random
import logging
from datetime import datetime

import database
from mqtt_service import mqtt_manager

logger = logging.getLogger("MOVEMENT_ENGINE")

# Radio propagation parameters (Log-distance path loss)
TX_POWER_1M = -59         # Measured RSSI at 1 meter in dBm
PATH_LOSS_EXPONENT = 2.5  # n = 2.5 (Hospital indoor environment)


def rssi_to_distance(rssi, tx_power=TX_POWER_1M, n=PATH_LOSS_EXPONENT):
    """Calculates physical distance from RSSI using log-distance model."""
    try:
        ratio = (tx_power - rssi) / (10.0 * n)
        return round(math.pow(10, ratio), 2)
    except Exception:
        return 1.4


def distance_to_rssi(distance_m, tx_power=TX_POWER_1M, n=PATH_LOSS_EXPONENT, add_noise=True):
    """Calculates expected RSSI from distance with indoor multipath Gaussian noise."""
    if distance_m <= 0.1:
        distance_m = 0.1
    base_rssi = tx_power - (10.0 * n * math.log10(distance_m))
    if add_noise:
        noise = random.gauss(0, 1.0)
        base_rssi += noise
    return int(round(base_rssi))


class EquipmentMovementController:
    """
    Handles deterministic manual equipment relocation.
    Zero background timers or autonomous jumping.
    """
    def __init__(self):
        self.running = False  # Disabled by design: Manual mode is strict default
        self.gateway_map = {}
        self.room_gateways = {}
        self.room_map = {}
        self._load_metadata()

    def _load_metadata(self):
        """Caches gateway and room metadata from database."""
        gateways = database.get_all_gateways()
        self.gateway_map = {g['gateway_id']: g for g in gateways}
        self.room_gateways = {g['room_id']: g for g in gateways}

        rooms = database.get_all_rooms()
        self.room_map = {r['room_id']: r for r in rooms}

    def is_running(self):
        """Returns False because automatic movement is permanently disabled."""
        return False

    def start(self):
        """No-op: Automatic simulation is permanently disabled per user requirement."""
        logger.info("Automatic movement is disabled. Manual control is active.")

    def stop(self):
        """No-op: Already stopped."""
        self.running = False

    def process_location_update(self, asset_id, room_id, gateway_id, rssi, distance_m, battery=None):
        """Callback for location updates received via MQTT subscriber."""
        pass

    def manual_move_asset(self, asset_id, target_room_id, sync_assigned=False):
        """
        Explicitly moves a specific medical equipment to a destination ward.
        Updates location, calculates RSSI, emits MQTT packet, logs history,
        and evaluates geofencing.
        """
        self._load_metadata()
        asset = database.get_asset_by_id(asset_id)
        if not asset:
            return False, "Equipment not found in database", None

        previous_room_id = asset['current_room_id']
        previous_room_name = asset['current_room_name']

        target_room = self.room_map.get(target_room_id)
        if not target_room:
            return False, f"Target location '{target_room_id}' not recognized", None

        target_room_name = target_room['name']
        target_gw = self.room_gateways.get(target_room_id)
        if not target_gw:
            return False, f"No gateway configured for '{target_room_name}'", None

        # Calculate realistic RSSI and distance inside the destination ward
        dist = round(random.uniform(1.1, 1.9), 2)
        rssi = distance_to_rssi(dist)

        # 1. Publish MQTT telemetry packet from the target gateway
        mqtt_manager.publish_telemetry(
            gateway_id=target_gw['gateway_id'],
            gateway_ip=target_gw['ip_address'],
            tag_id=asset['tag_id'],
            asset_id=asset_id,
            rssi=rssi,
            battery=asset['battery'],
            room_id=target_room_id,
            distance_m=dist
        )

        # 2. Update database record with previous and new room IDs
        database.update_asset_telemetry(
            asset_id=asset_id,
            new_room_id=target_room_id,
            new_gateway_id=target_gw['gateway_id'],
            rssi=rssi,
            distance_m=dist,
            battery=asset['battery'],
            previous_room_id=previous_room_id,
            sync_assigned=sync_assigned
        )

        # 3. Evaluate Geofence Security Rules
        assigned_room_id = asset['assigned_room_id'] if not sync_assigned else target_room_id
        assigned_room_name = asset['assigned_room_name'] if not sync_assigned else target_room_name

        if asset['category'] == 'Ventilator' and target_room_id != assigned_room_id:
            database.add_alert(
                asset_id=asset_id,
                asset_name=asset['name'],
                alert_type='GEOFENCE_BREACH',
                severity='CRITICAL',
                room_id=target_room_id,
                message=f"GEOFENCE ALERT: Life-support equipment '{asset['name']}' assigned to {assigned_room_name} was relocated to {target_room_name}."
            )
        elif target_room_id == 'STORAGE' and asset['status'] == 'In Use':
            database.add_alert(
                asset_id=asset_id,
                asset_name=asset['name'],
                alert_type='GEOFENCE_BREACH',
                severity='WARNING',
                room_id=target_room_id,
                message=f"AUDIT WARNING: Active equipment '{asset['name']}' moved to Storage while marked 'In Use'."
            )

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        movement_record = {
            "asset_id": asset_id,
            "asset_name": asset['name'],
            "tag_id": asset['tag_id'],
            "previous_room_id": previous_room_id,
            "previous_room_name": previous_room_name,
            "new_room_id": target_room_id,
            "new_room_name": target_room_name,
            "gateway_id": target_gw['gateway_id'],
            "gateway_ip": target_gw['ip_address'],
            "rssi": rssi,
            "distance_m": dist,
            "timestamp": now_str
        }

        msg = f"Successfully moved '{asset['name']}' from {previous_room_name} to {target_room_name}."
        logger.info(msg)
        return True, msg, movement_record

    def reset_demo_state(self):
        """
        Resets all 12 assets, gateways, alerts, and movement logs to initial baseline state.
        Guarantees clean JSON response for reset button.
        """
        try:
            database.reset_database()
            self._load_metadata()
            # Send initial packet to revive live ticker & pipeline
            gw = self.room_gateways.get('ICU')
            if gw:
                mqtt_manager.publish_telemetry(
                    gateway_id=gw['gateway_id'],
                    gateway_ip=gw['ip_address'],
                    tag_id='TAG-BLE-701',
                    asset_id='AST-VENT-01',
                    rssi=-62,
                    battery=94,
                    room_id='ICU',
                    distance_m=1.3
                )
            logger.info("Demo state successfully reset to pristine baseline.")
            return True, "Demonstration environment reset to pristine baseline state. All 12 equipment positions restored."
        except Exception as e:
            logger.error(f"Error resetting demo state: {e}", exc_info=True)
            return False, f"Failed to reset demo state: {str(e)}"

    def trigger_icu_breach_demo(self):
        """
        Preset Scenario 1: ICU Ventilator Geofence Breach.
        Relocates Hamilton-C6 Ventilator (assigned to ICU) to Storage Depot.
        Triggers instant GEOFENCE_BREACH alarm & MQTT alert packet.
        """
        ok, msg, _ = self.manual_move_asset('AST-VENT-01', 'STORAGE')
        if ok:
            return True, "CRITICAL: Hamilton-C6 Ventilator breached ICU perimeter and moved to Storage Depot!"
        return False, msg

    def trigger_emergency_transfer_demo(self):
        """
        Preset Scenario 2: Emergency Trauma Transfer.
        Dispatches Zoll R-Series Defibrillator to Operation Theatre.
        """
        ok, msg, _ = self.manual_move_asset('AST-DEFIB-01', 'OT')
        if ok:
            return True, "URGENT DISPATCH: Zoll R Crash Defibrillator transferred to Operation Theatre for acute surgery."
        return False, msg

    def trigger_low_battery_demo(self):
        """
        Preset Scenario 3: Tag Battery Critical Drop.
        Simulates Philips Cardiograph battery dropping to 12% critical threshold.
        """
        try:
            self._load_metadata()
            asset_id = 'AST-ECG-02'
            asset = database.get_asset_by_id(asset_id)
            if not asset:
                return False, "Asset AST-ECG-02 not found"

            gw = self.room_gateways.get(asset['current_room_id'])
            gw_id = gw['gateway_id'] if gw else 'GW-GEN-01'
            gw_ip = gw['ip_address'] if gw else '10.20.1.13'

            # 1. Update DB with low battery
            database.update_asset_telemetry(
                asset_id=asset_id,
                new_room_id=asset['current_room_id'],
                new_gateway_id=gw_id,
                rssi=asset['rssi'],
                distance_m=asset['distance_m'],
                battery=12,
                previous_room_id=asset['current_room_id']
            )

            # 2. Add alert
            database.add_alert(
                asset_id=asset_id,
                asset_name=asset['name'],
                alert_type='LOW_BATTERY',
                severity='WARNING',
                room_id=asset['current_room_id'],
                message=f"LOW BATTERY: Tag '{asset['tag_id']}' battery dropped to 12% (threshold: 20%). Immediate recharge required."
            )

            # 3. Publish MQTT packet
            mqtt_manager.publish_telemetry(
                gateway_id=gw_id,
                gateway_ip=gw_ip,
                tag_id=asset['tag_id'],
                asset_id=asset_id,
                rssi=asset['rssi'],
                battery=12,
                room_id=asset['current_room_id'],
                distance_m=asset['distance_m']
            )
            return True, "Tag TAG-BLE-710 battery dropped to 12%. Low battery warning alert generated."
        except Exception as e:
            logger.error(f"Error in low battery scenario: {e}", exc_info=True)
            return False, f"Low battery scenario failed: {e}"

    def trigger_network_link_failover_demo(self):
        """
        Preset Scenario 4: Switch Link Failover & Gateway Buffer.
        Simulates 802.1Q trunk failover between Access and Distribution switches.
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            database.log_network_packet(
                source_ip='10.20.1.11',
                dest_ip='10.30.0.15',
                protocol='MQTT/TCP (Failover Path)',
                port=1883,
                vlan=20,
                topic='hospital/network/switch_failover',
                summary='RSTP 802.1w Link Failover: Primary uplink Gi0/1 down -> Standby trunk Gi0/2 forwarding',
                payload_dict={
                    "event": "LINK_FAILOVER",
                    "switch": "ACC-SW-FL3",
                    "old_port": "Gi0/1",
                    "new_port": "Gi0/2",
                    "convergence_ms": 14,
                    "buffered_packets_drained": 6
                },
                status='DELIVERED'
            )
            return True, "Network switch link failover simulated: RSTP convergence in 14ms. Gateway buffer flushed."
        except Exception as e:
            return False, f"Failover simulation failed: {e}"


# Global singleton instance
simulator = EquipmentMovementController()
