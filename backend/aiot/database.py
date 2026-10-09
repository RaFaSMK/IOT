from datetime import datetime, timezone
from urllib.parse import quote
from sqlalchemy import create_engine, String, DateTime, JSON, Boolean, Integer, Text, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import secrets


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    username: Mapped[str] = mapped_column(String(80), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Device(Base):
    __tablename__ = 'devices'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(30))
    unit: Mapped[str] = mapped_column(String(20), default='')
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Audit(Base):
    __tablename__ = 'audit'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    username: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class Rule(Base):
    __tablename__ = 'rules'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSON)


class Alert(Base):
    __tablename__ = 'alerts'
    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default='queued')
    progress: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ModelVersion(Base):
    __tablename__ = 'model_versions'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(80))
    metrics: Mapped[dict] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


_engine = None


def engine():
    global _engine
    if _engine is None:
        password = quote(secrets()['postgres_password'], safe='')
        _engine = create_engine(f'postgresql+psycopg://court:{password}@postgres:5432/court', pool_pre_ping=True)
    return _engine


def session():
    return sessionmaker(engine(), expire_on_commit=False)()


def as_dict(row):
    return {col.name: (value.isoformat() if isinstance(value, datetime) else value) for col in row.__table__.columns for value in [getattr(row, col.name)]}


def audit(username, action, details=None):
    with session() as db:
        db.add(Audit(username=username, action=action, details=details or {}))
        db.commit()


def initialize():
    import bcrypt
    Base.metadata.create_all(engine())
    initial_devices = [
        ('ambient_temperature', 'Temperatura da quadra', 'sensor', '°C', {'min': 10, 'max': 35}),
        ('humidity', 'Umidade do ar', 'sensor', '%', {'min': 25, 'max': 90}),
        ('luminosity', 'Luminosidade', 'sensor', 'lux', {'min': 0, 'max': 100000}),
        ('water_temperature', 'Temperatura da água', 'sensor', '°C', {'min': 4, 'max': 18}),
        ('compressor_temperature', 'Temperatura do compressor', 'sensor', '°C', {'min': 15, 'max': 75}),
        ('compressor_current', 'Corrente do compressor', 'sensor', 'A', {'min': 0, 'max': 7}),
        ('compressor_vibration', 'Vibração do compressor', 'sensor', 'mm/s', {'min': 0, 'max': 5}),
        ('compressor_01', 'Compressor do bebedouro', 'equipment', '', {}),
        ('cooling', 'Refrigeração do bebedouro', 'actuator', '', {}),
        ('floodlights', 'Refletores da quadra', 'actuator', '', {}),
        ('highlight_button', 'Botão de highlight', 'button', '', {}),
        ('simulator', 'Simulador da quadra', 'simulator', '', {}),
    ]
    with session() as db:
        for role, details in secrets()['demo_users'].items():
            if not db.get(User, details['username']):
                db.add(User(username=details['username'], role=role, password_hash=bcrypt.hashpw(details['password'].encode(), bcrypt.gensalt()).decode()))
        for identifier, name, kind, unit, config in initial_devices:
            if not db.get(Device, identifier):
                db.add(Device(id=identifier, name=name, kind=kind, unit=unit, config=config))
        if not db.get(Rule, 'water_cooling'):
            db.add(Rule(id='water_cooling', config={'sensor': 'water_temperature', 'actuator': 'cooling', 'on_above': 16, 'off_below': 10}))
        db.commit()
