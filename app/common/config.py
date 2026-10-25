"""
Central configuration for K.O.C Robot.

All ports, timeouts, and calibration values in one place.
Values can be overridden via environment variables.
"""
import os


def _env_int(key: str, default: int) -> int:
    """Get integer from environment variable with default."""
    return int(os.environ.get(key, default))


def _env_float(key: str, default: float) -> float:
    """Get float from environment variable with default."""
    return float(os.environ.get(key, default))


def _env_str(key: str, default: str) -> str:
    """Get string from environment variable with default."""
    return os.environ.get(key, default)


class Config:
    """Robot configuration constants."""

    # ==========================================================================
    # Network Ports
    # ==========================================================================

    # REQ/REP handshake port (HelloServer/HelloClient)
    HELLO_PORT = _env_int('HELLO_PORT', 5556)

    # Internal ports (server-side only, localhost)
    BRICKPI_PORT = _env_int('BRICKPI_PORT', 5557)  # BrickPi → Aggregator
    KINECT_PORT = _env_int('KINECT_PORT', 5558)    # Kinect → Aggregator

    # External ports (client-facing)
    TELEMETRY_PORT = _env_int('TELEMETRY_PORT', 5559)  # PUB: server → clients
    COMMAND_PORT = _env_int('COMMAND_PORT', 5560)      # PULL: clients → server

    # ==========================================================================
    # Connection Settings
    # ==========================================================================

    # Robot IP address (client only)
    ROBOT_IP = _env_str('ROBOT_IP', '')

    # Localhost for internal communication
    LOCALHOST = '127.0.0.1'

    # ==========================================================================
    # Timing
    # ==========================================================================

    # BrickPi update interval (seconds)
    BRICKPI_CLOCK = _env_float('BRICKPI_CLOCK', 0.1)

    # HelloServer sleep between handshakes (seconds)
    HELLO_SLEEP = _env_float('HELLO_SLEEP', 1.0)

    # Command queue max size
    COMMAND_QUEUE_SIZE = _env_int('COMMAND_QUEUE_SIZE', 100)

    # ==========================================================================
    # Kinect Calibration (for point cloud conversion)
    # ==========================================================================

    # Focal lengths (pixels)
    KINECT_FX = _env_float('KINECT_FX', 594.21)
    KINECT_FY = _env_float('KINECT_FY', 591.04)

    # Principal point (pixels)
    KINECT_CX = _env_float('KINECT_CX', 339.5)
    KINECT_CY = _env_float('KINECT_CY', 242.7)

    # ==========================================================================
    # Depth Processing
    # ==========================================================================

    # Raw depth range (11-bit sensor, 0-2047)
    # Note: Raw values are DISPARITY (not distance) - see frame_processor.py.
    # The conversion 0.1236*tan(raw/2842.5 + 1.1863) diverges at raw 1093
    # (argument reaches pi/2): larger raw yields negative/absurd distances,
    # so the valid ceiling is 1008 (0.42 m .. 4.0 m window used by probes).
    DEPTH_MAX = 2047
    DEPTH_MIN_VALID = _env_int('DEPTH_MIN_VALID', 300)   # Raw: filter too close
    DEPTH_MAX_VALID = _env_int('DEPTH_MAX_VALID', 1008)  # Raw: tan domain limit

    # Metric depth range (after conversion from raw disparity)
    # Used for filtering valid points in point cloud generation
    DEPTH_MIN_METERS = _env_float('DEPTH_MIN_METERS', 0.4)   # 40cm (Kinect min)
    DEPTH_MAX_METERS = _env_float('DEPTH_MAX_METERS', 4.0)   # 4m (practical max)

    # Display normalization
    DEPTH_DISPLAY_BITS = 10  # Clip to 10 bits before >> 2 to 8-bit

    # ==========================================================================
    # Point Cloud Settings
    # ==========================================================================

    # Use depth-based coloring (True) or attempt RGB alignment (False)
    POINTCLOUD_DEPTH_COLORING = True

    # Subsample stride (2 = every 2nd pixel, 4 = every 4th, etc.)
    POINTCLOUD_STRIDE = _env_int('POINTCLOUD_STRIDE', 2)
