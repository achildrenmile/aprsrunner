# APRSRunner

Move an APRS object along a defined route via APRS-IS to advertise ham radio events. The object travels between waypoints with configurable speed and beacon interval, carrying an event message in the APRS comment field.

## Requirements

- Python 3.8+
- Amateur radio callsign with APRS-IS passcode

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

1. Copy and edit the config file:
   ```bash
   cp config.yaml myevent.yaml
   ```

2. Set your callsign and passcode in `myevent.yaml`

3. Test with dry-run mode:
   ```bash
   python aprsrunner.py --config myevent.yaml --dry-run -v
   ```

4. Run for real:
   ```bash
   python aprsrunner.py --config myevent.yaml
   ```

Press `Ctrl+C` to stop. A kill packet is sent automatically to remove the object from the map.

## Configuration

### `aprs_is` - APRS-IS Connection

| Key        | Required | Default              | Description                     |
|------------|----------|----------------------|---------------------------------|
| `callsign` | Yes      |                      | Your amateur radio callsign     |
| `passcode` | Yes      |                      | APRS-IS passcode                |
| `host`     | No       | `rotate.aprs2.net`   | APRS-IS server hostname         |
| `port`     | No       | `14580`              | APRS-IS server port             |

### `object` - APRS Object Settings

| Key            | Required | Default | Description                              |
|----------------|----------|---------|------------------------------------------|
| `name`         | Yes      |         | Object name, max 9 characters            |
| `symbol_table` | No       | `/`     | Symbol table (`/` = primary, `\` = alt)  |
| `symbol`       | No       | `r`     | Symbol code (e.g., `r` = antenna)        |
| `comment`      | No       | `""`    | Event message shown in APRS comment      |

### `movement` - Movement Settings

| Key               | Required | Default | Description                          |
|-------------------|----------|---------|--------------------------------------|
| `speed_kmh`       | No       | `25.0`  | Speed in km/h along route            |
| `beacon_interval` | No       | `120`   | Seconds between position beacons     |
| `loop`            | No       | `true`  | Restart route when finished          |

### `route` - Route Definition

Use **one** of the following:

**Inline waypoints** (list of `[lat, lon]` pairs):
```yaml
route:
  waypoints:
    - [40.7128, -74.0060]
    - [40.7580, -73.9855]
    - [40.7484, -73.9857]
```

**GPX file** (routes, tracks, or waypoints):
```yaml
route:
  gpx_file: "path/to/route.gpx"
```

GPX paths are resolved relative to the config file directory.

## CLI Options

```
usage: aprsrunner.py [-h] [-c CONFIG] [-v] [--dry-run]

options:
  -c, --config CONFIG  Path to config YAML file (default: config.yaml)
  -v, --verbose        Enable verbose/debug logging
  --dry-run            Print packets to stdout instead of transmitting
```

## APRS Symbol Reference

Common symbols for events:

| Table | Code | Description     |
|-------|------|-----------------|
| `/`   | `r`  | Antenna         |
| `/`   | `-`  | House            |
| `/`   | `k`  | School          |
| `\`   | `C`  | Club / event    |
| `/`   | `p`  | Rover           |

See the [APRS symbol table](http://www.aprs.org/symbols.html) for the full list.

## License

MIT
