import logging
import queue
import time
from queue import Queue
from threading import Thread

import psutil
import smbus2
import zmq
from BrickPi import PORT_A, PORT_D, PORT_C, PORT_1, PORT_4, TYPE_SENSOR_LIGHT_ON, TYPE_SENSOR_ULTRASONIC_CONT, \
    BrickPiSetup, BrickPi, BrickPiSetupSensors, BrickPiUpdateValues

from app.common.serialization import compress, decompress
from app.networking import LegoMotor, LegoSensor, TelemetryPacket, SystemStats

COMMAND_QUEUE_GRACE = 3


class BrickPiWrapper(Thread):
    def __init__(self, host, port, command_queue: Queue, clock=0.1):
        Thread.__init__(self)
        Thread.daemon = True
        self._clock = clock
        self._host = host
        self._port = port
        self._logger = logging.getLogger(__name__)
        self._command_queue = command_queue

        BrickPiSetup()

        self._left_motor = LegoMotor(PORT_A)
        BrickPi.MotorEnable[PORT_A] = 1
        self._right_motor = LegoMotor(PORT_D)
        BrickPi.MotorEnable[PORT_D] = 1
        self._turret_motor = LegoMotor(PORT_C)
        BrickPi.MotorEnable[PORT_C] = 1

        self._color_sensor = LegoSensor(PORT_1)
        BrickPi.SensorType[PORT_1] = TYPE_SENSOR_LIGHT_ON

        self._ultrasonic_sensor = LegoSensor(PORT_4)
        BrickPi.SensorType[PORT_4] = TYPE_SENSOR_ULTRASONIC_CONT

        BrickPiSetupSensors()

        self._running = True
        self._sequence = 0
        self._brick_temp = 0
        self._brick_voltage = 0
        self._command_queue_grace = COMMAND_QUEUE_GRACE

        # One SMBus for the wrapper's lifetime. The robot's smbus2 (0.2.1)
        # has no context-manager support, so the previous per-call
        # open/with pattern leaked one /dev/i2c-1 fd per read and exhausted
        # the process limit in ~15-20 min, killing telemetry
        # (bd koc-hw-kinect-wedge). Opened lazily; reopened on error.
        self._voltage_bus = None

        # System stats
        self._system_stats = SystemStats()
        self._last_net_bytes_sent = 0
        self._last_net_bytes_recv = 0
        self._last_net_time = time.time()

    @property
    def running(self):
        return self._running

    @running.setter
    def running(self, running):
        self._running = running

    def run(self):
        context = zmq.Context()
        sender = context.socket(zmq.PUSH)
        address = "tcp://{}:{}".format(self._host, self._port)
        sender.bind(address)
        self._logger.info("Starting -> address: {}".format(address))

        command_packet = TelemetryPacket(1)
        while self._running:
            try:
                command_packet = self._command_queue.get_nowait()
                self._command_queue_grace = COMMAND_QUEUE_GRACE
            except queue.Empty as e:
                if self._command_queue_grace > 0:
                    self._command_queue_grace -= 1
                if self._command_queue_grace <= 0:
                    self._command_queue_grace = COMMAND_QUEUE_GRACE
                    command_packet = TelemetryPacket(1)
                    self.update_values(command_packet)
                    # self._logger.exception(e)
            except KeyboardInterrupt:
                self._logger.debug("exiting...")
                self._running = False
            except Exception as e:
                self._logger.exception(e)
                break

            try:
                telemetry_packet = self.update_values(command_packet)
                sender.send(compress(telemetry_packet))
            except KeyboardInterrupt:
                self._logger.debug("exiting...")
                self._running = False
            except Exception as e:
                self._logger.exception(e)
                break

        sender.close()
        context.term()

    def update_values(self, telemetry: TelemetryPacket) -> TelemetryPacket:
        BrickPi.MotorSpeed[self._left_motor.port] = telemetry.left_motor.speed
        BrickPi.MotorSpeed[self._right_motor.port] = telemetry.right_motor.speed
        BrickPi.MotorSpeed[self._turret_motor.port] = telemetry.turret_motor.speed

        BrickPiUpdateValues()

        # Update temp, voltage, and system stats every 10 cycles (~1 second)
        if self._sequence % 10 == 0:
            self._brick_temp = self.read_temp()
            self._brick_voltage = self.get_voltage()
            self._update_system_stats()

        self._left_motor.angle = BrickPi.Encoder[self._left_motor.port]
        self._right_motor.angle = BrickPi.Encoder[self._right_motor.port]
        self._turret_motor.angle = BrickPi.Encoder[self._turret_motor.port]

        self._color_sensor.raw = BrickPi.Sensor[self._color_sensor.port]
        self._ultrasonic_sensor.raw = BrickPi.Sensor[self._ultrasonic_sensor.port]

        self._sequence += 1
        output = TelemetryPacket(self._sequence)
        output.left_motor = self._left_motor
        output.right_motor = self._right_motor
        output.turret_motor = self._turret_motor
        output.color_sensor = self._color_sensor
        output.ultrasound_sensor = self._ultrasonic_sensor
        output.temperature = self._brick_temp
        output.voltage = self._brick_voltage
        output.system_stats = self._system_stats

        time.sleep(self._clock)

        return output

    def _update_system_stats(self):
        """Collect system stats using psutil."""
        try:
            # CPU usage (non-blocking, uses cached value from previous call)
            self._system_stats.cpu_percent = psutil.cpu_percent(interval=None)

            # RAM usage
            mem = psutil.virtual_memory()
            self._system_stats.ram_percent = mem.percent
            self._system_stats.ram_used_mb = mem.used / (1024 * 1024)
            self._system_stats.ram_total_mb = mem.total / (1024 * 1024)

            # Network stats for wlan0
            net_io = psutil.net_io_counters(pernic=True)
            if 'wlan0' in net_io:
                wlan = net_io['wlan0']
                current_time = time.time()
                time_delta = current_time - self._last_net_time

                if time_delta > 0 and self._last_net_bytes_sent > 0:
                    # Calculate bandwidth in Mbps
                    bytes_sent_delta = wlan.bytes_sent - self._last_net_bytes_sent
                    bytes_recv_delta = wlan.bytes_recv - self._last_net_bytes_recv
                    total_bytes = bytes_sent_delta + bytes_recv_delta
                    bandwidth_mbps = (total_bytes * 8) / (time_delta * 1000000)
                    self._system_stats.net_bandwidth_mbps = round(bandwidth_mbps, 2)

                self._last_net_bytes_sent = wlan.bytes_sent
                self._last_net_bytes_recv = wlan.bytes_recv
                self._last_net_time = current_time
                self._system_stats.net_bytes_sent = wlan.bytes_sent
                self._system_stats.net_bytes_recv = wlan.bytes_recv

        except Exception as e:
            self._logger.warning("Failed to collect system stats: {}".format(e))

    def read_temp(self):
        temp = 0
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as file:
            try:
                temp = int(file.readline()) / 1000
            except Exception as e:
                self._logger.exception(e)

        return temp

    def get_voltage(self):
        """
        Reads the digital output code of the MCP3021 chip on the BrickPi+ over i2c.
        Some bit operation magic to get a voltage floating number.

        If this doesnt work try this on the command line: i2cdetect -y 1
        The 1 in there is the bus number, same as in bus = smbus.SMBus(1)
        Google the resulting error.

        :return: voltage (float)
        """

        # time.sleep(0.1) # Necessary?
        try:
            # SMBUS 1 because we're using greater than V1. One bus for the
            # wrapper's lifetime: the robot's smbus2 0.2.1 has no context
            # manager, so the previous per-call open/with leaked one
            # /dev/i2c-1 fd per read and exhausted the process limit in
            # ~15-20 min, killing the wrapper thread and telemetry with it
            # (bd koc-hw-kinect-wedge). On any error the bus is dropped so
            # the next call reopens fresh.
            address = 0x48
            if self._voltage_bus is None:
                self._voltage_bus = smbus2.SMBus(1)
            # the 0 command is mandatory for the protocol but not used in this chip.
            data = self._voltage_bus.read_word_data(address, 0)

            # from this data we need the last 4 bits and the first 6.
            last_4 = data & 0b1111 # using a bit mask
            first_6 = data >> 10 # left shift 10 because data is 16 bits

            # together they make the voltage conversion ratio
            # to make it all easier the last_4 bits are most significant :S
            vratio = (last_4 << 6) | first_6

            # Now we can calculate the battery voltage like so:
            ratio = 0.01818     # this is 0.1/5.5V Still have to find out why...
            voltage = vratio * ratio

            return "{:.3F}".format(voltage)

        except Exception as e:
            self._logger.exception(e)
            self._voltage_bus = None  # reopen fresh on the next call
            return 0
