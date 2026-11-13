"""Sensor feed: a protocol, a fixture-backed mock, and a live slot."""

from __future__ import annotations

import os

from larder.llm.client import load_project_env
from larder.sensors.base import Sensor


def current_sensor() -> Sensor:
    """Build the sensor selected by ``SENSOR_MODE`` (``mock`` or ``live``)."""
    load_project_env()
    mode = os.environ.get("SENSOR_MODE", "mock").strip().lower() or "mock"
    if mode == "live":
        from larder.sensors.live import LiveSensor

        return LiveSensor()
    if mode == "mock":
        from larder.sensors.mock import MockSensor

        return MockSensor()
    raise ValueError("SENSOR_MODE must be 'mock' or 'live'")
