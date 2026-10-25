#!/usr/bin/env python3
"""
K.O.C Robot Server

Runs on Raspberry Pi with BrickPi+ and Kinect.
Accepts commands from clients and publishes telemetry/video.
"""
import logging
import os
import signal
from queue import Queue

import zmq

from app.common.config import Config
from app.common.logging_wrapper import setup_logging
from app.server.brick_pi_wrapper import BrickPiWrapper
from app.server.command_receiver import CommandReceiver
from app.server.handshake_server import HandshakeServer
from app.server.kinect_process import KinectProcess


def telemetry_publisher(localhost, brick_pi_port, kinect_port, publisher_port):
    """
    Aggregates data from BrickPi and Kinect, publishes to clients.

    This is the main loop that runs on the server.
    """
    context = zmq.Context()
    logger = logging.getLogger(__name__)

    brick_pi_receiver = context.socket(zmq.PULL)
    brick_pi_receiver.connect("tcp://{}:{}".format(localhost, brick_pi_port))

    kinect_receiver = context.socket(zmq.PULL)
    kinect_receiver.connect("tcp://{}:{}".format(localhost, kinect_port))

    poller = zmq.Poller()
    poller.register(brick_pi_receiver, zmq.POLLIN)
    poller.register(kinect_receiver, zmq.POLLIN)

    publisher = context.socket(zmq.PUB)
    publisher.bind('tcp://*:{}'.format(publisher_port))
    logger.info("Telemetry publisher bound to :{}".format(publisher_port))

    while True:
        try:
            socks = dict(poller.poll())
        except KeyboardInterrupt:
            break

        if brick_pi_receiver in socks:
            publisher.send(brick_pi_receiver.recv())

        if kinect_receiver in socks:
            publisher.send(kinect_receiver.recv())

    publisher.close()
    brick_pi_receiver.close()
    kinect_receiver.close()
    context.term()


def main():
    logger = logging.getLogger(__name__)

    command_queue = Queue(maxsize=Config.COMMAND_QUEUE_SIZE)

    # Create components using centralized config
    brick_pi_wrapper = BrickPiWrapper(
        Config.LOCALHOST,
        Config.BRICKPI_PORT,
        command_queue,
        Config.BRICKPI_CLOCK
    )
    kinect_process = KinectProcess(Config.LOCALHOST, Config.KINECT_PORT)

    # Reap the kinect child on termination so restarts never leave orphans
    # holding the camera and the internal port (bd koc-hw-kinect-wedge).
    def _terminate_kinect(signum, frame):
        kinect_process.terminate()
        os._exit(0)

    signal.signal(signal.SIGTERM, _terminate_kinect)
    command_receiver = CommandReceiver(command_queue, Config.COMMAND_PORT)
    handshake_server = HandshakeServer(
        Config.HELLO_PORT,
        brick_pi_wrapper,
        kinect_process=kinect_process
    )

    # Start command receiver immediately (no client IP needed!)
    command_receiver.start()
    logger.info("Command receiver started on port {}".format(Config.COMMAND_PORT))

    # Start handshake server (manages BrickPi/Kinect startup on first client connect)
    handshake_server.start()

    # Run main telemetry publisher loop
    telemetry_publisher(
        Config.LOCALHOST,
        Config.BRICKPI_PORT,
        Config.KINECT_PORT,
        Config.TELEMETRY_PORT
    )


if __name__ == '__main__':
    setup_logging()
    main()
