"""Sensor readings: mock data until hardware drivers are wired."""

from __future__ import annotations

import random
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class SensorSnapshot:
    temperature_c: float
    humidity_pct: float
    soil_moisture_pct: float
    pressure_hpa: float | None
    light_lux: float | None
    timestamp: float


class SensorService:
    """Returns one snapshot per call; replace internals with I²C/SPI reads later."""

    def read_all(self) -> Dict[str, Any]:
        snap = self._snapshot()
        return asdict(snap)

    def _snapshot(self) -> SensorSnapshot:
        return SensorSnapshot(
            temperature_c=round(20.0 + random.random() * 6.0, 2),
            humidity_pct=round(45.0 + random.random() * 25.0, 1),
            soil_moisture_pct=round(35.0 + random.random() * 40.0, 1),
            pressure_hpa=round(1008.0 + random.random() * 12.0, 1),
            light_lux=round(2000.0 + random.random() * 15000.0, 0),
            timestamp=time.time(),
        )


_service: SensorService | None = None


def get_sensor_service() -> SensorService:
    global _service
    if _service is None:
        _service = SensorService()
    return _service
