"""Sensor that reads a JSON fixture instead of hardware.

``SENSOR_MODE=mock`` uses ``fixtures/sensor.sample.json``. Swap the path in
tests or in a demo when you want a different season.
"""

from __future__ import annotations

import json
from pathlib import Path

from larder import project_root
from larder.sensors.base import SensorSnapshot


class MockSensor:
    """Return the same recorded reading every time ``read`` is called."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (project_root() / "fixtures" / "sensor.sample.json")

    def read(self) -> SensorSnapshot:
        if not self.path.is_file():
            raise FileNotFoundError(f"Mock sensor fixture not found: {self.path}")
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return SensorSnapshot.model_validate(payload)
