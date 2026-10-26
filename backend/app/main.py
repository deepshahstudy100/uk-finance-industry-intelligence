from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .api import dashboards, platform, series
from .config import get_settings
from .db import Base, get_engine, session_scope
from .demo.generator import ensure_demo
from .ingestion.runner import sync_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def init_db() -> None:
    engine = get_engine()
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)  # PostgreSQL uses Alembic migrations
    with session_scope() as s:
        sync_registry(s)
        if get_settings().demo_mode != "off":
            ensure_demo(s)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="UK National Finance & Industry Intelligence Platform API",
    version="0.1.0",
    description=(
        "Official, openly licensed UK statistics with full provenance. Every observation carries its source, "
        "retrieval time and ingestion run. Responses include `data_status` = `real` or `demo`; demo data is "
        "synthetic and never mixed with real observations."
    ),
    lifespan=lifespan,
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in get_settings().cors_origins.split(",")],
                   allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"],
                   expose_headers=["Content-Disposition", "X-Source-URL", "X-Retrieved-At"])
app.include_router(series.router)
app.include_router(dashboards.router)
app.include_router(platform.router)
