"""Small local proxy for OpenAQ station readings; keeps the API key off the page."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
import json
import math
import os
from pathlib import Path
import threading
import time
import webbrowser


BASE_DIR = Path(__file__).resolve().parent
PORT = int(os.environ.get("PORT", "8123"))
CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".config"))) / "AirScope"
CONFIG_FILE = CONFIG_DIR / "openaq.env"
STATION_CACHE = {}
STATION_CACHE_LOCK = threading.Lock()
STATION_CACHE_SECONDS = 90


def load_local_env():
    env_file = CONFIG_FILE
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip().strip("\"'")
        if name and value:
            os.environ.setdefault(name, value)


load_local_env()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def send_json(self, status, body):
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/stations":
            return self.station_readings(parse_qs(parsed.query))
        if parsed.path == "/api/health":
            return self.send_json(200, {"ok": True, "api_key_configured": bool(os.environ.get("OPENAQ_API_KEY"))})
        return super().do_GET()

    def station_readings(self, query):
        api_key = os.environ.get("OPENAQ_API_KEY", "").strip()
        if not api_key:
            return self.send_json(503, {
                "error": "OpenAQ API key is not set. Add it to the local .env file, then restart this server.",
                "key_required": True,
            })
        try:
            lat = float(query.get("latitude", [""])[0])
            lon = float(query.get("longitude", [""])[0])
            if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError
        except (ValueError, TypeError):
            return self.send_json(400, {"error": "A valid latitude and longitude are required."})

        cache_key = (round(lat, 2), round(lon, 2))
        now = time.monotonic()
        with STATION_CACHE_LOCK:
            cached = STATION_CACHE.get(cache_key)
            if cached and now - cached[0] < STATION_CACHE_SECONDS:
                return self.send_json(200, cached[1])

        try:
            params = urlencode({"coordinates": f"{lat:.4f},{lon:.4f}", "radius": 25000, "limit": 100, "page": 1})
            locations = self.openaq_get(f"https://api.openaq.org/v3/locations?{params}").get("results", [])
            locations = sorted(
                (loc for loc in locations if loc.get("coordinates") and loc["coordinates"].get("latitude") is not None),
                key=lambda loc: loc.get("distance") if loc.get("distance") is not None else 1e12,
            )[:4]
            stations = []
            with ThreadPoolExecutor(max_workers=6) as pool:
                futures = {pool.submit(self.fetch_location, loc): loc for loc in locations}
                for future in as_completed(futures):
                    try:
                        station = future.result()
                    except (HTTPError, URLError, TimeoutError, ValueError, KeyError):
                        continue
                    if station and station["measurements"]:
                        stations.append(station)
            stations.sort(key=lambda item: item.get("distance_m") if item.get("distance_m") is not None else 1e12)
            result = {"stations": stations, "radius_m": 25000, "source": "OpenAQ"}
            with STATION_CACHE_LOCK:
                STATION_CACHE[cache_key] = (time.monotonic(), result)
            return self.send_json(200, result)
        except HTTPError as exc:
            message = "OpenAQ rejected the request. Check that the API key is valid."
            if exc.code == 429:
                message = "OpenAQ request limit reached. Please wait a minute and try again."
            return self.send_json(502, {"error": message})
        except (URLError, TimeoutError):
            return self.send_json(502, {"error": "Could not reach OpenAQ. Check your internet and try again."})
        except Exception:
            return self.send_json(502, {"error": "Station readings could not be loaded right now."})

    def openaq_get(self, url):
        request = Request(url, headers={"X-API-Key": os.environ["OPENAQ_API_KEY"], "Accept": "application/json"})
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def fetch_location(self, loc):
        location_id = loc["id"]
        data = self.openaq_get(f"https://api.openaq.org/v3/locations/{location_id}/latest?limit=100&page=1")
        sensors = {sensor.get("id"): sensor for sensor in loc.get("sensors", [])}
        measurements = []
        for reading in data.get("results", []):
            sensor = sensors.get(reading.get("sensorsId"), {})
            parameter = sensor.get("parameter", {})
            name = parameter.get("displayName") or parameter.get("name") or sensor.get("name")
            value = reading.get("value")
            if not name or not isinstance(value, (int, float)):
                continue
            measurements.append({
                "name": str(name),
                "value": value,
                "units": sensor.get("units") or parameter.get("units") or "",
                "time": (reading.get("datetime") or {}).get("local") or (reading.get("datetime") or {}).get("utc"),
            })
        coordinates = loc.get("coordinates") or {}
        return {
            "id": location_id,
            "name": loc.get("name") or loc.get("locality") or "Monitoring station",
            "locality": loc.get("locality"),
            "provider": (loc.get("provider") or {}).get("name"),
            "owner": (loc.get("owner") or {}).get("name"),
            "is_monitor": bool(loc.get("isMonitor")),
            "distance_m": loc.get("distance"),
            "latitude": coordinates.get("latitude"),
            "longitude": coordinates.get("longitude"),
            "last_reported": ((loc.get("datetimeLast") or {}).get("local") or (loc.get("datetimeLast") or {}).get("utc")),
            "measurements": measurements,
        }


if __name__ == "__main__":
    print(f"AirScope station dashboard: http://127.0.0.1:{PORT}/")
    print("Press Ctrl+C here to stop the server.")
    threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}/")).start()
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
