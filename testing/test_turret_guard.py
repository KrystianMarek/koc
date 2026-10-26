"""Unit tests for app/server/turret_guard.py (stdlib unittest, Python 3.5+).

    python3 -m unittest testing.test_turret_guard
"""
import json
import os
import shutil
import tempfile
import unittest

from app.server import turret_guard as g


class FakeClock(object):
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class AllowedSpeed(unittest.TestCase):
    STATE = {"center": 1000, "half_range": 2000, "last": 1000}

    def test_locked_blocks_motion_but_not_stop(self):
        self.assertEqual(g.allowed_speed(None, 0, 50), (0, "locked"))
        self.assertEqual(g.allowed_speed(None, 0, 0), (0, None))

    def test_inside_envelope_passes(self):
        self.assertEqual(g.allowed_speed(self.STATE, 1000, 50), (50, None))
        self.assertEqual(g.allowed_speed(self.STATE, 1000, -50), (-50, None))

    def test_outward_at_limits_blocked_inward_allowed(self):
        high = 1000 + 2000 - g.STOP_MARGIN
        low = 1000 - 2000 + g.STOP_MARGIN
        self.assertEqual(g.allowed_speed(self.STATE, high, 50)[0], 0)
        self.assertEqual(g.allowed_speed(self.STATE, high, -50)[0], -50)
        self.assertEqual(g.allowed_speed(self.STATE, low, -50)[0], 0)
        self.assertEqual(g.allowed_speed(self.STATE, low, 50)[0], 50)
        self.assertEqual(g.allowed_speed(self.STATE, high - 1, 50)[0], 50)


class Guard(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "koc", "turret.json")
        self.clock = FakeClock()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def write(self, **state):
        g.save_state(state, self.path)

    def guard(self):
        return g.TurretGuard(path=self.path, clock=self.clock)

    def test_missing_file_locks(self):
        guard = self.guard()
        guard.observe(0)
        self.assertTrue(guard.locked)
        self.assertEqual(guard.limit(0, 40), 0)

    def test_invalid_file_locks(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w") as f:
            f.write("{not json")
        self.assertIsNone(g.load_state(self.path))

    def test_no_motion_before_first_reading(self):
        self.write(center=0, half_range=5000, last=0)
        self.assertEqual(self.guard().limit(0, 40), 0)

    def test_no_motion_after_failed_read(self):
        self.write(center=0, half_range=5000, last=0)
        guard = self.guard()
        guard.observe(0)
        self.assertEqual(guard.limit(0, 40), 40)
        guard.mark_stale()
        self.assertEqual(guard.limit(0, 40), 0)
        guard.observe(5)
        self.assertEqual(guard.limit(5, 40), 40)

    def test_discontinuity_locks(self):
        self.write(center=42298, half_range=21000, last=42298)
        guard = self.guard()
        guard.observe(0)  # BrickPi power cycle resets encoders to 0
        self.assertTrue(guard.locked)
        self.assertIn("re-reference", guard.reason)
        self.assertEqual(guard.limit(0, 40), 0)

    def test_continuous_start_allows_and_persists(self):
        self.write(center=42298, half_range=21000, last=42298)
        guard = self.guard()
        guard.observe(42300)
        self.assertFalse(guard.locked)
        self.assertEqual(guard.limit(42300, 40), 40)
        guard.observe(42400)  # too soon after start: not persisted yet
        self.assertEqual(g.load_state(self.path)["last"], 42298)
        self.clock.t += 0.3
        guard.observe(42410)
        self.assertEqual(g.load_state(self.path)["last"], 42410)
        self.clock.t += 0.3
        guard.observe(42415)  # below the minimum delta
        self.assertEqual(g.load_state(self.path)["last"], 42410)

    def test_reads_motord_format(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w") as f:
            f.write('{"center": 5, "half_range": 21000, "last": 7}\n')
        self.assertEqual(g.load_state(self.path),
                         {"center": 5, "half_range": 21000, "last": 7})

    def test_save_is_plain_json(self):
        self.write(center=1, half_range=21000, last=2)
        with open(self.path) as f:
            self.assertEqual(json.load(f), {"center": 1, "half_range": 21000, "last": 2})


if __name__ == "__main__":
    unittest.main()
