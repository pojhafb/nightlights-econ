"""SQLite cache for GEE VIIRS extractions.

Stores raw monthly radiance + cloud-free obs per district so GEE is
only called once per (geometry_key, start_year, end_year, scale).

DB location: ~/.cache/nightlights_econ/viirs_cache.db
Schema:
  extractions(id, geometry_key, start_year, end_year, scale, fetched_at)
  monthly_obs(extraction_id, date, year, month, radiance_raw, cf_obs)
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from .utils import CACHE_DIR

DB_PATH = CACHE_DIR / "viirs_cache.db"


def _connect() -> sqlite3.Connection:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS extractions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            geometry_key TEXT    NOT NULL,
            start_year   INTEGER NOT NULL,
            end_year     INTEGER NOT NULL,
            scale        INTEGER NOT NULL,
            fetched_at   TEXT    NOT NULL,
            n_rows       INTEGER NOT NULL DEFAULT 0,
            UNIQUE(geometry_key, start_year, end_year, scale)
        );

        CREATE TABLE IF NOT EXISTS monthly_obs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            extraction_id INTEGER NOT NULL REFERENCES extractions(id) ON DELETE CASCADE,
            date          TEXT    NOT NULL,
            year          INTEGER NOT NULL,
            month         INTEGER NOT NULL,
            radiance_raw  REAL,
            cf_obs        REAL
        );

        CREATE INDEX IF NOT EXISTS idx_monthly_extraction
            ON monthly_obs(extraction_id);
    """)
    conn.commit()


def geometry_key(admin2: str, admin1: str, country: str = "India") -> str:
    """Stable hash key for a district boundary (case-insensitive)."""
    raw = f"{country.lower()}|{admin1.lower()}|{admin2.lower()}"
    h = hashlib.sha1(raw.encode()).hexdigest()[:16]
    return f"{h}:{admin2.title()}/{admin1.title()}"


def geometry_key_from_coords(lat: float, lon: float, radius_km: float) -> str:
    raw = f"point:{lat:.4f},{lon:.4f},r{radius_km:.1f}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16] + f":point({lat:.3f},{lon:.3f})"


def geometry_key_from_geojson(geojson: dict, name: str) -> str:
    raw = json.dumps(geojson, sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()[:16] + f":geojson/{name}"


def get_cached(
    key: str,
    start_year: int,
    end_year: int,
    scale: int,
) -> Optional[pd.DataFrame]:
    """Return cached DataFrame if available, else None.

    Args:
        key: geometry_key string.
        start_year: First year of requested range.
        end_year: Last year of requested range.
        scale: GEE reduce scale in metres.

    Returns:
        DataFrame with columns (date, year, month, radiance_raw, cf_obs),
        or None if not cached.
    """
    with _connect() as conn:
        row = conn.execute(
            """SELECT id FROM extractions
               WHERE geometry_key=? AND start_year<=? AND end_year>=? AND scale=?""",
            (key, start_year, end_year, scale),
        ).fetchone()

        if row is None:
            return None

        rows = conn.execute(
            """SELECT date, year, month, radiance_raw, cf_obs
               FROM monthly_obs WHERE extraction_id=?
               AND year>=? AND year<=?
               ORDER BY date""",
            (row["id"], start_year, end_year),
        ).fetchall()

    if not rows:
        return None

    df = pd.DataFrame([dict(r) for r in rows])
    df["date"] = pd.to_datetime(df["date"])
    return df


def save_to_cache(
    key: str,
    start_year: int,
    end_year: int,
    scale: int,
    df: pd.DataFrame,
) -> None:
    """Persist a fetched DataFrame to the cache.

    Args:
        key: geometry_key string.
        start_year: First year fetched.
        end_year: Last year fetched.
        scale: GEE reduce scale.
        df: DataFrame with (date, year, month, radiance_raw, cf_obs).
    """
    with _connect() as conn:
        # Upsert extraction record
        conn.execute(
            """INSERT INTO extractions(geometry_key, start_year, end_year, scale, fetched_at, n_rows)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(geometry_key, start_year, end_year, scale)
               DO UPDATE SET fetched_at=excluded.fetched_at, n_rows=excluded.n_rows""",
            (key, start_year, end_year, scale,
             datetime.now(timezone.utc).isoformat(), len(df)),
        )
        extraction_id = conn.execute(
            "SELECT id FROM extractions WHERE geometry_key=? AND start_year=? AND end_year=? AND scale=?",
            (key, start_year, end_year, scale),
        ).fetchone()["id"]

        # Delete old monthly rows for this extraction (in case of refresh)
        conn.execute("DELETE FROM monthly_obs WHERE extraction_id=?", (extraction_id,))

        # Insert rows
        conn.executemany(
            """INSERT INTO monthly_obs(extraction_id, date, year, month, radiance_raw, cf_obs)
               VALUES(?,?,?,?,?,?)""",
            [
                (extraction_id, str(row["date"])[:10],
                 int(row["year"]), int(row["month"]),
                 float(row["radiance_raw"]) if pd.notna(row["radiance_raw"]) else None,
                 float(row["cf_obs"])       if pd.notna(row["cf_obs"])       else None)
                for _, row in df.iterrows()
            ],
        )
        conn.commit()


def cache_info() -> pd.DataFrame:
    """Return a summary of all cached extractions.

    Returns:
        DataFrame with columns: geometry_key, start_year, end_year, scale,
        fetched_at, n_rows.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT geometry_key, start_year, end_year, scale, fetched_at, n_rows "
            "FROM extractions ORDER BY fetched_at DESC"
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()


def invalidate(key: str, start_year: int, end_year: int, scale: int) -> bool:
    """Remove a specific cached extraction (force re-fetch on next call).

    Returns:
        True if a row was deleted.
    """
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM extractions WHERE geometry_key=? AND start_year=? AND end_year=? AND scale=?",
            (key, start_year, end_year, scale),
        )
        conn.commit()
        return cur.rowcount > 0


def invalidate_all() -> int:
    """Wipe the entire cache. Returns number of extractions deleted."""
    with _connect() as conn:
        cur = conn.execute("DELETE FROM extractions")
        conn.commit()
        return cur.rowcount
