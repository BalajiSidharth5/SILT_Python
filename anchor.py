"""GPS anchor (station keeping) for the pilot console.

Pure math, no controller or UI code. main.py saves the anchor on Triangle,
clears it on X, and calls anchor_target() once per pass with status["data"].

Directions are compass degrees: north is 0, east is 90.
Servo scale: 0 is full right, 90 is straight ahead, 180 is full left.
"""

import math
import time

METERS_PER_DEG_LAT = 111_320.0   # one degree of latitude, in meters

STATUS_OK = "ok"
STATUS_NO_FIX = "no fix"
STATUS_COMPASS_DEAD = "compass dead"
STATUS_NO_ANCHOR = "no anchor"


def new_anchor():
    """Anchor state for main.py. lat/lon/saved_at are None until Triangle saves one."""
    return {"lat": None, "lon": None, "saved_at": None}


def has_fix(data):
    return data is not None and data["fix"] != 0


def set_anchor(anchor, data, now=None):
    """Save the boat's current position as the anchor. Refuses (returns False) without a GPS fix.
    Saving again replaces the old anchor and restarts the age count."""
    if not has_fix(data):
        return False
    anchor["lat"] = data["lat"]
    anchor["lon"] = data["lon"]
    anchor["saved_at"] = time.monotonic() if now is None else now
    return True


def clear_anchor(anchor):
    anchor["lat"] = None
    anchor["lon"] = None
    anchor["saved_at"] = None


def offset_to_anchor(lat, lon, anchor_lat, anchor_lon):
    """Vector from the boat to the anchor in meters: (north, east, distance, bearing).
    Longitude degrees shrink toward the poles, so east is scaled by cos(latitude)."""
    north = (anchor_lat - lat) * METERS_PER_DEG_LAT
    east = (anchor_lon - lon) * METERS_PER_DEG_LAT * math.cos(math.radians(lat))
    distance = math.hypot(north, east)
    bearing = math.degrees(math.atan2(east, north)) % 360
    return north, east, distance, bearing


def round_to_5(angle):
    return int(math.floor(angle / 5 + 0.5)) * 5


def turn_to_servo(turn):
    """Turn the anchor's direction relative to the bow (0 to 360, clockwise) into
    (servo angle, "forward" or "reverse").

    Within 90 degrees either side of the bow the boat drives forward toward it.
    Anything further behind is out of the servo's range, so the thrusters point
    the opposite way and the boat backs toward the anchor instead."""
    signed = (turn + 180) % 360 - 180        # -180 to 180, right is positive
    if -90 <= signed <= 90:
        direction = "forward"
    else:
        direction = "reverse"
        signed = (signed + 360) % 360 - 180  # aim the stern at the anchor
    servo = round_to_5(90 - signed)
    return max(0, min(180, servo)), direction


def anchor_target(anchor, data, now=None):
    """One reading in, one answer out. Always returns every key; values the
    current status cannot give are None.

    status:       "ok", "no fix", "compass dead" or "no anchor"
    target_angle: servo angle 0 to 180 in steps of 5, or None
    direction:    "forward", "reverse" or None
    age:          seconds since the anchor was saved, or None without an anchor
    distance:     meters to the anchor, or None without a fix
    bearing:      compass direction from the boat to the anchor, or None without a fix
    turn:         anchor direction relative to the bow, 0 to 360 clockwise, or None
    """
    result = {"status": STATUS_NO_ANCHOR, "target_angle": None, "direction": None,
              "age": None, "distance": None, "bearing": None, "turn": None}

    if anchor["saved_at"] is None:
        return result
    now = time.monotonic() if now is None else now
    result["age"] = now - anchor["saved_at"]   # keeps counting while the fix is lost

    if not has_fix(data):
        result["status"] = STATUS_NO_FIX
        return result

    _, _, distance, bearing = offset_to_anchor(data["lat"], data["lon"], anchor["lat"], anchor["lon"])
    result["distance"] = distance
    result["bearing"] = bearing

    if data["heading"] == -1:
        result["status"] = STATUS_COMPASS_DEAD
        return result

    turn = (bearing - data["heading"]) % 360
    result["turn"] = turn
    result["target_angle"], result["direction"] = turn_to_servo(turn)
    result["status"] = STATUS_OK
    return result
