"""
Backfill the SQLite cache with all cities already analysed.
Re-runs each extraction through the fast batch extractor so future runs
are served from cache instead of hitting GEE again.

Run once:
    python examples/backfill_cache.py
"""

import matplotlib; matplotlib.use("Agg")
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import ee
from nightlights_econ.cache import geometry_key, get_cached, cache_info
from nightlights_econ.extractor import extract_for_district

START_YR, END_YR, SCALE = 2014, 2026, 500

print("Initializing GEE…")
ee.Initialize(project="nightlights-analysis")

ALL_DISTRICTS = [
    # (display_name, admin2_GAUL, admin1_GAUL, country)
    # ── Previous runs ──────────────────────────────────────
    ("Hyderabad",        "Hyderabad",          "Andhra Pradesh",  "India"),
    ("Kolkata",          "Kolkata",             "West Bengal",     "India"),
    ("Bhubaneswar",      "Khordha",             "Orissa",          "India"),
    ("Rangareddi",       "Rangareddi",          "Andhra Pradesh",  "India"),
    ("Varanasi",         "Varanasi",            "Uttar Pradesh",   "India"),
    ("Lucknow",          "Lucknow",             "Uttar Pradesh",   "India"),
    ("Ghaziabad",        "Ghaziabad",           "Uttar Pradesh",   "India"),
    ("Allahabad",        "Allahabad",           "Uttar Pradesh",   "India"),
    ("Bengaluru",        "Bangalore Urban",     "Karnataka",       "India"),
    ("Mysuru",           "Mysore",              "Karnataka",       "India"),
    ("Hubli-Dharwad",    "Dharwad",             "Karnataka",       "India"),
    ("Belagavi",         "Belgaum",             "Karnataka",       "India"),
    ("Mangaluru",        "Dakshin Kannad",      "Karnataka",       "India"),
    ("Kalaburagi",       "Gulbarga",            "Karnataka",       "India"),
    ("Chennai",          "Chennai",             "Tamil Nadu",      "India"),
    ("Coimbatore",       "Coimbatore",          "Tamil Nadu",      "India"),
    ("Madurai",          "Madurai",             "Tamil Nadu",      "India"),
    ("Tiruchirappalli",  "Tiruchchirappalli",   "Tamil Nadu",      "India"),
    ("Salem",            "Salem",               "Tamil Nadu",      "India"),
    ("Tirunelveli",      "Tirunelveli Kattabo", "Tamil Nadu",      "India"),
    ("Vellore",          "Vellore",             "Tamil Nadu",      "India"),
    ("Erode",            "Erode",               "Tamil Nadu",      "India"),
]

already, fetched, failed = 0, 0, 0

for display, admin2, admin1, country in ALL_DISTRICTS:
    key = geometry_key(admin2, admin1, country)
    cached = get_cached(key, START_YR, END_YR, SCALE)
    if cached is not None:
        print(f"  ✓ {display:20s} — already cached ({len(cached)} rows)")
        already += 1
        continue

    print(f"  ↓ {display:20s} — fetching from GEE…", end=" ", flush=True)
    try:
        df = extract_for_district(admin2, admin1, country, START_YR, END_YR, SCALE)
        print(f"{len(df)} rows cached.")
        fetched += 1
    except Exception as e:
        print(f"FAILED: {e}")
        failed += 1

print(f"\nDone. {already} already cached, {fetched} newly fetched, {failed} failed.")
info = cache_info()
print(f"Cache DB: {len(info)} total extractions stored.")
print(info[["geometry_key", "start_year", "end_year", "n_rows", "fetched_at"]].to_string(index=False))
