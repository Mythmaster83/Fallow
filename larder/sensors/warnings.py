"""Short warnings for weather and soil that are hard on a garden."""

from __future__ import annotations

from larder.sensors.base import SensorSnapshot, aqi_label

HEAVY_RAIN_MM = 20.0
HIGH_WIND_KPH = 50.0
SMOKE_PM25 = 35.0  # µg/m³, the US EPA 24-hour standard


def condition_warnings(snapshot: SensorSnapshot) -> list[str]:
    """Return the unusual conditions worth a small banner note.

    An ordinary cool day returns nothing. Frost, a freeze, a storm, and soil
    that is very dry or very wet each add one short line.
    """
    notes: list[str] = []
    weather = snapshot.weather.lower()
    if snapshot.frost_risk or snapshot.temp_c <= 0:
        notes.append("Frost overnight")
    elif snapshot.temp_c <= 2:
        notes.append("Near freezing")
    if snapshot.temp_c >= 32:
        notes.append("Extreme heat")
    if "thunder" in weather or "storm" in weather:
        notes.append("Storm")
    if "snow" in weather:
        notes.append("Snow")
    if "fog" in weather:
        notes.append("Fog")
    moisture = snapshot.soil_moisture
    if moisture is not None and moisture < 0.3:
        notes.append("Soil is dry")
    elif moisture is not None and moisture > 0.75:
        notes.append("Soil is waterlogged")
    root = snapshot.soil_moisture_root
    if root is not None and root < 0.3 and not (moisture is not None and moisture < 0.3):
        notes.append("Root zone is dry")
    if snapshot.rain_today_mm is not None and snapshot.rain_today_mm >= HEAVY_RAIN_MM:
        notes.append("Heavy rain")
    if snapshot.wind_kph is not None and snapshot.wind_kph >= HIGH_WIND_KPH:
        notes.append("High wind")
    air = snapshot.air
    if air is not None:
        if air.us_aqi > 100:
            notes.append(f"Air: {aqi_label(air.us_aqi).lower()}")
        elif air.pm2_5 is not None and air.pm2_5 > SMOKE_PM25:
            notes.append("Smoke or dust in the air")
    return notes
