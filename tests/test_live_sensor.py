"""The Open-Meteo sensor: parsing, frost, soil, and the offline fallback.

No network: every test hands the sensor a canned reply or a failing fetch.
"""

from typing import Any

import pytest

from larder.grow.advisor import advise
from larder.sensors import FallbackSensor
from larder.sensors.base import LiveSensorUnavailable
from larder.sensors.live import LiveSensor
from larder.sensors.mock import MockSensor


def _reply(temp: float = 2.9, code: int = 3, moisture: float | None = 0.275, lows: list[float] | None = None) -> dict[str, Any]:
    return {
        "utc_offset_seconds": -18000,
        "current": {
            "time": "2026-11-13T13:30",
            "temperature_2m": temp,
            "weather_code": code,
            "soil_moisture_0_to_1cm": moisture,
            "soil_temperature_0cm": 4.2,
        },
        "daily": {"time": ["2026-11-13", "2026-11-14"], "temperature_2m_min": lows or [1.2, -0.1]},
    }


def _sensor(payload: dict[str, Any] | Exception) -> LiveSensor:
    def fetch(url: str, timeout: float) -> dict[str, Any]:
        assert "api.open-meteo.com" in url
        if isinstance(payload, Exception):
            raise payload
        return payload

    return LiveSensor(41.7, -73.93, "Hudson Valley, NY", fetch=fetch, cache_seconds=0)


def test_parses_a_real_shaped_reply() -> None:
    snap = _sensor(_reply()).read()
    assert snap.source == "live"
    assert snap.temp_c == pytest.approx(2.9)
    assert snap.weather.startswith("Overcast")
    assert snap.frost_risk  # tomorrow's low is below zero
    assert snap.soil_moisture == pytest.approx(0.275 / 0.45)
    assert snap.soil_condition.startswith("moist soil")
    assert snap.captured_at.utcoffset() is not None


def test_mild_nights_are_not_frost() -> None:
    assert not _sensor(_reply(lows=[6.0, 7.5])).read().frost_risk


def test_dry_topsoil_reads_dry_and_the_advisor_reacts() -> None:
    snap = _sensor(_reply(moisture=0.08, lows=[6.0, 7.0])).read()
    assert snap.soil_condition.startswith("dry soil")
    assert "thyme" in [crop.crop for crop in advise(snap)]


def test_missing_soil_reading_is_not_invented() -> None:
    snap = _sensor(_reply(moisture=None)).read()
    assert snap.soil_moisture is None
    assert snap.soil_condition == "soil reading unavailable"


def test_broken_reply_refuses_instead_of_guessing() -> None:
    with pytest.raises(LiveSensorUnavailable):
        _sensor({"current": {}}).read()


def test_offline_falls_back_to_the_recorded_reading() -> None:
    sensor = FallbackSensor(_sensor(LiveSensorUnavailable("no network")), MockSensor())
    snap = sensor.read()
    assert snap.source == "fallback"
    assert "no network" in snap.note
    assert snap.location == MockSensor().read().location
