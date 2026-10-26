"""
Turret cable envelope guard. The same rules live in robot/motord/src/guard.rs;
change both together.

The turret's cables are neutral at camera-forward and the turret must never
turn more than 180 degrees either way from it. State on the robot, in
~/.koc/turret.json:

    {"center": <ticks>, "half_range": <ticks>, "last": <ticks>}

Fail-closed: a missing or invalid file, or a first encoder reading that does
not match "last" (the BrickPi lost power and reset its encoders, or the turret
was turned by hand), locks the turret until it is re-referenced with
testing/turret_envelope.py.
"""
import json
import logging
import os
import time

STATE_PATH = os.path.expanduser("~/.koc/turret.json")
# Stop this far short of the limit. Measured 2026-10-26: at pwm 250 the v1
# server (10 Hz loop) overshot the stop point by 313 ticks; worst case one
# full cycle plus coast is ~500 ticks.
STOP_MARGIN = 800
DISCONTINUITY = 400      # first reading vs "last" beyond this -> locked
PERSIST_MIN_DELTA = 20
PERSIST_PERIOD_S = 0.25


def load_state(path=STATE_PATH):
    """The state dict, or None when the file is missing or invalid."""
    try:
        with open(path) as f:
            raw = json.load(f)
        state = {k: int(raw[k]) for k in ("center", "half_range", "last")}
    except (IOError, OSError, ValueError, KeyError, TypeError):
        return None
    if state["half_range"] <= STOP_MARGIN:
        return None
    return state


def save_state(state, path=STATE_PATH):
    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({k: int(state[k]) for k in ("center", "half_range", "last")}, f)
    os.rename(tmp, path)


def limits(state):
    """(low, high) encoder positions where outward motion stops."""
    return (state["center"] - state["half_range"] + STOP_MARGIN,
            state["center"] + state["half_range"] - STOP_MARGIN)


def allowed_speed(state, encoder, speed):
    """(speed to apply, reason or None). Positive speed = encoder-positive
    (turret left). Stopping is always allowed; motion back toward the center
    is allowed at the limit."""
    if speed == 0:
        return 0, None
    if state is None:
        return 0, "locked"
    low, high = limits(state)
    if speed > 0 and encoder >= high:
        return 0, "left limit: C={} >= {}".format(encoder, high)
    if speed < 0 and encoder <= low:
        return 0, "right limit: C={} <= {}".format(encoder, low)
    return speed, None


class TurretGuard(object):
    """Stateful wrapper for one motor writer: feed every encoder exchange to
    observe() (success) or mark_stale() (failure), filter every turret speed
    through limit()."""

    def __init__(self, path=STATE_PATH, clock=time.monotonic):
        self._path = path
        self._clock = clock
        self._logger = logging.getLogger(__name__)
        self.state = load_state(path)
        self.reason = None if self.state else "no valid state file {}".format(path)
        self.started = False
        self._fresh = False
        self._last_written = None
        self._last_write_t = None
        self._last_block = None

    @property
    def locked(self):
        return self.state is None

    def observe(self, encoder):
        self._fresh = True
        if not self.started:
            self.started = True
            if self.state is not None and abs(encoder - self.state["last"]) > DISCONTINUITY:
                self.reason = ("encoder C={} but last saved {}: power cycle or hand "
                               "move - re-reference the turret".format(encoder, self.state["last"]))
                self.state = None
            if self.state is None:
                self._logger.error("turret LOCKED: %s", self.reason)
            else:
                self._last_written = self.state["last"]
                self._last_write_t = self._clock()
                self._logger.info("turret envelope ok: C=%d, limits %s", encoder, limits(self.state))
            return
        if self.state is None:
            return
        now = self._clock()
        if (abs(encoder - self._last_written) >= PERSIST_MIN_DELTA
                and now - self._last_write_t >= PERSIST_PERIOD_S):
            self._last_write_t = now
            self.state["last"] = encoder
            try:
                save_state(self.state, self._path)
                self._last_written = encoder
            except (IOError, OSError) as error:
                self._logger.warning("turret state not saved: %s", error)

    def mark_stale(self):
        """The last exchange failed: the encoder value is old."""
        self._fresh = False

    def limit(self, encoder, speed):
        """The speed to write for a requested turret speed."""
        if not self.started or not self._fresh:
            return 0
        out, reason = allowed_speed(self.state, encoder, speed)
        if reason and not self._last_block:
            self._logger.warning("turret command blocked: %s",
                                 self.reason if reason == "locked" else reason)
        self._last_block = reason
        return out
