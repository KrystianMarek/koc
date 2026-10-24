"""
Packet classes for robot communication.

All packet types used for client-server communication are defined here:
- Packet: Base class with sequence number and timestamp
- HeartbeatPacket: Connection handshake/keepalive
- CommandPacket: Movement and turret commands
- TelemetryPacket: Sensor data from robot
- KinectPacket: Video and depth frames from Kinect
"""
import time


# =============================================================================
# Base Packet
# =============================================================================

class Packet:
    """Base packet class with sequence number and timestamp."""

    def __init__(self, sequence: int):
        self._sequence = sequence
        self._time = time.time()

    @property
    def sequence(self) -> int:
        return self._sequence

    @property
    def time(self) -> float:
        return self._time


# =============================================================================
# Heartbeat Packets (formerly Hello*)
# =============================================================================

CLIENT = 1
SERVER = 2


class HeartbeatPacket(Packet):
    """Base heartbeat packet for connection keepalive."""

    def __init__(self, sequence: int, role: int, network: dict, running: bool, sleep: float):
        Packet.__init__(self, sequence)
        self._role = role
        self._running = running
        self._network = network
        self._sleep = sleep

    @property
    def sleep(self) -> float:
        return self._sleep

    @property
    def role(self) -> int:
        return self._role

    @role.setter
    def role(self, role: int):
        self._role = role

    def get_network(self) -> dict:
        return self._network

    @property
    def running(self) -> bool:
        return self._running


class HeartbeatRequest(HeartbeatPacket):
    """Client heartbeat request (formerly HelloClientPacket)."""

    def __init__(self, sequence: int, running: bool, network: dict, sleep: float):
        HeartbeatPacket.__init__(
            self, sequence, role=CLIENT, running=running, network=network, sleep=sleep)


class HeartbeatResponse(HeartbeatPacket):
    """Server heartbeat response (formerly HelloServerPacket)."""

    def __init__(self, sequence: int, running: bool, network: dict, sleep: float):
        HeartbeatPacket.__init__(
            self, sequence=sequence, role=SERVER, running=running, network=network, sleep=sleep)


# =============================================================================
# Command Packets
# =============================================================================

# Command type constants
GO_FORWARD = 1
GO_BACKWARD = 2
GO_LEFT = 3
GO_RIGHT = 4
TURN_LEFT = 5
TURN_RIGHT = 6
TURRET_RIGHT = 7
TURRET_LEFT = 8
TURRET_RESET = 9


class CommandPacket(Packet):
    """Base command packet for robot control."""

    def __init__(self, command: int, value: int):
        Packet.__init__(self, 0)
        self._command = command
        self._value = value

    @property
    def command(self) -> int:
        return self._command

    @property
    def value(self) -> int:
        return self._value

    def __repr__(self):
        return repr("command: {}, value: {}".format(self._command, self._value))


class GoForward(CommandPacket):
    """Move robot forward."""
    def __init__(self, value: int):
        CommandPacket.__init__(self, GO_FORWARD, value)


class GoBackward(CommandPacket):
    """Move robot backward."""
    def __init__(self, value: int):
        CommandPacket.__init__(self, GO_BACKWARD, value)


class GoLeft(CommandPacket):
    """Strafe robot left."""
    def __init__(self, value: int):
        CommandPacket.__init__(self, GO_LEFT, value)


class GoRight(CommandPacket):
    """Strafe robot right."""
    def __init__(self, value: int):
        CommandPacket.__init__(self, GO_RIGHT, value)


class TurnLeft(CommandPacket):
    """Turn robot left (rotate in place)."""
    def __init__(self, value: int):
        CommandPacket.__init__(self, TURN_LEFT, value)


class TurnRight(CommandPacket):
    """Turn robot right (rotate in place)."""
    def __init__(self, value: int):
        CommandPacket.__init__(self, TURN_RIGHT, value)


class TurretLeft(CommandPacket):
    """Rotate turret left."""
    def __init__(self, value: int):
        CommandPacket.__init__(self, TURRET_LEFT, value)


class TurretRight(CommandPacket):
    """Rotate turret right."""
    def __init__(self, value: int):
        CommandPacket.__init__(self, TURRET_RIGHT, value)


class TurretReset(CommandPacket):
    """Reset turret to center position."""
    def __init__(self):
        CommandPacket.__init__(self, TURRET_RESET, 0)


# =============================================================================
# Telemetry Data Classes
# =============================================================================

class SystemStats:
    """System statistics from the robot (CPU, RAM, Network)."""

    def __init__(self):
        self._cpu_percent = 0.0
        self._ram_percent = 0.0
        self._ram_used_mb = 0.0
        self._ram_total_mb = 0.0
        self._net_bytes_sent = 0
        self._net_bytes_recv = 0
        self._net_bandwidth_mbps = 0.0

    @property
    def cpu_percent(self) -> float:
        return self._cpu_percent

    @cpu_percent.setter
    def cpu_percent(self, value: float):
        self._cpu_percent = value

    @property
    def ram_percent(self) -> float:
        return self._ram_percent

    @ram_percent.setter
    def ram_percent(self, value: float):
        self._ram_percent = value

    @property
    def ram_used_mb(self) -> float:
        return self._ram_used_mb

    @ram_used_mb.setter
    def ram_used_mb(self, value: float):
        self._ram_used_mb = value

    @property
    def ram_total_mb(self) -> float:
        return self._ram_total_mb

    @ram_total_mb.setter
    def ram_total_mb(self, value: float):
        self._ram_total_mb = value

    @property
    def net_bytes_sent(self) -> int:
        return self._net_bytes_sent

    @net_bytes_sent.setter
    def net_bytes_sent(self, value: int):
        self._net_bytes_sent = value

    @property
    def net_bytes_recv(self) -> int:
        return self._net_bytes_recv

    @net_bytes_recv.setter
    def net_bytes_recv(self, value: int):
        self._net_bytes_recv = value

    @property
    def net_bandwidth_mbps(self) -> float:
        return self._net_bandwidth_mbps

    @net_bandwidth_mbps.setter
    def net_bandwidth_mbps(self, value: float):
        self._net_bandwidth_mbps = value


