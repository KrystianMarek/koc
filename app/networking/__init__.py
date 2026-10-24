"""
Networking module - All packet classes and network utilities.

This module provides:
- Packet base class and all packet types
- Network interface utilities
"""
import logging
import netifaces

from .packets import (
    # Base
    Packet,
    # Heartbeat (connection handshake)
    HeartbeatPacket,
    HeartbeatRequest,
    HeartbeatResponse,
    CLIENT,
    SERVER,
    # Commands
    CommandPacket,
    GoForward,
    GoBackward,
    GoLeft,
    GoRight,
    TurnLeft,
    TurnRight,
    TurretLeft,
    TurretRight,
    TurretReset,
    GO_FORWARD,
    GO_BACKWARD,
    GO_LEFT,
    GO_RIGHT,
    TURN_LEFT,
    TURN_RIGHT,
    TURRET_LEFT,
    TURRET_RIGHT,
    TURRET_RESET,
    # Telemetry
    SystemStats,
    LegoMotor,
    LegoSensor,
    TelemetryPacket,
    # Kinect
    KinectPacket,
)

# Backward compatibility aliases (old Hello* names)
HelloPacket = HeartbeatPacket
HelloClientPacket = HeartbeatRequest
HelloServerPacket = HeartbeatResponse

logger = logging.getLogger(__name__)


def get_available_interfaces():
    """Get available network interfaces and their addresses."""
    result = {}
    interfaces = netifaces.interfaces()
    for interface in interfaces:
        try:
            address = netifaces.ifaddresses(interface)
            result[interface] = address[netifaces.AF_INET][0]
        except Exception as e:
            logger.exception(e)

    result['default'] = netifaces.gateways()['default'][netifaces.AF_INET][1]

    return result


# Export all public names
__all__ = [
    # Base
    'Packet',
    # Heartbeat
    'HeartbeatPacket', 'HeartbeatRequest', 'HeartbeatResponse',
    'HelloPacket', 'HelloClientPacket', 'HelloServerPacket',  # Backward compat
    'CLIENT', 'SERVER',
    # Commands
    'CommandPacket',
    'GoForward', 'GoBackward', 'GoLeft', 'GoRight',
    'TurnLeft', 'TurnRight', 'TurretLeft', 'TurretRight', 'TurretReset',
    'GO_FORWARD', 'GO_BACKWARD', 'GO_LEFT', 'GO_RIGHT',
    'TURN_LEFT', 'TURN_RIGHT', 'TURRET_LEFT', 'TURRET_RIGHT', 'TURRET_RESET',
    # Telemetry
    'SystemStats', 'LegoMotor', 'LegoSensor', 'TelemetryPacket',
    # Kinect
    'KinectPacket',
    # Utilities
    'get_available_interfaces',
]
