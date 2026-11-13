"""The sensor contract.

A sensor is anything that can take one reading of where the kitchen is, what
the weather is doing, and what the soil is like. Mock and live sensors both
return the same ``SensorSnapshot``. The rest of Fallow never asks which one
it is talking to.
"""

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, Field


class SensorSnapshot(BaseModel):
    """One reading of place, weather, and soil."""

    captured_at: datetime
    location: str = Field(min_length=1)
    latitude: float | None = None
    longitude: float | None = None
    weather: str = Field(min_length=1)
    temp_c: float
    soil_condition: str = Field(min_length=1)
    soil_moisture: float | None = Field(default=None, ge=0, le=1)
    frost_risk: bool
    # Optional site-station readings. A feed that lacks them leaves them None.
    humidity: float | None = Field(default=None, ge=0, le=1)
    co2_ppm: float | None = Field(default=None, ge=0)
    radiation_usv_h: float | None = Field(default=None, ge=0)


class Sensor(Protocol):
    """Read the world once and return a snapshot.

    Implementations must not guess missing numbers. If the feed cannot be
    read, raise ``LiveSensorUnavailable`` (or a subclass of ``Exception``)
    instead of inventing a forecast.
    """

    def read(self) -> SensorSnapshot:
        """Return the current snapshot."""


class LiveSensorUnavailable(Exception):
    """The live feed is not ready, or it failed to produce a reading."""
