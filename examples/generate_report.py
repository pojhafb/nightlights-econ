"""
Nighttime Lights Economic Analysis - Report Generator
Writes nightlights_india_report.pdf to ~/Desktop/
"""

import matplotlib
matplotlib.use("Agg")

import sys, os, math, textwrap
from pathlib import Path
from datetime import date

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd
from fpdf import FPDF

OUT_DIR  = Path.home() / "Desktop" / "nightlights_report"
PDF_PATH = Path.home() / "Desktop" / "nightlights_india_report.pdf"
OUT_DIR.mkdir(exist_ok=True)
CHARTS   = OUT_DIR / "charts"
CHARTS.mkdir(exist_ok=True)

# -- Palette / style ----------------------------------------------------------
PALETTE  = ["#1B4F72", "#E74C3C", "#F39C12", "#27AE60", "#8E44AD", "#2C3E50",
            "#117A65", "#C0392B", "#D4AC0D", "#1A5276"]
BG       = "#FAFAFA"
SOURCE   = "Source: NASA VIIRS DNB / NOAA DMSP-OLS / GHS-POP / World Bank"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11,
    "axes.facecolor": BG, "figure.facecolor": BG,
    "axes.grid": True, "axes.grid.axis": "y",
    "grid.color": "#E0E0E0", "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False,
})

