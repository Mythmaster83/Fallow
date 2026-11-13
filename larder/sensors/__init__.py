"""Sensor feed: a protocol, a fixture-backed mock, and a live Open-Meteo feed."""

from __future__ import annotations

import os

from larder.llm.client import load_project_env
from larder.sensors.base import LiveSensorUnavailable, Sensor, SensorSnapshot
from larder.sensors.live import LiveSensor
from larder.sensors.mock import MockSensor


class FallbackSensor:
    """Try the live feed; if it fails, serve the recorded reading and say so.

    The demo must never break because the venue wifi did.
    """

    def __init__(self, primary: Sensor, fallback: Sensor) -> None:
        self.primary = primary
        self.fallback = fallback

    def read(self) -> SensorSnapshot:
        try:
            return self.primary.read()
        except LiveSensorUnavailable as exc:
            backup = self.fallback.read()
            return backup.model_copy(
                update={
                    "source": "fallback",
                    "note": f"Live feed unavailable ({exc}). Showing the recorded reading.",
                }
            )


def live_from_env() -> LiveSensor:
    """Live sensor for the configured place, or the sample fixture's place."""
    sample = MockSensor().read()
    lat = os.environ.get("FALLOW_LATITUDE", "").strip()
    lon = os.environ.get("FALLOW_LONGITUDE", "").strip()
    name = os.environ.get("FALLOW_LOCATION", "").strip()
    try:
        latitude = float(lat) if lat else sample.latitude
        longitude = float(lon) if lon else sample.longitude
    except ValueError as exc:
        raise ValueError("FALLOW_LATITUDE and FALLOW_LONGITUDE must be numbers") from exc
    if latitude is None or longitude is None:
        raise ValueError("Set FALLOW_LATITUDE and FALLOW_LONGITUDE for the live sensor")
    return LiveSensor(latitude, longitude, name or sample.location)


def current_sensor() -> Sensor:
    """Build the sensor selected by ``SENSOR_MODE`` (``mock`` or ``live``).

    ``live`` reads Open-Meteo and falls back to the mock reading offline.
    """
    load_project_env()
    mode = os.environ.get("SENSOR_MODE", "mock").strip().lower() or "mock"
    if mode == "live":
        return FallbackSensor(live_from_env(), MockSensor())
    if mode == "mock":
        return MockSensor()
    raise ValueError("SENSOR_MODE must be 'mock' or 'live'")
