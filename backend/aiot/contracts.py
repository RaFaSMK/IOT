from datetime import datetime, timezone
from uuid import uuid4
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator


def now():
    return datetime.now(timezone.utc).isoformat()


class Event(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    type: Literal['telemetry', 'highlight', 'command', 'ack', 'prediction', 'alert', 'job', 'task', 'model']
    device_id: str = Field(min_length=1, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')
    payload: dict
    schema_version: Literal[1] = 1
    correlation_id: str | None = None

    @model_validator(mode='after')
    def validate_content(self):
        import math
        if self.timestamp.tzinfo is None:
            raise ValueError('Timestamp deve informar fuso horário.')
        if self.type == 'telemetry':
            if set(self.payload) not in [{'court_id', 'sensors', 'actuators'}, {'court_id', 'sensors', 'actuators', 'simulation'}]:
                raise ValueError('Telemetria só pode conter quadra, sensores e atuadores, sem rótulos de treino.')
            readings = self.payload['sensors']
            allowed = {'ambient_temperature', 'humidity', 'luminosity', 'water_temperature', 'compressor_temperature', 'compressor_current', 'compressor_vibration'}
            if not isinstance(readings, dict) or set(readings) != allowed:
                raise ValueError('Conjunto de sensores da quadra inválido.')
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in readings.values()):
                raise ValueError('Sensores devem fornecer números finitos.')
            states = self.payload['actuators']
            if not isinstance(states, dict) or set(states) != {'cooling', 'floodlights'} or any(not isinstance(value, bool) for value in states.values()):
                raise ValueError('Estados dos atuadores inválidos.')
            if 'simulation' in self.payload:
                clock = self.payload['simulation']
                if (not isinstance(clock, dict) or set(clock) != {'step_hours', 'elapsed_hours'} or
                        any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in clock.values()) or
                        clock['step_hours'] <= 0):
                    raise ValueError('Relógio simulado inválido; não incluir rótulos ou desgaste.')
        if self.type == 'highlight':
            if self.payload.get('player') not in ['A', 'B'] or self.payload.get('event_type') not in ['highlight', 'ace', 'winner', 'error']:
                raise ValueError('Highlight inválido.')
        return self


class Command(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['set', 'inject_fault', 'reset_fault', 'highlight', 'pause', 'resume']
    on: bool | None = None
    player: Literal['A', 'B'] = 'A'


class LabConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    equipment_count: int = Field(default=100, ge=10, le=200)
    sensors_per_type: int = Field(default=1, ge=1, le=4)
    days: int = Field(default=60, ge=7, le=365)
    interval_minutes: int = Field(default=5, ge=1, le=60)
    failure_percent: float = Field(default=65, ge=10, le=95)
    failure_modes: list[Literal['bearing', 'overheating', 'imbalance']] = Field(default_factory=lambda: ['bearing', 'overheating', 'imbalance'], min_length=1)
    noise: float = Field(default=0.6, ge=0.1, le=3)
    missing_percent: float = Field(default=1, ge=0, le=15)
    outlier_percent: float = Field(default=0.5, ge=0, le=5)
    seed: int = Field(default=42, ge=0, le=2147483647)

    @property
    def rows(self):
        return self.equipment_count * (self.days * 1440 // self.interval_minutes)

    @property
    def readings(self):
        return self.rows * 3 * self.sensors_per_type
