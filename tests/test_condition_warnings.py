"""Unusual weather notes and the sample wearable reading."""

from larder.health.vitals import load_vitals, stress_label
from larder.sensors.mock import MockSensor
from larder.sensors.warnings import condition_warnings


def test_sample_weather_warns_about_frost() -> None:
    notes = condition_warnings(MockSensor().read())
    assert "Frost overnight" in notes
    assert "Soil is dry" not in notes


def test_dry_soil_and_heat_are_separate_notes() -> None:
    snapshot = MockSensor().read().model_copy(
        update={"frost_risk": False, "temp_c": 34, "weather": "Hot and clear", "soil_moisture": 0.2}
    )
    assert condition_warnings(snapshot) == ["Extreme heat", "Soil is dry"]


def test_sample_vitals_are_a_calm_reading() -> None:
    vitals = load_vitals()
    assert vitals.heart_rate_bpm == 72
    assert vitals.spo2_percent == 98
    assert stress_label(vitals.stress) == "Low"
    assert stress_label(70) == "High"
