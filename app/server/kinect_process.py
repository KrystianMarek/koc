"""
Kinect capture - spawned process pushing KinectPackets to the aggregator.

Two fixes for bd koc-hw-kinect-wedge:

1. **Spawn, not fork.** The original ran as a forked Process started AFTER
   the server had created its ZMQ sockets, so the child inherited copies of
   them (ss showed the child owning fds on :5557) - a known ZMQ fork hazard
   that silently corrupted the aggregator's pipes. Spawn re-imports cleanly
   and inherits nothing.

2. **Throttled capture.** The original pushed frames as fast as libfreenect
   delivered them (~5.7 GB in 33 min at 139% CPU), flooding the aggregator.
   TARGET_FPS caps it; the client GUI streams fine at this rate.
"""
import logging
import multiprocessing as mp
import time

import zmq

from app.common.serialization import compress
from app.networking import KinectPacket

TARGET_FPS = 10.0
FRAME_PERIOD = 1.0 / TARGET_FPS
ERROR_BACKOFF = 0.5


def kinect_worker(host, port):
    """Capture video+depth at TARGET_FPS and PUSH KinectPackets to the aggregator.

    Runs in a spawned process: imports here happen in the child only.
    """
    logging.basicConfig(
        format="%(asctime)s|kinect_worker|%(levelname)s|%(message)s")
    logger = logging.getLogger("kinect_worker")

    import freenect  # child-side import; the parent never touches libusb

    context = zmq.Context()
    sender = context.socket(zmq.PUSH)
    address = "tcp://{}:{}".format(host, port)
    sender.bind(address)
    logger.info("Starting -> address: %s", address)

    sequence = 0
    try:
        while True:
            start = time.time()
            try:
                video, _ = freenect.sync_get_video(0)
                depth, _ = freenect.sync_get_depth(0)
                # tilt interfaces are stubbed in v1 (kept for packet compat)
                sender.send(compress(KinectPacket(sequence, video, depth, 0, 0)))
                sequence += 1
            except Exception as e:
                logger.exception(e)
                time.sleep(ERROR_BACKOFF)
            elapsed = time.time() - start
            if elapsed < FRAME_PERIOD:
                time.sleep(FRAME_PERIOD - elapsed)
    finally:
        sender.close()
        context.term()


class KinectProcess(object):
    """Handle matching the v1 interface (start/is_alive/running)."""

    def __init__(self, host, port, running=True):
        self._running = running
        self._proc = mp.get_context("spawn").Process(
            target=kinect_worker, args=(host, port), daemon=True)

    def start(self):
        self._proc.start()

    def is_alive(self):
        return self._proc.is_alive()

    @property
    def running(self):
        return self._running

    @running.setter
    def running(self, value):
        self._running = value