class LegoMotor:
    """LEGO motor state (encoder, speed)."""

    def __init__(self, port=None, speed: int = 0, desired_speed: int = 0, angle: int = 0):
        self._port = port
        self._speed = speed
        self._desired_speed = desired_speed
        self._angle = angle

    @property
    def port(self):
        return self._port

    @property
    def speed(self) -> int:
        return self._speed

    @speed.setter
    def speed(self, speed: int):
        self._speed = speed

    @property
    def desired_speed(self) -> int:
        return self._desired_speed

    @desired_speed.setter
    def desired_speed(self, desired_speed: int):
        self._desired_speed = desired_speed

    @property
    def angle(self) -> int:
        return self._angle

    @angle.setter
    def angle(self, angle: int):
        self._angle = angle

    def stop(self):
        self._speed = 0


class LegoSensor:
    """LEGO sensor state (raw value)."""

    def __init__(self, port=None):
        self._port = port
        self._raw = 0

    @property
    def port(self):
        return self._port

    @property
    def raw(self) -> int:
        return self._raw

    @raw.setter
    def raw(self, raw: int):
        self._raw = raw


class TelemetryPacket(Packet):
    """Telemetry data from robot (motors, sensors, system stats)."""

    def __init__(
            self,
            sequence: int,
            left_motor: LegoMotor = None,
            right_motor: LegoMotor = None,
            turret_motor: LegoMotor = None,
            ultrasound_sensor: LegoSensor = None,
            color_sensor: LegoSensor = None):
        Packet.__init__(self, sequence)
        self._left_motor = left_motor or LegoMotor()
        self._right_motor = right_motor or LegoMotor()
        self._turret_motor = turret_motor or LegoMotor()
        self._ultrasound_sensor = ultrasound_sensor or LegoSensor()
        self._color_sensor = color_sensor or LegoSensor()
        self._voltage = 0
        self._temperature = 0
        self._system_stats = SystemStats()

    @property
    def voltage(self) -> float:
        return self._voltage

    @voltage.setter
    def voltage(self, voltage: float):
        self._voltage = voltage

    @property
    def temperature(self) -> float:
        return self._temperature

    @temperature.setter
    def temperature(self, temperature: float):
        self._temperature = temperature

    @property
    def left_motor(self) -> LegoMotor:
        return self._left_motor

    @left_motor.setter
    def left_motor(self, motor: LegoMotor):
        self._left_motor = motor

    @property
    def right_motor(self) -> LegoMotor:
        return self._right_motor

    @right_motor.setter
    def right_motor(self, motor: LegoMotor):
        self._right_motor = motor

    @property
    def turret_motor(self) -> LegoMotor:
        return self._turret_motor

    @turret_motor.setter
    def turret_motor(self, motor: LegoMotor):
        self._turret_motor = motor

    @property
    def ultrasound_sensor(self) -> LegoSensor:
        return self._ultrasound_sensor

    @ultrasound_sensor.setter
    def ultrasound_sensor(self, sensor: LegoSensor):
        self._ultrasound_sensor = sensor

    @property
    def color_sensor(self) -> LegoSensor:
        return self._color_sensor

    @color_sensor.setter
    def color_sensor(self, sensor: LegoSensor):
        self._color_sensor = sensor

    @property
    def system_stats(self) -> SystemStats:
        return self._system_stats

    @system_stats.setter
    def system_stats(self, stats: SystemStats):
        self._system_stats = stats


# =============================================================================
# Kinect Packet
# =============================================================================

class KinectPacket(Packet):
    """Video and depth data from Kinect sensor."""

    def __init__(self, sequence: int, video_frame, depth, tilt_state, tilt_degs):
        Packet.__init__(self, sequence)
        self._video_frame = video_frame
        self._depth = depth
        self._tilt_state = tilt_state
        self._tilt_degs = tilt_degs

    @property
    def video_frame(self):
        """RGB video frame from Kinect."""
        return self._video_frame

    @property
    def depth(self):
        """Depth array from Kinect."""
        return self._depth

    @property
    def tilt_state(self):
        """Current tilt motor state."""
        return self._tilt_state

    @property
    def tilt_degs(self):
        """Current tilt angle in degrees."""
        return self._tilt_degs

    # Backward compatibility methods (deprecated, use properties instead)
    def get_video_frame(self):
        return self._video_frame

    def get_depth(self):
        return self._depth

    def get_tilt_state(self):
        return self._tilt_state

    def get_tilt_degs(self):
        return self._tilt_degs
