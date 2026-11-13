"""The sensor contract.

A sensor is anything that can take one reading of where the kitchen is, what
the weather is doing, and what the soil is like. Mock and live sensors both
return the same ``SensorSnapshot``. The rest of Fallow never asks which one
it is talking to.
"""

from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, Field


class AirQuality(BaseModel):
    """Outdoor air at the garden. Units follow Open-Meteo / CAMS."""

    us_aqi: int = Field(ge=0)
    pm2_5: float | None = Field(default=None, ge=0)  # µg/m³
    pm10: float | None = Field(default=None, ge=0)  # µg/m³
    co2_ppm: float | None = Field(default=None, ge=0)
    carbon_monoxide: float | None = Field(default=None, ge=0)  # µg/m³
    ozone: float | None = Field(default=None, ge=0)  # µg/m³
    nitrogen_dioxide: float | None = Field(default=None, ge=0)  # µg/m³


def aqi_label(us_aqi: int) -> str:
    """US EPA AQI bands."""
    if us_aqi <= 50:
        return "Good"
    if us_aqi <= 100:
        return "Moderate"
    if us_aqi <= 150:
        return "Unhealthy for sensitive groups"
    if us_aqi <= 200:
        return "Unhealthy"
    if us_aqi <= 300:
        return "Very unhealthy"
    return "Hazardous"


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
    # Deeper soil and the rest of the weather. All optional: a sensor that
    # cannot read them leaves them out rather than guessing.
    soil_moisture_root: float | None = Field(default=None, ge=0, le=1)  # 9–27 cm
    soil_temp_c: float | None = None
    humidity_pct: float | None = Field(default=None, ge=0, le=100)
    wind_kph: float | None = Field(default=None, ge=0)
    rain_today_mm: float | None = Field(default=None, ge=0)
    air: AirQuality | None = None
    # Where this reading came from. "fallback" means the live feed failed
    # and a recorded reading stands in; ``note`` says why.
    source: Literal["mock", "live", "fallback"] = "mock"
    note: str = ""


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
