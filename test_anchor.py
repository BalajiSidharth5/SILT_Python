"""Tests for anchor.py. Run with:  python test_anchor.py"""

import math

from anchor import (
    METERS_PER_DEG_LAT, STATUS_COMPASS_DEAD, STATUS_NO_ANCHOR, STATUS_NO_FIX, STATUS_OK,
    anchor_target, clear_anchor, new_anchor, offset_to_anchor, set_anchor, turn_to_servo,
)

BOAT_LAT, BOAT_LON = 29.6516, -82.3248   # Lake Alice, Gainesville


def reading(lat=BOAT_LAT, lon=BOAT_LON, heading=0.0, fix=1):
    return {"seq": 1, "w1mA": 0, "w1mV": 0, "w2mA": 0, "w2mV": 0,
            "lat": lat, "lon": lon, "fix": fix, "sats": 9, "hdop": 0.9,
            "heading": heading, "pitch": 0.0, "roll": 0.0}


def meters_east(m, lat=BOAT_LAT):
    return m / (METERS_PER_DEG_LAT * math.cos(math.radians(lat)))


def meters_north(m):
    return m / METERS_PER_DEG_LAT


def anchored_at(lat, lon, now=0.0):
    a = new_anchor()
    assert set_anchor(a, reading(lat=lat, lon=lon), now=now)
    return a


def test_handoff_worked_cases():
    # Anchor 10 m due east of the boat
    a = anchored_at(BOAT_LAT, BOAT_LON + meters_east(10))
    cases = [(0, 0, "forward"),      # case 1: facing north -> 90 right -> servo 0
             (90, 90, "forward"),    # case 2: facing east  -> straight ahead -> servo 90
             (180, 180, "forward")]  # case 3: facing south -> 90 left -> servo 180
    for heading, servo, direction in cases:
        r = anchor_target(a, reading(heading=heading), now=1.0)
        assert r["status"] == STATUS_OK
        assert r["target_angle"] == servo, (heading, r)
        assert r["direction"] == direction, (heading, r)


def test_anchor_behind_reverses():
    # Facing west with the anchor due east: anchor is dead astern
    a = anchored_at(BOAT_LAT, BOAT_LON + meters_east(10))
    r = anchor_target(a, reading(heading=270), now=1.0)
    assert (r["target_angle"], r["direction"]) == (90, "reverse"), r


def test_reverse_aims_stern_at_anchor():
    # Anchor behind and to the right (135 deg clockwise of the bow): back up with
    # the thrusters pointed 45 left, which pushes the boat back and to the right
    assert turn_to_servo(135) == (135, "reverse")
    assert turn_to_servo(225) == (45, "reverse")     # behind and to the left
    assert turn_to_servo(90) == (0, "forward")       # exactly 90 right still drives forward
    assert turn_to_servo(270) == (180, "forward")    # exactly 90 left still drives forward


def test_rounds_to_5_degrees():
    assert turn_to_servo(12) == (80, "forward")      # servo 78 -> 80
    assert turn_to_servo(358) == (90, "forward")     # 2 left of the bow -> servo 92 -> 90
    assert turn_to_servo(3) == (85, "forward")       # servo 87 -> 85
    for t in range(0, 360):
        servo, _ = turn_to_servo(t + 0.37)
        assert 0 <= servo <= 180 and servo % 5 == 0, (t, servo)


def test_wraps_across_north():
    # Anchor due north, boat heading 350: anchor is 10 right -> servo 80
    a = anchored_at(BOAT_LAT + meters_north(20), BOAT_LON)
    r = anchor_target(a, reading(heading=350), now=1.0)
    assert (r["target_angle"], r["direction"]) == (80, "forward"), r
    # Heading 10: anchor is 10 left -> servo 100
    r = anchor_target(a, reading(heading=10), now=1.0)
    assert (r["target_angle"], r["direction"]) == (100, "forward"), r


def test_offset_vector():
    # 30 m north and 40 m east -> 50 m away, bearing 53.13
    north, east, distance, bearing = offset_to_anchor(
        BOAT_LAT, BOAT_LON, BOAT_LAT + meters_north(30), BOAT_LON + meters_east(40))
    assert abs(north - 30) < 0.01 and abs(east - 40) < 0.01
    assert abs(distance - 50) < 0.01
    assert abs(bearing - 53.13) < 0.01
    # Anchor south-west -> bearing 225
    _, _, _, bearing = offset_to_anchor(
        BOAT_LAT, BOAT_LON, BOAT_LAT - meters_north(5), BOAT_LON - meters_east(5))
    assert abs(bearing - 225) < 0.01


def test_longitude_scaled_by_latitude():
    # The same longitude change is fewer meters further from the equator
    _, east_low, _, _ = offset_to_anchor(0.0, 0.0, 0.0, 0.001)
    _, east_high, _, _ = offset_to_anchor(60.0, 0.0, 60.0, 0.001)
    assert abs(east_high - east_low / 2) < 0.01      # cos(60) = 0.5


def test_no_anchor():
    r = anchor_target(new_anchor(), reading(), now=5.0)
    assert r["status"] == STATUS_NO_ANCHOR
    assert all(r[k] is None for k in ("target_angle", "direction", "age", "distance", "bearing", "turn"))


def test_set_refuses_without_fix():
    a = new_anchor()
    assert not set_anchor(a, reading(lat=0.0, lon=0.0, fix=0), now=0.0)
    assert not set_anchor(a, None, now=0.0)          # no status line received yet
    assert a["saved_at"] is None


def test_no_fix_keeps_age_but_no_angle():
    a = anchored_at(BOAT_LAT, BOAT_LON + meters_east(10), now=100.0)
    r = anchor_target(a, reading(lat=0.0, lon=0.0, fix=0), now=112.5)
    assert r["status"] == STATUS_NO_FIX
    assert r["target_angle"] is None and r["direction"] is None and r["distance"] is None
    assert r["age"] == 12.5
    r = anchor_target(a, None, now=113.0)            # status["data"] still None
    assert r["status"] == STATUS_NO_FIX and r["age"] == 13.0


def test_compass_dead():
    a = anchored_at(BOAT_LAT, BOAT_LON + meters_east(10))
    r = anchor_target(a, reading(heading=-1), now=2.0)
    assert r["status"] == STATUS_COMPASS_DEAD
    assert r["target_angle"] is None and r["direction"] is None and r["turn"] is None
    assert abs(r["distance"] - 10) < 0.01            # distance needs no compass
    assert r["age"] == 2.0


def test_new_anchor_resets_age_and_clear_wipes_everything():
    a = anchored_at(BOAT_LAT, BOAT_LON, now=0.0)
    assert anchor_target(a, reading(), now=30.0)["age"] == 30.0
    assert set_anchor(a, reading(), now=30.0)
    assert anchor_target(a, reading(), now=31.0)["age"] == 1.0
    clear_anchor(a)
    r = anchor_target(a, reading(), now=40.0)
    assert r["status"] == STATUS_NO_ANCHOR and r["age"] is None and r["target_angle"] is None


def test_on_top_of_anchor():
    # Zero offset must not crash; atan2(0, 0) is 0 so it reads "straight north"
    a = anchored_at(BOAT_LAT, BOAT_LON)
    r = anchor_target(a, reading(heading=0), now=1.0)
    assert r["status"] == STATUS_OK and r["distance"] == 0


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for name, fn in tests:
        fn()
        print("PASS", name)
    print(f"\nAll {len(tests)} tests passed.")
