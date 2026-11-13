"""Live location, weather, and soil feed.

Built last. The class already matches the ``Sensor`` protocol so the app can
switch on ``SENSOR_MODE=live``. ``read`` will later:

1. Resolve the kitchen's location (name, latitude, longitude).
2. Read the current weather and temperature.
3. Read soil condition and moisture.
4. Set ``frost_risk`` when a freeze is likely overnight.
5. Return one ``SensorSnapshot``.

Until that feed exists, ``read`` fails clearly. It does not invent weather.
"""

from larder.sensors.base import LiveSensorUnavailable, SensorSnapshot


class LiveSensor:
    """Placeholder for the real sensor feed."""

    def read(self) -> SensorSnapshot:
        raise LiveSensorUnavailable(
            "The live sensor feed is not built yet. "
            "Set SENSOR_MODE=mock to use fixtures/sensor.sample.json."
        )
