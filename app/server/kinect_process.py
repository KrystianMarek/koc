"""
Kinect capture - spawned, self-healing process pushing KinectPackets.

Full fix set for bd koc-hw-kinect-wedge:

1. **Spawn, not fork** - no inherited ZMQ fds (fork corrupted the aggregator).
2. **Throttled, latest-wins pushes** - TARGET_FPS cap with DONTWAIT sends;
   frames are dropped instead of queued, so the pipe can never fill and jam
   the pipeline.
3. **Watchdog + auto-recovery** - the sync API blocks un-interruptibly inside
   libfreenect during USB storms, so capture runs on the callback API
   (process_events loop). If no frame arrives for STALL_EXIT_S the child
   os._exit()s - releasing the camera and port at the kernel level - and a
   reaper thread in the server respawns it within ~1 s. A USB storm costs
   seconds of downtime instead of a dead server.
4. Known physical limit: the Kinect hangs on a powered two-hub chain (its
   power source; a direct port is impossible per the user), whose link
   degrades after minutes of continuous streaming - the watchdog turns that
   into a brief recovery instead of a wedge. See
   doc/architecture/kinect-interface.md.
"""
import logging
import multiprocessing as mp
import os
import threading
import time

import zmq

from app.common.serialization import compress
from app.networking import KinectPacket

TARGET_FPS = 10.0
FRAME_PERIOD = 1.0 / TARGET_FPS
STALL_EXIT_S = 10.0     # no frames for this long -> exit (reaper respawns)
OPEN_BUDGET_S = 60.0    # device open must succeed within this or exit

_log = logging.getLogger("kinect_worker")

# latest-frame slot shared between the capture callbacks and the push loop
_slot = {"video": None, "depth": None, "t": 0.0}
_slot_lock = threading.Lock()


def _on_video(dev, data, timestamp):
    with _slot_lock:
        _slot["video"] = data.copy()
        _slot["t"] = time.time()


def _on_depth(dev, data, timestamp):
    with _slot_lock:
        _slot["depth"] = data.copy()
        _slot["t"] = time.time()


def _open_with_budget():
    """Open device 0, retrying; os._exit (for respawn) if the budget lapses."""
    import freenect as fn  # child-side import; the parent never touches libusb

    t0 = time.time()
    while True:
        try:
            ctx = fn.init()
            dev = fn.open_device(ctx, 0)
            if dev is None:
                raise RuntimeError("open_device returned None")
            return fn, ctx, dev
        except Exception as e:
            _log.warning("kinect open failed: %s - retrying in 5 s", e)
            if time.time() - t0 > OPEN_BUDGET_S:
                _log.error("open budget exhausted - exiting for respawn")
                os._exit(1)
            time.sleep(5)


def kinect_worker(host, port):
    """Capture RGB+depth via callbacks; push latest frames at TARGET_FPS.

    Runs in a spawned process: imports here happen in the child only.
    """
    logging.basicConfig(
        format="%(asctime)s|kinect_worker|%(levelname)s|%(message)s")
    import freenect as fn

    fn, ctx, dev = _open_with_budget()
    _log.info("device opened; starting streams (RGB + 11-bit depth)")

    sender = zmq.Context().socket(zmq.PUSH)
    address = "tcp://{}:{}".format(host, port)
    sender.bind(address)
    _log.info("pushing to %s", address)

    # capture thread: process_events loop; may stall during USB storms
    cap = threading.Thread(
        target=lambda: fn.runloop(depth=_on_depth, video=_on_video, dev=dev),
        daemon=True)
    cap.start()

    sequence = 0
    try:
        while True:
            with _slot_lock:
                video, depth, t = _slot["video"], _slot["depth"], _slot["t"]
            if video is not None and depth is not None:
                if time.time() - t > STALL_EXIT_S:
                    _log.error("no frames for %.0f s (USB storm?) - "
                               "exiting for respawn", STALL_EXIT_S)
                    os._exit(1)
                packet = compress(KinectPacket(
                    sequence, video, depth, 0, 0))
                try:
                    sender.send(packet, zmq.DONTWAIT)
                    sequence += 1
                except zmq.Again:
                    pass  # latest-wins: drop rather than queue
            time.sleep(FRAME_PERIOD)
    finally:
        sender.close()


class KinectProcess(object):
    """Handle matching the v1 interface (start/is_alive/running) + self-healing.

    A reaper thread respawns the capture child whenever it dies (the child
    exits itself when frames stall); terminate() kills it explicitly (used
    by the server's SIGTERM handler to prevent orphans).
    """

    def __init__(self, host, port, running=True):
        self._host = host
        self._port = port
        self._running = running
        self._proc = None
        self._reaper_t = None
        self._lock = threading.Lock()
        self._log = logging.getLogger(__name__)

    def _spawn(self):
        with self._lock:
            if self._proc is not None and self._proc.is_alive():
                return
            self._proc = mp.get_context("spawn").Process(
                target=kinect_worker, args=(self._host, self._port),
                daemon=True)
            self._proc.start()
        self._log.warning("kinect worker spawned pid=%d", self._proc.pid)

    def _reaper(self):
        while True:
            time.sleep(1.0)
            if self._running:
                self._spawn()

    def start(self):
        with self._lock:
            if self._reaper_t is None:
                self._reaper_t = threading.Thread(
                    target=self._reaper, daemon=True)
                self._reaper_t.start()
        self._spawn()

    def is_alive(self):
        with self._lock:
            return self._proc is not None and self._proc.is_alive()

    def terminate(self):
        with self._lock:
            if self._proc is not None:
                self._proc.terminate()

    @property
    def running(self):
        return self._running

    @running.setter
    def running(self, value):
        self._running = value
