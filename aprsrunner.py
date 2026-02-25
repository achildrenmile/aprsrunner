#!/usr/bin/env python3
"""APRSRunner - Move an APRS object along a route via APRS-IS."""

import argparse
import json
import logging
import math
import os
import random
import signal
import sys
import time
from pathlib import Path

import aprslib
import gpxpy
import yaml

log = logging.getLogger("aprsrunner")

EARTH_RADIUS_KM = 6371.0


# ---------------------------------------------------------------------------
# Geodesic math
# ---------------------------------------------------------------------------

def haversine_distance(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between two points."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def intermediate_point(lat1, lon1, lat2, lon2, fraction):
    """Interpolate a point along the great-circle path between two points.

    fraction: 0.0 = start, 1.0 = end
    Returns (lat, lon) in degrees.
    """
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    d = 2 * math.asin(math.sqrt(
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    ))
    if d < 1e-12:
        return math.degrees(lat1), math.degrees(lon1)

    a = math.sin((1 - fraction) * d) / math.sin(d)
    b = math.sin(fraction * d) / math.sin(d)

    x = a * math.cos(lat1) * math.cos(lon1) + b * math.cos(lat2) * math.cos(lon2)
    y = a * math.cos(lat1) * math.sin(lon1) + b * math.cos(lat2) * math.sin(lon2)
    z = a * math.sin(lat1) + b * math.sin(lat2)

    lat = math.atan2(z, math.sqrt(x ** 2 + y ** 2))
    lon = math.atan2(y, x)
    return math.degrees(lat), math.degrees(lon)


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

class Route:
    """A route defined by waypoints with distance-based interpolation."""

    def __init__(self, waypoints):
        """waypoints: list of (lat, lon) tuples."""
        if len(waypoints) < 2:
            raise ValueError("Route needs at least 2 waypoints")
        self.waypoints = waypoints
        self.cumulative = [0.0]
        for i in range(1, len(waypoints)):
            seg = haversine_distance(
                waypoints[i - 1][0], waypoints[i - 1][1],
                waypoints[i][0], waypoints[i][1],
            )
            self.cumulative.append(self.cumulative[-1] + seg)
        self.total_distance = self.cumulative[-1]
        log.info("Route: %d waypoints, %.2f km total", len(waypoints), self.total_distance)

    def position_at_distance(self, km):
        """Return (lat, lon) at the given distance along the route.

        Clamps to route bounds.
        """
        km = max(0.0, min(km, self.total_distance))
        for i in range(1, len(self.cumulative)):
            if km <= self.cumulative[i]:
                seg_start = self.cumulative[i - 1]
                seg_len = self.cumulative[i] - seg_start
                if seg_len < 1e-12:
                    return self.waypoints[i]
                frac = (km - seg_start) / seg_len
                return intermediate_point(
                    self.waypoints[i - 1][0], self.waypoints[i - 1][1],
                    self.waypoints[i][0], self.waypoints[i][1],
                    frac,
                )
        return self.waypoints[-1]


# ---------------------------------------------------------------------------
# APRS formatting (APRS101 spec)
# ---------------------------------------------------------------------------

def format_latitude(lat):
    """Format latitude as DDmm.mmN/S per APRS101."""
    hemisphere = "N" if lat >= 0 else "S"
    lat = abs(lat)
    degrees = int(lat)
    minutes = (lat - degrees) * 60
    return f"{degrees:02d}{minutes:05.2f}{hemisphere}"


def format_longitude(lon):
    """Format longitude as DDDmm.mmE/W per APRS101."""
    hemisphere = "E" if lon >= 0 else "W"
    lon = abs(lon)
    degrees = int(lon)
    minutes = (lon - degrees) * 60
    return f"{degrees:03d}{minutes:05.2f}{hemisphere}"


def pad_object_name(name):
    """Pad object name to exactly 9 characters per APRS101."""
    return name[:9].ljust(9)


def build_object_packet(callsign, name, lat, lon, symbol_table, symbol, comment):
    """Build an APRS object packet per APRS101 Chapter 11.

    Format: CALL>APRS:;NAME_____*DDmm.mmNSYMDDDmm.mmWCOMMENT
    """
    padded = pad_object_name(name)
    timestamp = time.strftime("%d%H%Mz", time.gmtime())
    lat_str = format_latitude(lat)
    lon_str = format_longitude(lon)
    data = f";{padded}*{timestamp}{lat_str}{symbol_table}{lon_str}{symbol}{comment}"
    return f"{callsign}>APRS,TCPIP*:{data}"


def build_kill_packet(callsign, name):
    """Build a kill packet to remove an object from the map.

    Uses '_' (underscore) after the padded name to indicate a killed object.
    """
    padded = pad_object_name(name)
    timestamp = time.strftime("%d%H%Mz", time.gmtime())
    data = f";{padded}_{timestamp}"
    return f"{callsign}>APRS,TCPIP*:{data}"


# ---------------------------------------------------------------------------
# GPX loading
# ---------------------------------------------------------------------------

def load_gpx_waypoints(gpx_path):
    """Extract waypoints from a GPX file (routes > tracks > waypoints)."""
    path = Path(gpx_path)
    if not path.exists():
        raise FileNotFoundError(f"GPX file not found: {gpx_path}")
    with open(path) as f:
        gpx = gpxpy.parse(f)

    points = []

    # Prefer routes
    for route in gpx.routes:
        for pt in route.points:
            points.append((pt.latitude, pt.longitude))
    if points:
        log.info("Loaded %d points from GPX routes", len(points))
        return points

    # Fall back to tracks
    for track in gpx.tracks:
        for segment in track.segments:
            for pt in segment.points:
                points.append((pt.latitude, pt.longitude))
    if points:
        log.info("Loaded %d points from GPX tracks", len(points))
        return points

    # Fall back to waypoints
    for pt in gpx.waypoints:
        points.append((pt.latitude, pt.longitude))
    if points:
        log.info("Loaded %d points from GPX waypoints", len(points))
        return points

    raise ValueError(f"No points found in GPX file: {gpx_path}")


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_config(config_path):
    """Load and validate configuration from YAML file."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(path) as f:
        cfg = yaml.safe_load(f)

    # Validate required sections
    for section in ("aprs_is", "object", "movement", "route"):
        if section not in cfg:
            raise ValueError(f"Missing config section: {section}")

    # Apply defaults
    aprs = cfg["aprs_is"]
    aprs.setdefault("host", "rotate.aprs2.net")
    aprs.setdefault("port", 14580)

    # Environment variable overrides (for Docker secrets)
    if os.environ.get("APRS_CALLSIGN"):
        aprs["callsign"] = os.environ["APRS_CALLSIGN"]
    if os.environ.get("APRS_PASSCODE"):
        aprs["passcode"] = os.environ["APRS_PASSCODE"]

    if not aprs.get("callsign"):
        raise ValueError("aprs_is.callsign is required")
    if not aprs.get("passcode"):
        raise ValueError("aprs_is.passcode is required")

    obj = cfg["object"]
    if not obj.get("name"):
        raise ValueError("object.name is required")
    if len(obj["name"]) > 9:
        raise ValueError("object.name must be 9 characters or fewer")
    obj.setdefault("symbol_table", "/")
    obj.setdefault("symbol", "r")
    obj.setdefault("comment", "")
    obj.setdefault("comments", [])

    mov = cfg["movement"]
    mov.setdefault("speed_kmh", 25.0)
    mov.setdefault("beacon_interval", 120)
    mov.setdefault("loop", True)

    # Load waypoints
    route_cfg = cfg["route"]
    if route_cfg.get("gpx_file"):
        gpx_path = route_cfg["gpx_file"]
        # Resolve relative to config file directory
        if not Path(gpx_path).is_absolute():
            gpx_path = str(path.parent / gpx_path)
        waypoints = load_gpx_waypoints(gpx_path)
    elif route_cfg.get("waypoints"):
        waypoints = [(pt[0], pt[1]) for pt in route_cfg["waypoints"]]
    else:
        raise ValueError("route.waypoints or route.gpx_file is required")

    if len(waypoints) < 2:
        raise ValueError("Route needs at least 2 waypoints")

    cfg["_waypoints"] = waypoints
    return cfg


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def load_state(state_file):
    """Load current_distance from state file, return 0.0 if missing/invalid."""
    try:
        with open(state_file) as f:
            data = json.load(f)
        distance = float(data.get("current_distance", 0.0))
        log.info("Resumed from state file: %.2f km", distance)
        return distance
    except (FileNotFoundError, json.JSONDecodeError, ValueError, TypeError):
        return 0.0


def save_state(state_file, current_distance):
    """Write current_distance to state file."""
    with open(state_file, "w") as f:
        json.dump({"current_distance": current_distance}, f)


def run(cfg, dry_run=False, state_file=None):
    """Main runner: connect to APRS-IS and beacon the object along the route."""
    aprs_cfg = cfg["aprs_is"]
    obj_cfg = cfg["object"]
    mov_cfg = cfg["movement"]
    waypoints = cfg["_waypoints"]

    route = Route(waypoints)
    speed_kmh = mov_cfg["speed_kmh"]
    interval = mov_cfg["beacon_interval"]
    loop = mov_cfg["loop"]
    distance_per_tick = speed_kmh * (interval / 3600.0)

    callsign = aprs_cfg["callsign"]
    obj_name = obj_cfg["name"]

    # State — resume from state file if available
    current_distance = 0.0
    if state_file:
        current_distance = load_state(state_file)
        if current_distance >= route.total_distance:
            current_distance = 0.0
    running = True

    def shutdown(signum, frame):
        nonlocal running
        log.info("Shutdown signal received, sending kill packet...")
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Connect
    ais = None
    if not dry_run:
        ais = aprslib.IS(callsign, passwd=str(aprs_cfg["passcode"]),
                         host=aprs_cfg["host"], port=aprs_cfg["port"])
        log.info("Connecting to APRS-IS %s:%d as %s...",
                 aprs_cfg["host"], aprs_cfg["port"], callsign)
        ais.connect()
        log.info("Connected to APRS-IS")
    else:
        log.info("DRY RUN - not connecting to APRS-IS")

    comments = obj_cfg.get("comments") or [obj_cfg["comment"]]

    try:
        while running:
            lat, lon = route.position_at_distance(current_distance)
            comment = random.choice(comments)
            packet = build_object_packet(
                callsign, obj_name, lat, lon,
                obj_cfg["symbol_table"], obj_cfg["symbol"], comment,
            )

            log.info("Distance: %.2f/%.2f km | Position: %.5f, %.5f",
                     current_distance, route.total_distance, lat, lon)
            log.debug("Packet: %s", packet)

            if dry_run:
                print(f"TX: {packet}")
            else:
                ais.sendall(packet)
                log.info("Beacon sent")

            # Advance
            current_distance += distance_per_tick

            # Check if route is complete
            if current_distance >= route.total_distance:
                if loop:
                    current_distance = 0.0
                    log.info("Route complete, looping...")
                else:
                    log.info("Route complete, stopping")
                    break

            # Persist state after each beacon
            if state_file:
                save_state(state_file, current_distance)

            # Wait for next beacon
            if running:
                log.debug("Sleeping %d seconds...", interval)
                for _ in range(interval):
                    if not running:
                        break
                    time.sleep(1)

    finally:
        # Send kill packet on exit
        kill = build_kill_packet(callsign, obj_name)
        log.info("Sending kill packet to remove object from map")
        log.debug("Kill packet: %s", kill)
        if dry_run:
            print(f"TX: {kill}")
        else:
            try:
                ais.sendall(kill)
            except Exception:
                log.warning("Failed to send kill packet")
            ais.close()
        # Keep state file so the dog resumes on restart/rollout
        if state_file:
            save_state(state_file, current_distance)
        log.info("Done")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Move an APRS object along a route via APRS-IS",
    )
    parser.add_argument(
        "-c", "--config", default="config.yaml",
        help="Path to config YAML file (default: config.yaml)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable verbose/debug logging",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print packets to stdout instead of transmitting",
    )
    parser.add_argument(
        "--state-file",
        help="Path to state file for restart resilience (JSON)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        cfg = load_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        log.error("Config error: %s", e)
        sys.exit(1)

    run(cfg, dry_run=args.dry_run, state_file=args.state_file)


if __name__ == "__main__":
    main()