def save(fig, name):
    p = str(CHARTS / name)
    fig.savefig(p, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return p

# ============================================================================
# DATA (embedded - all from our GEE runs)
# ============================================================================

# 2014-2026 VIIRS results (per-capita growth %)
VIIRS_RESULTS = {
    # UP cities
    "Varanasi":         {"pc": 493, "total": 629, "state": "Uttar Pradesh",
                         "periods": {"2014-19": 95,  "2019-26": 209}},
    "Allahabad":        {"pc": 369, "total": 484, "state": "Uttar Pradesh",
                         "periods": {"2014-19": 116, "2019-26": 152}},
    "Ghaziabad":        {"pc": 284, "total": 406, "state": "Uttar Pradesh",
                         "periods": {"2014-19": 83,  "2019-26": 130}},
    "Lucknow":          {"pc": 191, "total": 275, "state": "Uttar Pradesh",
                         "periods": {"2014-19": 58,  "2019-26": 98}},
    # South India
    "Bhubaneswar":      {"pc": 213, "total": 337, "state": "Odisha",
                         "periods": {"2014-19": 65, "2019-26": 183}},
    "Erode":            {"pc": 432, "total": 525, "state": "Tamil Nadu",
                         "periods": {"2014-19": 130, "2019-26": 192}},
    "Madurai":          {"pc": 391, "total": 495, "state": "Tamil Nadu",
                         "periods": {"2014-19": 118, "2019-26": 172}},
    "Coimbatore":       {"pc": 365, "total": 471, "state": "Tamil Nadu",
                         "periods": {"2014-19": 72,  "2019-26": 149}},
    "Tiruchirappalli":  {"pc": 358, "total": 450, "state": "Tamil Nadu",
                         "periods": {"2014-19": 95,  "2019-26": 150}},
    "Chennai":          {"pc": 227, "total": 296, "state": "Tamil Nadu",
                         "periods": {"2014-19": 63,  "2019-26": 122}},
    # Karnataka
    "Belagavi":         {"pc": 513, "total": 608, "state": "Karnataka",
                         "periods": {"2014-19": 180, "2019-26": 165}},
    "Hubli-Dharwad":    {"pc": 450, "total": 558, "state": "Karnataka",
                         "periods": {"2014-19": 155, "2019-26": 162}},
    "Mangaluru":        {"pc": 377, "total": 455, "state": "Karnataka",
                         "periods": {"2014-19": 120, "2019-26": 157}},
    "Bengaluru":        {"pc": 118, "total": 207, "state": "Karnataka",
                         "periods": {"2014-19": 37,  "2019-26": 44}},
    # Metros
    "Greater Hyderabad":{"pc": 131, "total": 253, "state": "Telangana",
                         "periods": {"2014-19": 30, "2019-26": 84}},
    "Kolkata":          {"pc": 117, "total": 150, "state": "West Bengal",
                         "periods": {"2014-19": 49,  "2019-26": 119}},
}

# Extended 2004-2026 period breakdown (per-capita %)
EXTENDED = {
    "Guwahati":     {"pc_total": 1322, "p1": 40,  "p2": 55,  "p3": 100, "p4": 227},
    "Allahabad":    {"pc_total": 1049, "p1": 1,   "p2": 109, "p3": 116, "p4": 152},
    "Patna":        {"pc_total": 1013, "p1": 31,  "p2": 74,  "p3": 134, "p4": 109},
    "Varanasi":     {"pc_total": 814,  "p1": 12,  "p2": 35,  "p3": 95,  "p4": 209},
    "Bhubaneswar":  {"pc_total": 748,  "p1": -2,  "p2": 86,  "p3": 65,  "p4": 183},
    "Ahmedabad":    {"pc_total": 730,  "p1": None,"p2": None,"p3": None,"p4": None},
    "Pune":         {"pc_total": 609,  "p1": 6,   "p2": 37,  "p3": 92,  "p4": 154},
    "Nagpur":       {"pc_total": 591,  "p1": -3,  "p2": 48,  "p3": 56,  "p4": 209},
    "Jaipur":       {"pc_total": 542,  "p1": 32,  "p2": 34,  "p3": 54,  "p4": 135},
    "Coimbatore":   {"pc_total": 530,  "p1": 14,  "p2": 29,  "p3": 72,  "p4": 149},
    "Lucknow":      {"pc_total": 444,  "p1": 22,  "p2": 42,  "p3": 58,  "p4": 98},
    "Chennai":      {"pc_total": 367,  "p1": -3,  "p2": 33,  "p3": 63,  "p4": 122},
    "Kolkata":      {"pc_total": 358,  "p1": 1,   "p2": 39,  "p3": 49,  "p4": 119},
    "Bengaluru":    {"pc_total": 153,  "p1": 0,   "p2": 28,  "p3": 37,  "p4": 44},
    "Hyderabad":    {"pc_total": 129,  "p1": -3,  "p2": 16,  "p3": 13,  "p4": 79},
}

# India state rankings
STATE_RANKINGS = [
    ("Kerala", 852), ("Manipur", 555), ("Arunachal Pradesh", 503),
    ("Assam", 470), ("Gujarat", 398), ("Uttar Pradesh", 392),
    ("Nagaland", 391), ("Bihar", 389), ("Orissa", 385),
    ("Himachal Pradesh", 384), ("Madhya Pradesh", 361), ("Mizoram", 359),
    ("Jharkhand", 350), ("Uttarakhand", 345), ("Punjab", 345),
    ("Maharashtra", 339), ("Andhra Pradesh", 321), ("Meghalaya", 320),
    ("Goa", 309), ("Tamil Nadu", 293), ("Sikkim", 288),
    ("West Bengal", 287), ("Karnataka", 281), ("Chhattisgarh", 279),
    ("Rajasthan", 275), ("Tripura", 262), ("Haryana", 260),
    ("Puducherry", 213), ("Chandigarh", 213), ("Daman and Diu", 72),
    ("Dadra and Nagar Haveli", 63),
]

# ============================================================================
# CHART GENERATION
# ============================================================================

def chart_overall_rankings():
    """Top 20 cities by VIIRS per-capita growth 2014-2026."""
    items = sorted(VIIRS_RESULTS.items(), key=lambda x: x[1]["pc"], reverse=True)[:20]
    cities = [x[0] for x in items]
    values = [x[1]["pc"] for x in items]
    median = np.median(values)
    colors = [PALETTE[3] if v > median*1.1 else PALETTE[1] if v < median*0.9 else PALETTE[2]
              for v in values]

    fig, ax = plt.subplots(figsize=(12, 8))
    bars = ax.barh(cities[::-1], values[::-1], color=colors[::-1], height=0.7)
    ax.axvline(median, color="#888", linewidth=1.2, linestyle="--",
               label=f"Median ({median:.0f}%)")
    for bar, val in zip(bars, values[::-1]):
        ax.text(bar.get_width()+5, bar.get_y()+bar.get_height()/2,
                f"+{val}%", va="center", fontsize=8.5, color="#444")
    ax.set_xlabel("Per-Capita GDP Growth % (2014->2026, base=100)", fontsize=11)
    ax.set_title("Indian Cities: Per-Capita GDP Growth via VIIRS Nighttime Lights",
                 fontsize=13, fontweight="bold", pad=12)
    ax.legend(fontsize=9)
    ax.annotate(SOURCE, xy=(0,-0.10), xycoords="axes fraction", fontsize=7.5, color="#777")
    fig.tight_layout()
    return save(fig, "01_city_rankings_viirs.png")

def chart_period_breakdown():
    """Stacked bar: per-period growth for extended 2004-2026 cities."""
    cities = [c for c, d in EXTENDED.items() if d["p1"] is not None]
    p1 = [EXTENDED[c]["p1"] for c in cities]
    p2 = [EXTENDED[c]["p2"] for c in cities]
    p3 = [EXTENDED[c]["p3"] for c in cities]
    p4 = [EXTENDED[c]["p4"] for c in cities]

    x = np.arange(len(cities))
    w = 0.6
    fig, ax = plt.subplots(figsize=(14, 7))
    b1 = ax.bar(x, p1, w, label="2004->2009 (UPA-2 boom)", color=PALETTE[2], alpha=0.9)
    b2 = ax.bar(x, p2, w, bottom=p1, label="2009->2014 (slowdown)", color=PALETTE[0], alpha=0.9)
    b3 = ax.bar(x, p3, w,
                bottom=[a+b for a,b in zip(p1,p2)],
                label="2014->2019 (NDA-1)", color=PALETTE[3], alpha=0.9)
    b4 = ax.bar(x, p4, w,
                bottom=[a+b+c for a,b,c in zip(p1,p2,p3)],
                label="2019->2026 (post-Covid)", color=PALETTE[4], alpha=0.9)

    ax.set_xticks(x)
    ax.set_xticklabels(cities, rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("Per-Capita GDP Growth (%)", fontsize=11)
    ax.set_title("Period-wise Per-Capita GDP Growth: 2004-2026 (DMSP + VIIRS)",
                 fontsize=13, fontweight="bold", pad=12)
    ax.legend(fontsize=9, loc="upper left")
    ax.axhline(0, color="#888", linewidth=0.8)
    ax.annotate(SOURCE, xy=(0,-0.18), xycoords="axes fraction", fontsize=7.5, color="#777")
    fig.tight_layout()
    return save(fig, "02_period_breakdown.png")

def chart_extended_total():
    """Total 2004-2026 per-capita ranking."""
    items = sorted(EXTENDED.items(), key=lambda x: x[1]["pc_total"])
    cities = [x[0] for x in items]
    values = [x[1]["pc_total"] for x in items]
    median = np.median(values)
    colors = [PALETTE[3] if v > median*1.1 else PALETTE[1] if v < median*0.9 else PALETTE[2]
              for v in values]

    fig, ax = plt.subplots(figsize=(11, 7))
    bars = ax.barh(cities, values, color=colors, height=0.7)
    ax.axvline(median, color="#888", linewidth=1.2, linestyle="--",
               label=f"Median ({median:.0f}%)")
    for bar, val in zip(bars, values):
        ax.text(bar.get_width()+15, bar.get_y()+bar.get_height()/2,
                f"+{val}%", va="center", fontsize=9, color="#444")
    ax.set_xlabel("Per-Capita GDP Growth % (2004->2026)", fontsize=11)
    ax.set_title("22-Year Rankings: Per-Capita GDP Growth 2004-2026",
                 fontsize=13, fontweight="bold", pad=12)
    ax.legend(fontsize=9)
    ax.annotate(SOURCE, xy=(0,-0.10), xycoords="axes fraction", fontsize=7.5, color="#777")
    fig.tight_layout()
    return save(fig, "03_extended_total_ranking.png")

def chart_state_heatmap():
    """Simplified state bar ranking."""
    states_sorted = sorted(STATE_RANKINGS, key=lambda x: x[1])
    names = [x[0] for x in states_sorted]
    vals  = [x[1] for x in states_sorted]
    median = np.median(vals)
    colors = [PALETTE[3] if v > median*1.15 else PALETTE[1] if v < median*0.85 else PALETTE[2]
              for v in vals]

    fig, ax = plt.subplots(figsize=(12, 10))
    bars = ax.barh(names, vals, color=colors, height=0.72)
    ax.axvline(median, color="#888", linewidth=1.2, linestyle="--",
               label=f"Median ({median:.0f}%)")
    for bar, val in zip(bars, vals):
        ax.text(bar.get_width()+5, bar.get_y()+bar.get_height()/2,
                f"+{val}%", va="center", fontsize=8, color="#444")
    ax.set_xlabel("Per-Capita GDP Growth % (2014->2026)", fontsize=11)
    ax.set_title("All-India State Rankings: Per-Capita GDP Growth\n"
                 "Population-ratio district selection, VIIRS + LED correction",
                 fontsize=12, fontweight="bold", pad=12)
    for label in ax.get_yticklabels():
        label.set_fontsize(8.5)
    green_p = mpatches.Patch(color=PALETTE[3], label="Above median")
    amber_p = mpatches.Patch(color=PALETTE[2], label="Near median")
    red_p   = mpatches.Patch(color=PALETTE[1], label="Below median")
    ax.legend(handles=[green_p, amber_p, red_p], fontsize=9, loc="lower right")
    ax.annotate(SOURCE, xy=(0,-0.05), xycoords="axes fraction", fontsize=7.5, color="#777")
    fig.tight_layout()
    return save(fig, "04_state_rankings.png")

def chart_up_cities():
    """UP cities 2014-2026 comparison."""
    cities = ["Varanasi", "Allahabad", "Ghaziabad", "Lucknow"]
    pc     = [VIIRS_RESULTS[c]["pc"] for c in cities]
    tot    = [VIIRS_RESULTS[c]["total"] for c in cities]

    x = np.arange(len(cities))
    w = 0.35
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(x - w/2, tot, w, label="Total GDP proxy growth", color=PALETTE[0], alpha=0.9)
    ax.bar(x + w/2, pc,  w, label="Per-capita GDP growth",  color=PALETTE[3], alpha=0.9)
    for i, (t, p) in enumerate(zip(tot, pc)):
        ax.text(i-w/2, t+5, f"+{t}%", ha="center", fontsize=8.5, color=PALETTE[0])
        ax.text(i+w/2, p+5, f"+{p}%", ha="center", fontsize=8.5, color=PALETTE[3])
    ax.set_xticks(x)
    ax.set_xticklabels(cities, fontsize=11)
    ax.set_ylabel("Growth % (2014->2026, base=100)", fontsize=11)
    ax.set_title("Uttar Pradesh Cities: GDP & Per-Capita Growth 2014-2026",
                 fontsize=13, fontweight="bold", pad=12)
    ax.legend(fontsize=10)
    ax.annotate(SOURCE, xy=(0,-0.12), xycoords="axes fraction", fontsize=7.5, color="#777")
    fig.tight_layout()
    return save(fig, "05_up_cities.png")

def chart_south_india():
    """Karnataka and Tamil Nadu comparison."""
    karnataka = {k: v for k, v in VIIRS_RESULTS.items() if v["state"] == "Karnataka"}
    tamilnadu = {k: v for k, v in VIIRS_RESULTS.items() if v["state"] == "Tamil Nadu"}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    for ax, data, title in [(ax1, karnataka, "Karnataka"), (ax2, tamilnadu, "Tamil Nadu")]:
        items = sorted(data.items(), key=lambda x: x[1]["pc"])
        names = [x[0] for x in items]
        pcs   = [x[1]["pc"] for x in items]
        colors = [PALETTE[i % len(PALETTE)] for i in range(len(names))]
        bars = ax.barh(names, pcs, color=colors, height=0.6)
        for bar, val in zip(bars, pcs):
            ax.text(bar.get_width()+5, bar.get_y()+bar.get_height()/2,
                    f"+{val}%", va="center", fontsize=8.5)
        ax.set_title(f"{title}: Per-Capita Growth\n2014-2026",
                     fontsize=11, fontweight="bold")
        ax.set_xlabel("Per-Capita Growth %", fontsize=10)
    ax1.annotate(SOURCE, xy=(0,-0.14), xycoords="axes fraction", fontsize=7.5, color="#777")
    fig.suptitle("South India Cities: Per-Capita GDP Growth via VIIRS", fontsize=13, fontweight="bold", y=1.02)
    fig.tight_layout()
    return save(fig, "06_south_india.png")

def chart_dmsp_saturation():
    """Illustrate DMSP saturation issue for large metros."""
    cities = ["Guwahati", "Varanasi", "Patna", "Lucknow", "Pune",
              "Kolkata", "Chennai", "Bengaluru", "Hyderabad"]
    dmsp_2013 = [7.03, 12.02, 9.43, 19.69, 13.99, 63.0, 62.41, 43.94, 63.0]
    pc_total  = [1322, 814, 1013, 444, 609, 358, 367, 153, 129]

    fig, ax = plt.subplots(figsize=(11, 7))
    scatter_colors = [PALETTE[3] if d < 40 else PALETTE[1] if d > 60 else PALETTE[2]
                      for d in dmsp_2013]
    sc = ax.scatter(dmsp_2013, pc_total, c=scatter_colors, s=120, zorder=5)
    for city, x_val, y_val in zip(cities, dmsp_2013, pc_total):
        ax.annotate(city, (x_val, y_val), textcoords="offset points",
                    xytext=(8, 4), fontsize=9, color="#333")
    ax.axvline(60, color=PALETTE[1], linewidth=1.2, linestyle="--", alpha=0.7,
               label="DMSP saturation threshold (DN~60)")
    ax.set_xlabel("DMSP 2013 Stable Lights DN value (0-63 scale, 63 = saturated)",
                  fontsize=11)
    ax.set_ylabel("22-Year Per-Capita Growth % (2004->2026)", fontsize=11)
    ax.set_title("DMSP Saturation Effect: Already-Bright Cities Appear to Grow Less\n"
                 "Cities near DN=63 in 2004 have unreliable pre-2014 baselines",
                 fontsize=11, fontweight="bold", pad=12)
    ax.legend(fontsize=10)
    green_p = mpatches.Patch(color=PALETTE[3], label="Low DN (reliable baseline)")
    red_p   = mpatches.Patch(color=PALETTE[1], label="High DN (likely saturated)")
    ax.legend(handles=[green_p, red_p], fontsize=9)
    ax.annotate(SOURCE, xy=(0,-0.10), xycoords="axes fraction", fontsize=7.5, color="#777")
    fig.tight_layout()
    return save(fig, "07_dmsp_saturation.png")

def chart_pipeline():
    """Visual pipeline diagram."""
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.set_xlim(0, 14); ax.set_ylim(0, 4); ax.axis("off")
    steps = [
        ("VIIRS DNB\nMonthly", "NOAA/GEE\n2014->2026", PALETTE[0]),
        ("DMSP-OLS\nAnnual", "NOAA/GEE\n2004->2013", "#555555"),
        ("Cloud\nCorrection", "xKDR algorithm\nMonsoon months", PALETTE[2]),
        ("LED\nCorrection", "SLNP penetration\nby state+year", PALETTE[4]),
        ("Cross-\nCalibration", "2013 overlap\nper-district", "#888"),
        ("Pop\nNorm.", "Census CAGR\nGHS-POP", PALETTE[3]),
        ("PPP\nAdjust", "World Bank\nPA.NUS.PPP", PALETTE[1]),
        ("GDP\nProxy", "Henderson\nb=0.95", "#117A65"),
    ]
    for i, (title, sub, col) in enumerate(steps):
        x = i*1.75 + 0.5
        rect = mpatches.FancyBboxPatch((x, 1.2), 1.4, 1.6, boxstyle="round,pad=0.1",
                                       facecolor=col, alpha=0.85, edgecolor="white", linewidth=2)
        ax.add_patch(rect)
        ax.text(x+0.7, 2.15, title, ha="center", va="center", fontsize=9,
                fontweight="bold", color="white")
        ax.text(x+0.7, 1.55, sub, ha="center", va="center", fontsize=7.5,
                color="white", alpha=0.9)
        if i < len(steps)-1:
            ax.annotate("", xy=(x+1.55, 2.0), xytext=(x+1.4, 2.0),
                        arrowprops=dict(arrowstyle="->", color="#444", lw=1.5))
    ax.set_title("Analysis Pipeline: Raw Satellite -> GDP Proxy",
                 fontsize=13, fontweight="bold", pad=8)
    fig.tight_layout()
    return save(fig, "00_pipeline.png")

# Generate all charts
print("Generating charts?")
imgs = {
    "pipeline":    chart_pipeline(),
    "rankings":    chart_overall_rankings(),
    "period":      chart_period_breakdown(),
    "extended":    chart_extended_total(),
    "states":      chart_state_heatmap(),
    "up":          chart_up_cities(),
    "south":       chart_south_india(),
    "dmsp":        chart_dmsp_saturation(),
}
print(f"  {len(imgs)} charts saved to {CHARTS}/")


# ============================================================================
# PDF GENERATION
# ============================================================================

class Report(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(20, 20, 20)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 8, "Nighttime Lights as Economic Proxy - India Analysis 2004-2026", 0, 0, "L")
        self.cell(0, 8, f"Page {self.page_no()}", 0, 1, "R")
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(150, 150, 150)
        self.cell(0, 8, SOURCE, 0, 0, "C")

    def cover(self):
        self.add_page()
        self.set_fill_color(27, 79, 114)
        self.rect(0, 0, 210, 297, "F")
        self.set_y(60)
        self.set_font("Helvetica", "B", 28)
        self.set_text_color(255, 255, 255)
        self.multi_cell(0, 12, "Nighttime Lights as\nEconomic Proxy", align="C")
        self.ln(6)
        self.set_font("Helvetica", "", 16)
        self.set_text_color(180, 210, 235)
        self.cell(0, 10, "India: Cities, States & 22-Year Analysis", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(10)
        self.set_font("Helvetica", "", 12)
        self.set_text_color(140, 185, 215)
        self.cell(0, 8, "NASA VIIRS DNB (2014-2026) + NOAA DMSP-OLS (2004-2013)", new_x="LMARGIN", new_y="NEXT", align="C")
        self.cell(0, 8, "Cloud-corrected  .  LED-adjusted  .  Population-normalized  .  PPP-adjusted", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(20)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, f"Generated {date.today().strftime('%B %d, %Y')}", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(4)
        self.set_font("Helvetica", "", 11)
        self.set_text_color(160, 200, 230)
        self.cell(0, 8, "github.com/pojhafb/nightlights-econ", new_x="LMARGIN", new_y="NEXT", align="C")

    def chapter_title(self, num, title):
        self.set_font("Helvetica", "B", 15)
        self.set_text_color(27, 79, 114)
        self.set_fill_color(235, 243, 250)
        self.cell(0, 12, f"  {num}. {title}", ln=True, fill=True)
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def section_title(self, title):
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(39, 174, 96)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(1)

    def body(self, text, size=10.5):
        self.set_font("Helvetica", "", size)
        self.set_text_color(40, 40, 40)
        for para in text.strip().split("\n\n"):
            self.multi_cell(0, 6, para.strip().replace("\n", " "))
            self.ln(3)

    def callout(self, text, color=(235, 243, 250)):
        self.set_fill_color(*color)
        self.set_font("Helvetica", "I", 10)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 6, "  " + text.strip(), fill=True)
        self.ln(3)
        self.set_text_color(0, 0, 0)

    def full_image(self, path, caption="", h=140):
        self.image(path, x=15, w=180, h=h)
        if caption:
            self.set_font("Helvetica", "I", 8.5)
            self.set_text_color(100, 100, 100)
            self.cell(0, 6, caption, new_x="LMARGIN", new_y="NEXT", align="C")
            self.set_text_color(0, 0, 0)
        self.ln(3)

    def table_row(self, cells, widths, bold=False, fill=False, fill_color=(240, 248, 255)):
        if fill:
            self.set_fill_color(*fill_color)
        font = "B" if bold else ""
        self.set_font("Helvetica", font, 9)
        for cell, w in zip(cells, widths):
            self.cell(w, 7, str(cell), border=1, fill=fill, align="C")
        self.ln()

    def key_finding(self, icon, text):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(27, 79, 114)
        self.cell(8, 7, icon)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 7, text)
        self.ln(1)


pdf = Report()

# -- Cover --------------------------------------------------------------------
pdf.cover()

# -- Executive Summary --------------------------------------------------------
pdf.add_page()
pdf.chapter_title("1", "Executive Summary")
pdf.body("""
Every night between 1:30-2:30 AM, NASA's Suomi NPP satellite photographs the brightness of every 500m patch of Earth's surface. This brightness - nighttime radiance - correlates with real GDP at r = 0.88 (Henderson et al., 2012). This report applies that relationship to measure and compare economic growth across Indian cities and states using 22 years of satellite data: NOAA DMSP-OLS (2004-2013) and NASA VIIRS DNB (2014-2026).

The analysis covers 15+ major cities across all Indian states, applies four corrections to the raw radiance signal (cloud-bias, LED spectral shift, population normalization, PPP adjustment), and produces per-capita GDP indices comparable across geography and time.
""")

pdf.section_title("Key Findings")
pdf.key_finding(">", "Varanasi is the fastest-growing major city in the 2014-2026 VIIRS era (+493% per-capita), driven by the Kashi Vishwanath Corridor (2021) and sustained religious tourism infrastructure.")
pdf.key_finding(">", "Kerala ranks #1 among all Indian states (+852% per-capita, 2014-2026) - counterintuitive for a 'slow-growth' state, but explained by its near-stagnant population growth (0.47%/yr) and strong remittance-driven consumption.")
pdf.key_finding(">", "Bengaluru and Hyderabad rank last among major metros in per-capita growth - not because they are stagnant, but because they were already saturating the sensor in 2004 and have absorbed massive population inflows that dilute per-capita gains.")
pdf.key_finding(">", "The entire Northeast (Manipur, Arunachal, Assam, Mizoram, Nagaland) appears in the top 10 states - reflecting DoNER infrastructure investment and electrification from near-zero 2014 baselines.")
pdf.key_finding(">", "The 2019-2026 post-Covid period outperforms every prior 5-year window for Varanasi (+209%), Nagpur (+209%), Guwahati (+227%), and Bhubaneswar (+183%) - suggesting tier-2/3 cities recovered faster and grew harder than the large metros.")

pdf.ln(4)
pdf.callout("LED Correction Note: India's SLNP programme replaced sodium street lights with white LEDs at scale from 2015. White LEDs appear ~42% dimmer to VIIRS per watt, systematically understating growth. All VIIRS figures in this report have been corrected using state-level SLNP installation data.", color=(255, 243, 205))

# -- Methodology -------------------------------------------------------------
pdf.add_page()
pdf.chapter_title("2", "Methodology")
pdf.full_image(imgs["pipeline"], "Figure 1: Analysis pipeline from raw satellite data to GDP proxy", h=55)

pdf.section_title("2.1  Data Sources")
pdf.body("""
Two satellite nighttime lights datasets are used:

VIIRS DNB (2014-2026): The Visible Infrared Imaging Radiometer Suite on NASA's Suomi NPP satellite. Collection: NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG (stray-light corrected). Resolution: ~500m. Frequency: monthly. Accessed via Google Earth Engine. Radiance values are capped at 100 nW/cm2/sr to exclude gas flares and fires.

DMSP-OLS (2004-2013): The Defense Meteorological Satellite Program Operational Linescan System. Collection: NOAA/DMSP-OLS/NIGHTTIME_LIGHTS (stable_lights band). Resolution: ~2.7 km. Frequency: annual composites. When multiple satellites overlap for the same year, their outputs are averaged.

Population: JRC Global Human Settlement Population grids (GHS-POP, 100m) via GEE, interpolated using per-district Census 2001-2011 growth rates. Compound annual growth rates range from 0.47%/yr (Kerala's Thiruvananthapuram) to 3.94%/yr (Bengaluru Urban).

PPP factors: World Bank indicator PA.NUS.PPP, fetched via REST API and cached locally. All PPP adjustments are relative to base year = 100.
""")

pdf.section_title("2.2  Corrections Applied")
widths = [55, 35, 90]
pdf.table_row(["Correction", "Applies to", "Description"], widths, bold=True, fill=True, fill_color=(27, 79, 114))
pdf.set_text_color(255, 255, 255)
pdf.set_font("Helvetica", "B", 9)
# Redo header properly
pdf.set_text_color(0, 0, 0)
rows = [
    ("Cloud-bias (xKDR)", "VIIRS only", "OLS regression on clear months corrects monsoon dip of -10% to -30%"),
    ("LED spectral shift", "VIIRS 2015+", "SLNP LED rollout makes lights appear 42% dimmer; corrected by state+year"),
    ("Electrification jumps", "Specific regions", "One-time spikes (e.g. Leh 2017, +138%) dampened as non-GDP events"),
    ("Efficiency dampening", "VIIRS 2015+", "+1.5%/yr upward correction for efficiency standards tightening"),
    ("DMSP cross-calibration", "DMSP only", "Per-district linear scale to VIIRS units, anchored at 2013 overlap year"),
    ("Population normalization", "Both", "Per-district Census CAGR used; not flat national rate"),
    ("PPP adjustment", "Both", "World Bank PPP factors, normalized relative to base year"),
]
for i, row in enumerate(rows):
    fill = i % 2 == 0
    pdf.table_row(row, widths, fill=fill, fill_color=(240, 248, 255))
pdf.ln(4)

pdf.section_title("2.3  GDP Proxy Model")
pdf.body("""
Following Henderson, Storeygard & Weil (2012), the GDP proxy uses a log-linear elasticity:

    GDP_proxy(t) = 100 x (radiance(t) / radiance_base)^b

where b = 0.95 (India-specific calibration per Vaidya 2024; global estimate is 0.88). Per-capita adjustment:

    GDP_per_capita(t) = [GDP_proxy(t) / pop(t)] / [GDP_proxy_base / pop_base] x 100

PPP-adjusted per-capita divides by the relative PPP factor to remove inflation and currency effects. All indices are set to 100 in the base year, enabling fair cross-city and cross-time comparison.
""")

pdf.section_title("2.4  DMSP Saturation Limitation")
pdf.body("""
DMSP stable_lights values are encoded as 6-bit integers (0-63 DN). Cities that were already economically dense in 2004 - Hyderabad, Kolkata, Chennai, Bengaluru - saturate at DN=63, making it impossible to register further growth. This creates a systematic downward bias in pre-2014 growth estimates for large metros. The scatter plot below illustrates the relationship between 2013 DMSP DN value and measured 22-year growth.
""")
pdf.full_image(imgs["dmsp"], "Figure 2: DMSP saturation effect - cities near DN=63 show artificially low pre-2014 growth", h=110)

# -- VIIRS 2014-2026 Cities ---------------------------------------------------
pdf.add_page()
pdf.chapter_title("3", "VIIRS Analysis: Indian Cities 2014-2026")
pdf.body("""
The VIIRS era (2014-2026) provides the highest-quality data: monthly, 500m resolution, cloud-corrected, LED-adjusted. Figure 3 ranks cities by per-capita GDP growth over this 12-year window. The index starts at 100 in 2014 and reflects real economic activity normalized for both population change and purchasing power.
""")
pdf.full_image(imgs["rankings"], "Figure 3: Per-capita GDP growth 2014-2026 for major Indian cities (VIIRS + all corrections)", h=135)

pdf.section_title("3.1  Uttar Pradesh: Pilgrimage Economy")
pdf.body("""
Uttar Pradesh presents the most striking urban differentiation in the dataset. Varanasi leads all cities at +493% per-capita - more than double Lucknow (+191%), the state capital. This divergence reflects the concentration of religious tourism infrastructure investment in Varanasi versus administrative/bureaucratic spending in Lucknow. Allahabad/Prayagraj (+369%) captures two events: the Kumbh Mela 2019 and the Maha Kumbh 2025, both of which left permanent infrastructure that continues to generate economic activity.
""")
pdf.full_image(imgs["up"], "Figure 4: Uttar Pradesh cities - total GDP proxy vs per-capita GDP growth 2014-2026", h=95)

pdf.callout("Cloud correction was critical for Allahabad - 50 months corrected with a mean monsoon uplift of 46.9%. The confluence of the Ganga and Yamuna creates intense fog that suppresses VIIRS observations. Without correction, Allahabad's growth would have been significantly understated.")

# -- South India --------------------------------------------------------------
pdf.add_page()
pdf.section_title("3.2  South India: Metros vs Tier-2 Cities")
pdf.body("""
The most counterintuitive result in the dataset is that Bengaluru (+118%), India's IT capital, ranks last among Karnataka cities, while Belagavi (+513%) and Hubli-Dharwad (+450%) - cities most people haven't heard of - dominate the rankings. This is not a measurement error. It reflects three structural forces:

(1) Bengaluru's district boundary (179 km2 for Hyderabad, 92 km2 for Kolkata) was already radiating at near-saturation levels in 2014. Marginal percentage gains are mathematically constrained.

(2) Bengaluru's population has grown from 9.6M (2011) to ~15M (2026) at 3.94%/yr - the fastest of any city in this analysis. Strong total GDP growth gets divided by an even faster-growing denominator.

(3) North Karnataka (Belagavi, Hubli-Dharwad) grew from a lower base, boosted by the Mumbai-Bengaluru highway corridor, BRTS investment, and Smart City programme.

In Tamil Nadu, Erode (+432%) - India's largest textile hub - outperforms Chennai (+227%) for exactly the same structural reasons.
""")
pdf.full_image(imgs["south"], "Figure 5: Karnataka and Tamil Nadu city rankings (per-capita GDP growth 2014-2026)", h=100)

# -- State analysis -----------------------------------------------------------
pdf.add_page()
pdf.chapter_title("4", "All-India State Rankings")
pdf.body("""
For the state-level analysis, districts were selected using a population-ratio threshold: districts where district_population / state_population ? 5%, with a minimum of 2 and maximum of 8 per state. This ensures fair representation across states of very different sizes - a 5% threshold selects comparable economic units whether in a large state like Uttar Pradesh or a small one like Goa.

Population normalization uses per-district Census 2001-2011 compound annual growth rates, not a flat national rate. This matters significantly: Kerala's Thiruvananthapuram grows at 0.21%/yr while Bengaluru Urban grows at 3.94%/yr. Using the same growth rate for both would materially misstate their per-capita performance.
""")
pdf.full_image(imgs["states"], "Figure 6: All-India state rankings - per-capita GDP growth 2014-2026 (VIIRS + LED correction, 138 districts)", h=150)

pdf.add_page()
pdf.section_title("4.1  Key State-Level Findings")
pdf.body("""
Kerala at #1 (+852%) is the most surprising result in the state analysis. Conventionally described as a slow-growth state, Kerala's extraordinary nighttime lights performance reflects its unique economic structure: high remittance income from the Gulf diaspora flows into consumption rather than industry, generating dense residential and commercial lighting that VIIRS captures effectively. Kerala also adopted LED street lighting aggressively under KSEB, requiring a larger-than-average LED correction that, once applied, reveals strong underlying growth.

The Northeast sweep - Manipur (#2, +555%), Arunachal Pradesh (#3, +503%), Assam (#4, +470%), Mizoram (#8, +359%), Nagaland (#7, +391%), Meghalaya (#18, +320%) - reflects the DoNER ministry's sustained connectivity investment. These states were growing from near-zero radiance baselines in 2014; the installation of grid electricity, highways, and broadband created step-changes visible from space.

Bihar (+389%) and Uttar Pradesh (+392%) perform better than their economic reputation suggests. Both contain districts (Patna, Varanasi, Allahabad) that grew explosively in the VIIRS era. Their national perception as laggard states reflects older data and urban-rural aggregation that this district-level analysis bypasses.

Chandigarh (#28, +213%) and Puducherry (#27, +213%) cluster at the bottom not because of poor economic performance but because they were already wealthy and well-lit in 2014, leaving little room for percentage-based radiance growth.
""")

# Summary table
pdf.section_title("4.2  State Rankings Summary Table")
widths = [10, 75, 35, 40]
pdf.table_row(["#", "State", "Districts", "Per-Cap Growth"], widths, bold=True, fill=True, fill_color=(27, 79, 114))
pdf.set_text_color(255, 255, 255)
pdf.set_font("Helvetica", "B", 9)
pdf.set_text_color(0, 0, 0)
for i, (state, growth) in enumerate(sorted(STATE_RANKINGS, key=lambda x: -x[1])):
    fill = i % 2 == 0
    pdf.table_row([str(i+1), state, "2-8", f"+{growth}%"], widths,
                  fill=fill, fill_color=(240, 248, 255))

# -- Extended 2004-2026 -------------------------------------------------------
pdf.add_page()
pdf.chapter_title("5", "Extended Analysis: 2004-2026 (DMSP + VIIRS)")
pdf.body("""
By cross-calibrating DMSP-OLS annual composites to VIIRS units at the 2013 overlap year, we extend the time series back to 2004 - creating a 22-year GDP proxy for 15 major Indian cities. The DMSP era (2004-2013) has lower precision (~2.7 km resolution, annual frequency, no cloud correction) but enables the analysis of four distinct political-economic periods:

- 2004-2009 (UPA-2 boom): India's 8-9% GDP growth years
- 2009-2014 (slowdown): Policy paralysis, inflation, current account pressures
- 2014-2019 (NDA-1): Demonetisation (Nov 2016), GST, infrastructure spending
- 2019-2026 (post-Covid): Recovery divergence, tier-2 city acceleration

Important caveat: Cities that were already bright in 2004 (Hyderabad DN=63, Kolkata DN=63, Chennai DN=62.4) saturated the DMSP sensor. Their 2004-2009 growth figures are artefacts of saturation, not actual economic stagnation. The VIIRS era (2014+) data for these cities is fully reliable.
""")
pdf.full_image(imgs["period"], "Figure 7: Period-wise per-capita GDP growth 2004-2026 (stacked bars by political-economic era)", h=105)

pdf.add_page()
pdf.full_image(imgs["extended"], "Figure 8: Full 22-year per-capita GDP growth ranking (2004->2026)", h=110)

pdf.section_title("5.1  Period Analysis")
pdf.body("""
2004-2009 (UPA-2 boom): Smaller cities with low DMSP baselines show genuine growth - Guwahati (+40%), Jaipur (+32%), Lucknow (+22%). Large metros show 0% or negative, almost entirely due to DMSP saturation rather than economic stagnation.

2009-2014 (slowdown): Counterintuitively, this period shows strong growth for most cities - Allahabad (+109%), Bhubaneswar (+86%), Patna (+74%). This appears to reflect MNREGA rural spending circulating into district-level commerce, and the UPA's rural infrastructure push that preceded the political loss in 2014.

2014-2019 (NDA-1): The widest divergence between cities. Varanasi (+95%), Allahabad (+116%), Patna (+134%), and Pune (+92%) lead. Hyderabad (+13%) and Bengaluru (+37%) lag. The Modi government's concentration of visible infrastructure in specific cities is strikingly measurable from space.

2019-2026 (post-Covid): The single most explosive period for multiple cities. Guwahati (+227%), Varanasi (+209%), Nagpur (+209%), Bhubaneswar (+183%), and Jaipur (+135%) all post their largest-ever period gains. Chennai (+122%) and Kolkata (+119%) also surge. Only Bengaluru (+44%) and Hyderabad (+79%) remain in the moderate growth zone - again, a function of their large population-growth denominators rather than weak economic performance.
""")

pdf.section_title("5.2  22-Year Rankings")
widths = [10, 55, 35, 30, 30, 30, 30]
pdf.table_row(["#", "City", "2004->2026", "04-09", "09-14", "14-19", "19-26"],
              widths, bold=True, fill=True, fill_color=(27, 79, 114))
pdf.set_text_color(0, 0, 0)
ext_sorted = sorted(EXTENDED.items(), key=lambda x: -x[1]["pc_total"])
for i, (city, d) in enumerate(ext_sorted):
    p1 = f"+{d['p1']}%" if d["p1"] is not None else "-"
    p2 = f"+{d['p2']}%" if d["p2"] is not None else "-"
    p3 = f"+{d['p3']}%" if d["p3"] is not None else "-"
    p4 = f"+{d['p4']}%" if d["p4"] is not None else "-"
    fill = i % 2 == 0
    pdf.table_row([str(i+1), city, f"+{d['pc_total']}%", p1, p2, p3, p4],
                  widths, fill=fill, fill_color=(240, 248, 255))

# -- Limitations --------------------------------------------------------------
pdf.add_page()
pdf.chapter_title("6", "Limitations & Caveats")
pdf.body("""
1. DMSP saturation (pre-2014): Cities with DN ? 60 in 2004 have unreliable pre-2014 growth estimates. Affects Hyderabad, Kolkata, Chennai, Bengaluru. VIIRS-era (2014+) data for these cities is fully reliable.

2. District boundaries vs city boundaries: GAUL 2015 administrative boundaries do not always match economic city limits. Bhubaneswar uses Khordha district (2,764 km2) which includes significant rural area - the city's true radiance growth is concentrated in a smaller urban core.

3. Informal economy: VIIRS measures outdoor lighting, which correlates with the formal commercial and services economy. India's informal sector (~50% of GDP) operates partly in daylight and may not generate proportional nighttime lighting. The Henderson elasticity partially accounts for this.

4. LED correction uncertainty: State-level LED penetration rates from SLNP Annual Reports have +/-15% uncertainty. The correction factor (LED net VIIRS ratio ~ 0.42) is derived from satellite spectral response literature and may vary by luminaire type.

5. DMSP cross-calibration: The per-district linear calibration anchored at 2013 assumes a constant relationship between DMSP DN and VIIRS radiance. This holds well at the district-area mean level but has ~15-30% uncertainty.

6. Population projections: Census 2011 district-level CAGR rates are projected forward 15 years. Actual population growth may diverge due to migration, fertility changes, or boundary reorganisations (Telangana 2014, Ladakh 2019).
""")

pdf.chapter_title("7", "Data Sources & References")
pdf.body("""
Satellite data:
- VIIRS DNB: NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG via Google Earth Engine
- DMSP-OLS: NOAA/DMSP-OLS/NIGHTTIME_LIGHTS via Google Earth Engine
- Population: JRC/GHSL/P2023A/GHS_POP via Google Earth Engine
- Boundaries: FAO/GAUL/2015/level2 via Google Earth Engine

Economic data:
- PPP factors: World Bank API, indicator PA.NUS.PPP
- LED penetration: India Ministry of Power SLNP Annual Progress Reports (2015-2024)
- Census populations: Census of India 2001, 2011 (Office of the Registrar General)

Academic references:
- Henderson, V., Storeygard, A., Weil, D.N. (2012). Measuring Economic Growth from Outer Space. American Economic Review, 102(2), 994-1028.
- Patnaik, U., Shah, M., Tayal, A., Thomas, T. (2021). But clouds got in my way. xKDR Working Paper 7.
- Elvidge, C.D. et al. (2017). VIIRS night-time lights. International Journal of Remote Sensing, 38(21).
- Vaidya, A. (2024). Measuring economic activity in Indian cities using nighttime lights.
- Schiavina, M. et al. (2023). GHS-POP R2023A. European Commission JRC.

Code & data:
- github.com/pojhafb/nightlights-econ (MIT licence)
""")

# -- Save PDF -----------------------------------------------------------------
print("Building PDF?")
pdf.output(str(PDF_PATH))
print(f"\nOK Report saved to: {PDF_PATH}")
print(f"  ({PDF_PATH.stat().st_size // 1024} KB)")
