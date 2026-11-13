"""Short warnings for weather and soil that are hard on a garden."""

from __future__ import annotations

from larder.sensors.base import SensorSnapshot


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
    return notes
