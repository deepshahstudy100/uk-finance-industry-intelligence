"""ORM models. Schema is mirrored by alembic/versions/0001_initial.py."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class Source(Base):
    """A publisher endpoint family. Static facts come from app/registry/sources.py; runtime health lives here."""

    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    publisher: Mapped[str] = mapped_column(String(200))
    meta: Mapped[dict] = mapped_column(JSONType, default=dict)  # licence, docs, limits, schedule...
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    disabled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)


class Series(Base):
    """A metric definition. Static definition from app/registry/catalogue.py, runtime fields filled by ingestion."""

    __tablename__ = "series"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), index=True)
    source_key: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    definition: Mapped[dict] = mapped_column(JSONType, default=dict)
    # Runtime
    source_title: Mapped[str | None] = mapped_column(String(400), nullable=True)
    last_period: Mapped[str | None] = mapped_column(String(32), nullable=True)
    release_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_release: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_request_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_meta: Mapped[dict] = mapped_column(JSONType, default=dict)


class Observation(Base):
    __tablename__ = "observations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id: Mapped[str] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"))
    geo: Mapped[str] = mapped_column(String(32), default="K02000001")
    dim: Mapped[str] = mapped_column(String(64), default="_")
    period: Mapped[str] = mapped_column(String(32))  # canonical: 2026, 2026-Q3, 2026-09, 2026-10-23, 2026-10-26T12:30Z
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="normal")
    flags: Mapped[dict] = mapped_column(JSONType, default=dict)
    release_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    run_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_runs.id"), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("series_id", "geo", "dim", "period", "is_demo", name="uq_obs_key"),
        Index("ix_obs_series_geo_dim_start", "series_id", "geo", "dim", "period_start"),
    )


class ObservationRevision(Base):
    """A change to a previously ingested value, detected by comparing successive retrievals."""

    __tablename__ = "observation_revisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id: Mapped[str] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"), index=True)
    geo: Mapped[str] = mapped_column(String(32))
    dim: Mapped[str] = mapped_column(String(64))
    period: Mapped[str] = mapped_column(String(32))
    old_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    new_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    old_release_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    new_release_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    run_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_runs.id"), nullable=True)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), index=True)
    job: Mapped[str] = mapped_column(String(96))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")  # running|success|partial|failed|skipped
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    revised: Mapped[int] = mapped_column(Integer, default=0)
    unchanged: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list] = mapped_column(JSONType, default=list)
    requests: Mapped[list] = mapped_column(JSONType, default=list)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fingerprint: Mapped[str] = mapped_column(String(200), unique=True)
    kind: Mapped[str] = mapped_column(String(32))  # outlier|stale|delayed|source_failure|revision|validation
    severity: Mapped[str] = mapped_column(String(16))  # info|warning|critical
    series_id: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    geo: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dim: Mapped[str | None] = mapped_column(String(64), nullable=True)
    period: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    detail: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class GeoArea(Base):
    __tablename__ = "geo_areas"
    code: Mapped[str] = mapped_column(String(32), primary_key=True)  # GSS code
    name: Mapped[str] = mapped_column(String(200))
    level: Mapped[str] = mapped_column(String(16))  # uk|nation|itl1|lad
    parent_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    alt_codes: Mapped[dict] = mapped_column(JSONType, default=dict)  # itl, lr_slug, ...


class GeoBoundary(Base):
    __tablename__ = "geo_boundaries"
    level: Mapped[str] = mapped_column(String(16), primary_key=True)
    geojson: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    feature_count: Mapped[int] = mapped_column(Integer)


class SavedView(Base):
    __tablename__ = "saved_views"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    path: Mapped[str] = mapped_column(String(400))
    state: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HttpCacheEntry(Base):
    __tablename__ = "http_cache"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    url: Mapped[str] = mapped_column(Text)
    status: Mapped[int] = mapped_column(Integer)
    etag: Mapped[str | None] = mapped_column(String(300), nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body: Mapped[bytes] = mapped_column(LargeBinary)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
