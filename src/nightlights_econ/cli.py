"""Click-based CLI for nightlights-econ."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click

from .core import CityDefinition


def _make_engine(project_id: Optional[str] = None):
    from .engine import NighttimeLightsEngine
    try:
        return NighttimeLightsEngine(project_id=project_id)
    except Exception as exc:
        click.echo(
            f"\nERROR: Could not initialize Google Earth Engine.\n"
            f"Run `earthengine authenticate` in your terminal first.\n"
            f"Or pass --project <GCP-project-id> if using a GCP project.\n"
            f"Details: {exc}",
            err=True,
        )
        sys.exit(1)


@click.group()
@click.version_option()
def cli() -> None:
    """nightlights-econ — Measure real economic activity from NASA satellite data."""


@cli.command()
@click.option("--city", required=True, help="City name")
@click.option("--country", default=None, help="Country name")
@click.option("--state", default=None, help="State/province name")
@click.option("--district", default=None, help="District/admin2 name")
@click.option("--lat", type=float, default=None, help="Latitude (point + radius mode)")
@click.option("--lon", type=float, default=None, help="Longitude (point + radius mode)")
@click.option("--radius", type=float, default=15.0, help="Radius in km (default 15)")
@click.option("--country-code", default="IND", help="ISO 3166-1 alpha-3 code (default IND)")
@click.option("--start", type=int, default=2014, help="Start year (default 2014)")
@click.option("--end", type=int, default=2026, help="End year (default 2026)")
@click.option("--output", default="./reports", help="Output directory for charts")
@click.option("--project", default=None, help="Google Cloud project ID")
@click.option("--event-date", multiple=True, help="Event date YYYY-MM-DD (repeatable)")
@click.option("--event-name", multiple=True, help="Event label (paired with --event-date)")
def analyze(
    city, country, state, district, lat, lon, radius, country_code,
    start, end, output, project, event_date, event_name,
):
    """Run full analysis for a single city and generate all charts."""
    if lat and lon:
        city_def = CityDefinition(
            name=city, lat=lat, lon=lon, radius_km=radius, country_code=country_code
        )
    else:
        city_def = CityDefinition(
            name=city, country=country, admin1=state, admin2=district,
            country_code=country_code,
        )

    events = []
    for d, n in zip(event_date, event_name):
        events.append({"date": d, "label": n})

    engine = _make_engine(project)
    click.echo(f"Analyzing {city}…")
    series = engine.analyze(city_def, start_year=start, end_year=end)

    from .plotting import plot_city_report
    click.echo(f"Generating charts → {output}")
    plot_city_report(series, save_dir=output, events=events or None)
    click.echo(f"Done. Charts saved to {output}/")


@cli.command()
@click.option("--cities", required=True, help="Comma-separated city names")
@click.option("--country", default=None, help="Country name (applied to all cities)")
@click.option("--start", type=int, default=2014)
@click.option("--end", type=int, default=2026)
@click.option("--output", default="./reports")
@click.option("--project", default=None)
def compare(cities, country, start, end, output, project):
    """Compare multiple cities side-by-side and generate a dashboard."""
    city_names = [c.strip() for c in cities.split(",")]
    city_defs = [
        CityDefinition(name=n, country=country) for n in city_names
    ]

    engine = _make_engine(project)
    click.echo(f"Comparing {', '.join(city_names)}…")
    series_list = engine.analyze_many(city_defs, start_year=start, end_year=end)

    from .plotting import plot_comparison_report
    plot_comparison_report(series_list, save_dir=output)
    click.echo(f"Done. Charts saved to {output}/")


@cli.command()
@click.option("--city", required=True, help="City name")
@click.option("--country", default=None)
@click.option("--event-date", required=True, help="Shock event date YYYY-MM-DD")
@click.option("--event-name", required=True, help="Event label")
@click.option("--window", type=int, default=12, help="Months before/after event (default 12)")
@click.option("--start", type=int, default=2014)
@click.option("--end", type=int, default=2026)
@click.option("--output", default="./reports")
@click.option("--project", default=None)
def shock(city, country, event_date, event_name, window, start, end, output, project):
    """Analyse the economic impact of a shock event on a city."""
    city_def = CityDefinition(name=city, country=country)
    engine = _make_engine(project)
    click.echo(f"Analyzing shock impact on {city}…")
    series = engine.analyze(city_def, start_year=start, end_year=end)

    from .analysis import shock_analysis
    from .plotting import plot_shock_resilience

    result = shock_analysis(series, event_date=event_date, window_months=window)
    if "error" in result:
        click.echo(f"ERROR: {result['error']}", err=True)
        sys.exit(1)

    click.echo(f"\n  Drop: {result['drop_pct']:.1f}%")
    click.echo(f"  Resilience score: {result['resilience_score']:.0f}/100")
    if result["recovery_months"]:
        click.echo(f"  Recovery: {result['recovery_months']} months")
    else:
        click.echo("  Recovery: not observed in window")

    fig = plot_shock_resilience([result], event_name=event_name)
    from .utils import safe_save
    Path(output).mkdir(parents=True, exist_ok=True)
    safe_save(fig, f"{output}/{city.lower().replace(' ', '_')}_shock_{event_date}.png", dpi=150)
    click.echo(f"\nChart saved to {output}/")


@cli.command()
@click.option("--country", required=True, help="Country name")
@click.option("--states", default=None, help="Comma-separated state names to restrict to")
@click.option("--top", type=int, default=5, help="Number of top districts")
@click.option("--bottom", type=int, default=5, help="Number of bottom districts")
@click.option("--metric", default="per_capita_growth",
              type=click.Choice(["per_capita_growth", "total_growth", "ppp_per_capita"]))
@click.option("--start", type=int, default=2014)
@click.option("--end", type=int, default=2026)
@click.option("--output", default="./reports")
@click.option("--project", default=None)
def rank(country, states, top, bottom, metric, start, end, output, project):
    """Rank all districts in a country by nighttime lights growth."""
    admin1_list = [s.strip() for s in states.split(",")] if states else None
    engine = _make_engine(project)
    click.echo(f"Ranking districts in {country}…")

    from .rankings import rank_country
    df = rank_country(
        country=country,
        admin1_list=admin1_list,
        start_year=start,
        end_year=end,
        top_n=top,
        bottom_n=bottom,
        engine=engine,
    )
    click.echo(df.to_string(index=False))

    from .plotting import plot_rankings
    fig = plot_rankings(df, metric=metric, title=f"{country} District Rankings")
    Path(output).mkdir(parents=True, exist_ok=True)
    from .utils import safe_save
    safe_save(fig, f"{output}/{country.lower()}_rankings.png")
    click.echo(f"\nChart saved to {output}/")


@cli.command()
@click.option("--city", required=True, help="City name")
@click.option("--country", default=None)
@click.option("--project", default=None)
def quick(city, country, project):
    """Quick analysis — print key stats for a city (no charts)."""
    city_def = CityDefinition(name=city, country=country)
    engine = _make_engine(project)
    click.echo(f"Quick analysis for {city}…")
    series = engine.analyze(city_def, start_year=2014, end_year=2026)

    from .analysis import total_growth_pct
    click.echo(f"\n  City: {series.city}")
    click.echo(f"  Period: {series.start_year}–{series.end_year}")
    click.echo(f"  Area: {series.geometry_area_km2:.0f} km²")
    click.echo(f"  GDP proxy growth: {total_growth_pct(series, 'gdp_proxy'):.1f}%")
    click.echo(f"  Per-capita growth: {total_growth_pct(series, 'gdp_per_capita'):.1f}%")
    click.echo(f"  PPP-adj per-capita growth: {total_growth_pct(series, 'gdp_ppp_per_capita'):.1f}%")
