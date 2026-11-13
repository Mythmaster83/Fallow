"""Live location, weather, and soil from Open-Meteo.

Open-Meteo is a free forecast API with no key. One request returns the
current temperature, a WMO weather code, top-layer soil moisture and soil
temperature, and tonight's and tomorrow's lows (for frost).

``read`` never invents numbers. If the request fails or the reply is missing
a field, it raises ``LiveSensorUnavailable``; ``FallbackSensor`` in
``larder.sensors`` then serves the recorded mock reading instead and says so.

The kitchen's coordinates come from ``FALLOW_LATITUDE``, ``FALLOW_LONGITUDE``
and ``FALLOW_LOCATION``. Without them the sample fixture's place is used.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from larder.sensors.base import AirQuality, LiveSensorUnavailable, SensorSnapshot

API_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
CACHE_SECONDS = 600

# Volumetric water content (m³/m³) at which a loam is saturated. Dividing by
# this turns the API's reading into the 0..1 "how wet" scale the advisor uses,
# where under 0.3 counts as dry (roughly the wilting side of loam).
SATURATED_VWC = 0.45

# Frost is likely when the overnight low reaches this (ground frost forms
# a little above an air temperature of 0 °C).
FROST_LOW_C = 1.0

_WMO: list[tuple[range, str]] = [
    (range(0, 1), "Clear sky"),
    (range(1, 3), "Partly cloudy"),
    (range(3, 4), "Overcast"),
    (range(45, 49), "Fog"),
    (range(51, 58), "Drizzle"),
    (range(61, 68), "Rain"),
    (range(71, 78), "Snow"),
    (range(80, 83), "Rain showers"),
    (range(85, 87), "Snow showers"),
    (range(95, 100), "Thunderstorm"),
]

Fetch = Callable[[str, float], dict[str, Any]]
_cache: dict[str, tuple[float, SensorSnapshot]] = {}


def weather_label(code: int) -> str:
    for codes, label in _WMO:
        if code in codes:
            return label
    return f"Weather code {code}"


def soil_label(relative: float) -> str:
    if relative < 0.3:
        return "dry soil"
    if relative < 0.7:
        return "moist soil"
    return "wet soil"


def _http_fetch(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "fallow-planner"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload: object = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise LiveSensorUnavailable(f"Open-Meteo did not answer: {exc}") from exc
    if not isinstance(payload, dict):
        raise LiveSensorUnavailable("Open-Meteo returned something other than a JSON object.")
    return payload


class LiveSensor:
    """Read current conditions for one place from Open-Meteo."""

    def __init__(
        self,
        latitude: float,
        longitude: float,
        location: str,
        fetch: Fetch | None = None,
        timeout: float = 8.0,
        cache_seconds: float = CACHE_SECONDS,
    ) -> None:
        self.latitude = latitude
        self.longitude = longitude
        self.location = location
        self._fetch = fetch or _http_fetch
        self.timeout = timeout
        self.cache_seconds = cache_seconds

    def url(self) -> str:
        query = urllib.parse.urlencode(
            {
                "latitude": f"{self.latitude:.4f}",
                "longitude": f"{self.longitude:.4f}",
                "current": (
                    "temperature_2m,weather_code,relative_humidity_2m,wind_speed_10m,"
                    "soil_moisture_0_to_1cm,soil_moisture_9_to_27cm,soil_temperature_0cm,soil_temperature_6cm"
                ),
                "daily": "temperature_2m_min,precipitation_sum",
                "forecast_days": 2,
                "timezone": "auto",
            }
        )
        return f"{API_URL}?{query}"

    def air_url(self) -> str:
        query = urllib.parse.urlencode(
            {
                "latitude": f"{self.latitude:.4f}",
                "longitude": f"{self.longitude:.4f}",
                "current": "us_aqi,pm2_5,pm10,carbon_dioxide,carbon_monoxide,ozone,nitrogen_dioxide",
                "timezone": "auto",
            }
        )
        return f"{AIR_URL}?{query}"

    def read(self) -> SensorSnapshot:
        url = self.url()
        cached = _cache.get(url)
        if cached and time.monotonic() - cached[0] < self.cache_seconds:
            return cached[1]
        snapshot = self.parse(self._fetch(url, self.timeout))
        try:
            air = self.parse_air(self._fetch(self.air_url(), self.timeout))
        except LiveSensorUnavailable:
            air = None  # weather and soil still count without the air reading
        snapshot = snapshot.model_copy(
            update={"air": air, "co2_ppm": air.co2_ppm if air is not None else None}
        )
        _cache[url] = (time.monotonic(), snapshot)
        return snapshot

    @staticmethod
    def parse_air(payload: dict[str, Any]) -> AirQuality:
        """Turn an Open-Meteo air-quality reply into readings, or refuse."""
        try:
            current = payload["current"]
            aqi = current["us_aqi"]
            if aqi is None:
                raise KeyError("us_aqi")

            def opt(key: str) -> float | None:
                value = current.get(key)
                return None if value is None else float(value)

            return AirQuality(
                us_aqi=int(aqi),
                pm2_5=opt("pm2_5"),
                pm10=opt("pm10"),
                co2_ppm=opt("carbon_dioxide"),
                carbon_monoxide=opt("carbon_monoxide"),
                ozone=opt("ozone"),
                nitrogen_dioxide=opt("nitrogen_dioxide"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise LiveSensorUnavailable(f"Air-quality reply is missing a field: {exc}") from exc

    def parse(self, payload: dict[str, Any]) -> SensorSnapshot:
        """Turn an Open-Meteo reply into a snapshot, or refuse."""
        try:
            current = payload["current"]
            offset = timedelta(seconds=int(payload.get("utc_offset_seconds", 0)))
            captured = datetime.fromisoformat(str(current["time"])).replace(tzinfo=timezone(offset))
            temp = float(current["temperature_2m"])
            code = int(current["weather_code"])
            lows = [float(v) for v in payload["daily"]["temperature_2m_min"] if v is not None]
            raw_moisture = current.get("soil_moisture_0_to_1cm")
            raw_root = current.get("soil_moisture_9_to_27cm")
            soil_temp = current.get("soil_temperature_0cm")
            soil_temp_6 = current.get("soil_temperature_6cm")
            humidity = current.get("relative_humidity_2m")
            wind = current.get("wind_speed_10m")
            rain = payload["daily"].get("precipitation_sum") or [None]
        except (KeyError, TypeError, ValueError) as exc:
            raise LiveSensorUnavailable(f"Open-Meteo reply is missing a field: {exc}") from exc
        if not lows:
            raise LiveSensorUnavailable("Open-Meteo reply has no overnight low.")

        moisture: float | None = None
        condition = "soil reading unavailable"
        if raw_moisture is not None:
            moisture = max(0.0, min(1.0, float(raw_moisture) / SATURATED_VWC))
            condition = soil_label(moisture)
            if soil_temp is not None:
                condition = f"{condition}, {round(float(soil_temp))} °C"

        low = min(lows)
        weather = weather_label(code)
        return SensorSnapshot(
            captured_at=captured,
            location=self.location,
            latitude=self.latitude,
            longitude=self.longitude,
            weather=f"{weather}, low {round(low)} °C",
            temp_c=temp,
            soil_condition=condition,
            soil_moisture=moisture,
            frost_risk=low <= FROST_LOW_C,
            soil_moisture_root=None if raw_root is None else max(0.0, min(1.0, float(raw_root) / SATURATED_VWC)),
            soil_temp_c=None if soil_temp_6 is None else float(soil_temp_6),
            humidity=None if humidity is None else max(0.0, min(1.0, float(humidity) / 100)),
            wind_kph=None if wind is None else float(wind),
            rain_today_mm=None if rain[0] is None else float(rain[0]),
            source="live",
        )
