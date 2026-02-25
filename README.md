# APRSRunner

Move an APRS object along a defined route via APRS-IS to advertise ham radio events. The object travels between waypoints with configurable speed and beacon interval, carrying an event message in the APRS comment field.

## Requirements

- Python 3.8+
- Amateur radio callsign with APRS-IS passcode

## Quick Start

### Local

```bash
pip install -r requirements.txt
cp config.yaml myevent.yaml
# Edit myevent.yaml with your callsign, passcode, route, etc.
python aprsrunner.py --config myevent.yaml --dry-run -v
python aprsrunner.py --config myevent.yaml
```

Press `Ctrl+C` to stop. A kill packet is sent automatically to remove the object from the map.

### Docker

```bash
docker build -t aprsrunner .
docker run -d --name aprsrunner --restart unless-stopped \
  -e APRS_CALLSIGN=OE8YML-11 \
  -e APRS_PASSCODE=12345 \
  aprsrunner
```

Or with docker compose:

```bash
APRS_CALLSIGN=OE8YML-11 APRS_PASSCODE=12345 docker compose up -d
```

The default Dockerfile uses `config-carinthia.yaml`. Override with:

```bash
docker run --rm -e APRS_CALLSIGN=N0CALL -e APRS_PASSCODE=12345 \
  aprsrunner --config config.yaml
```

## Environment Variables

Environment variables override values from the config file, keeping secrets out of YAML:

| Variable         | Overrides            |
|------------------|----------------------|
| `APRS_CALLSIGN`  | `aprs_is.callsign`  |
| `APRS_PASSCODE`  | `aprs_is.passcode`  |

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

## Included Configs

| File | Route | Description |
|------|-------|-------------|
| `config.yaml` | New York City | Example config with NYC landmarks |
| `config-carinthia.yaml` | Carinthia, Austria | ~224 km loop: Klagenfurt → Gailtal → Plöckenpass → Drautal → Klagenfurt |

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
| `/`   | `-`  | House           |
| `/`   | `k`  | School          |
| `\`   | `C`  | Club / event    |
| `/`   | `p`  | Dog / rover     |
| `/`   | `e`  | Horse           |
| `/`   | `b`  | Bicycle         |
| `/`   | `[`  | Jogger          |

See the [APRS symbol table](http://www.aprs.org/symbols.html) for the full list.

## License

MIT
