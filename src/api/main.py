import logging
import sqlite3
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers.companies import router as companies_router
from src.api.routers.documents import router as documents_router
from src.api.routers.peers import router as peers_router
from src.api.routers.portfolio import router as portfolio_router
from src.api.routers.screener import router as screener_router
from src.api.routers.sectors import router as sectors_router
from src.api.routers.valuation import router as valuation_router

# ============================================================
# CONFIGURATION
# ============================================================

APP_VERSION = "1.0.0"

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DB_PATH = PROJECT_ROOT / "db" / "nifty100.sqlite3"

START_TIME = time.time()


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="NIFTY 100 Analytics API",
    description=(
        "Financial intelligence and analytics API " "for NIFTY 100 companies."
    ),
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST LOGGING
# ============================================================


@app.middleware("http")
async def request_logging_middleware(request, call_next):

    start = time.time()

    response = await call_next(request)

    duration = time.time() - start

    logger.info(
        "%s %s -> %s (%.3fs)",
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )

    return response


# ============================================================
# DATABASE
# ============================================================


def get_db_connection():

    connection = sqlite3.connect(DB_PATH)

    connection.row_factory = sqlite3.Row

    return connection


def get_table_counts():

    counts = {}

    connection = get_db_connection()

    try:

        cursor = connection.cursor()

        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """)

        tables = [row["name"] for row in cursor.fetchall()]

        for table in tables:

            try:

                cursor.execute(f'SELECT COUNT(*) AS count FROM "{table}"')

                counts[table] = cursor.fetchone()["count"]

            except sqlite3.Error:

                counts[table] = None

    finally:

        connection.close()

    return counts


# ============================================================
# ROOT ENDPOINT
# ============================================================


@app.get("/")
def root():

    return {
        "name": "NIFTY 100 Analytics API",
        "version": APP_VERSION,
        "status": "ok",
        "docs": "/docs",
        "api_base": "/api/v1",
    }


# ============================================================
# API V1 ROOT
# ============================================================


@app.get(
    "/api/v1",
    tags=["Health"],
)
def api_v1_root():

    return {
        "api": "NIFTY 100 Analytics API",
        "version": APP_VERSION,
        "status": "ok",
    }


# ============================================================
# HEALTH CHECK
# ============================================================


@app.get(
    "/api/v1/health",
    tags=["Health"],
)
def health():

    database_status = "ok"

    try:

        connection = get_db_connection()

        cursor = connection.cursor()

        cursor.execute("SELECT 1")

        cursor.fetchone()

        connection.close()

    except Exception as exc:

        database_status = f"error: {exc}"

    return {
        "status": "ok",
        "database": database_status,
        "tables": get_table_counts(),
        "uptime_seconds": round(
            time.time() - START_TIME,
            2,
        ),
        "version": APP_VERSION,
    }


# ============================================================
# API ROUTERS
# ============================================================

# Companies
app.include_router(
    companies_router,
    prefix="/api/v1",
)


# Screener
app.include_router(
    screener_router,
    prefix="/api/v1",
)


# Sectors
app.include_router(
    sectors_router,
    prefix="/api/v1",
)
app.include_router(
    peers_router,
    prefix="/api/v1",
)
app.include_router(
    valuation_router,
    prefix="/api/v1",
)

app.include_router(portfolio_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
# ============================================================
# STARTUP
# ============================================================


@app.on_event("startup")
async def startup_event():

    logger.info("=" * 60)

    logger.info("NIFTY 100 Analytics API starting")

    logger.info(
        "Database: %s",
        DB_PATH,
    )

    logger.info(
        "Version: %s",
        APP_VERSION,
    )

    logger.info("=" * 60)
