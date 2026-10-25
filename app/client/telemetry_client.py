"""
TelemetryClient - Receives telemetry and Kinect data from the robot.

Subscribes to the robot's telemetry publisher (ZMQ PUB socket) and
emits Qt signals when data is received.
"""
import logging

import zmq
from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSignal

from app.client.heartbeat_client import HeartbeatClient
from app.common.config import Config
from app.common.serialization import decompress
from app.networking import KinectPacket, TelemetryPacket


class TelemetryClient(QtCore.QThread):
    """
    Receives telemetry and Kinect packets from the robot via ZMQ SUB socket.

    Signals:
        telemetry_packet_signal: Emitted when TelemetryPacket received
        kinect_packet_signal: Emitted when KinectPacket received
        connection_timeout_signal: Emitted when no data received for timeout period
    """

    telemetry_packet_signal = pyqtSignal(TelemetryPacket)
    kinect_packet_signal = pyqtSignal(KinectPacket)
    connection_timeout_signal = pyqtSignal()

    # Timeout in milliseconds (2 seconds without data = timeout)
    POLL_TIMEOUT_MS = 500
    TIMEOUT_THRESHOLD = 4  # 4 timeouts = 2 seconds

    def __init__(self, port: int = None, parent=None):
        QtCore.QThread.__init__(self, parent)
        self._logger = logging.getLogger(__name__)
        self._robot_ip_address = ''
        self._port = port if port is not None else Config.TELEMETRY_PORT

        self._heartbeat_client = None

        self.running = True
        self.ultrasonic_sensor = 0
        self.color_sensor = 0
        self._timeout_count = 0

    def robot_ip_address(self):
        return self._robot_ip_address

    def set_robot_ip_address(self, ip):
        self._robot_ip_address = ip

    def launch_heartbeat_client(self):
        """Start the heartbeat client to maintain connection."""
        self._heartbeat_client = HeartbeatClient(self._robot_ip_address, Config.HELLO_PORT)
        self._heartbeat_client.start()

    def on_telemetry_packet(self, packet: TelemetryPacket):
        self.telemetry_packet_signal.emit(packet)

    def run(self):
        self.launch_heartbeat_client()

        context = zmq.Context()
        zmq_address = "tcp://{}:{}".format(self._robot_ip_address, self._port)
        self._logger.debug("ZMQ connecting to {}".format(zmq_address))

        subscriber = context.socket(zmq.SUB)
        subscriber.connect(zmq_address)
        subscriber.setsockopt(zmq.SUBSCRIBE, b'')

        # Use poller for non-blocking receive with timeout
        poller = zmq.Poller()
        poller.register(subscriber, zmq.POLLIN)

        while self.running:
            try:
                # Poll with timeout instead of blocking recv
                events = dict(poller.poll(timeout=self.POLL_TIMEOUT_MS))

                if subscriber in events and events[subscriber] == zmq.POLLIN:
                    # Data available - reset timeout counter
                    self._timeout_count = 0
                    data = decompress(subscriber.recv(flags=zmq.NOBLOCK))

                    if type(data) is TelemetryPacket:
                        self.telemetry_packet_signal.emit(data)
                    if type(data) is KinectPacket:
                        self.kinect_packet_signal.emit(data)
                else:
                    # No data - increment timeout counter
                    self._timeout_count += 1
                    if self._timeout_count >= self.TIMEOUT_THRESHOLD:
                        self._logger.warning("Connection timeout - no data for {} seconds".format(
                            (self.POLL_TIMEOUT_MS * self.TIMEOUT_THRESHOLD) / 1000))
                        self.connection_timeout_signal.emit()
                        self._timeout_count = 0  # Reset to avoid spam

            except zmq.Again:
                # No message available (shouldn't happen with poller, but safe)
                pass
            except Exception as e:
                self._logger.exception(e)
                break

        self._heartbeat_client.wait()
        subscriber.close()
        context.term()
