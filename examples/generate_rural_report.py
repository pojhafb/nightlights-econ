"""
Rural India Nighttime Lights Report Generator
Outputs: ~/Desktop/rural_india_report.pdf
Run:     python examples/generate_rural_report.py
"""

import matplotlib
matplotlib.use("Agg")

import sys, os
from pathlib import Path
from datetime import date

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd
from fpdf import FPDF

REPO     = Path(__file__).parent.parent
REPORTS  = REPO / "reports" / "rural_analysis"
OUT_DIR  = Path.home() / "Desktop" / "rural_report"
PDF_PATH = Path.home() / "Desktop" / "rural_india_report.pdf"
CHARTS   = OUT_DIR / "charts"
OUT_DIR.mkdir(exist_ok=True)
CHARTS.mkdir(exist_ok=True)

PALETTE = ["#1B4F72", "#27AE60", "#E74C3C", "#F39C12", "#8E44AD",
           "#2C3E50", "#117A65", "#C0392B", "#D4AC0D", "#1A5276"]
BG      = "#FAFAFA"
SOURCE  = "Source: NASA VIIRS DNB / JRC GHS-SMOD / World Bank / Census of India"

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

# ── Embedded results ──────────────────────────────────────────────────────────

DONUT = [
    ("Varanasi",        369,  753),
    ("Patna",           338,  672),
    ("Khordha",         137,  405),
    ("Pune",            234,  489),
    ("Coimbatore",      212,  440),
    ("Lucknow",         116,  304),
    ("Jaipur",          157,  267),
]

CLUSTERS = {
    "Tribal Belt\n(Jharkhand/CG)": {
        "mean": 1516,
        "color": PALETTE[2],
        "districts": [
            ("Dantewada",         3539),
            ("Gumla",             1114),
            ("Bastar",            1016),
            ("Pashchim Singhbhum", 393),
        ],
        "note": "Naxal-affected. Near-zero 2014 baseline. Security infrastructure and rural electrification visible.",
    },
    "KBK Region\n(Odisha)": {
        "mean": 671,
        "color": PALETTE[3],
        "districts": [
            ("Nuapada",   853),
            ("Kalahandi", 586),
            ("Koraput",   575),
        ],
        "note": "Kalahandi-Bolangir-Koraput. Historically India's poorest. KALIA scheme + SAADA visible.",
    },
    "Marathwada\n(Drought)": {
        "mean": 560,
        "color": PALETTE[0],
        "districts": [
            ("Osmanabad", 635),
            ("Latur",     622),
            ("Bid",       521),
            ("Nanded",    462),
        ],
        "note": "Maharashtra drought belt. Recurring water crisis. PM Krishi Sinchai Yojana irrigation investment.",
    },
    "Bundelkhand\n(Drought Belt)": {
        "mean": 383,
        "color": PALETTE[4],
        "districts": [
            ("Lalitpur",   583),
            ("Banda",      472),
            ("Jhansi",     382),
            ("Chhatarpur", 363),
            ("Tikamgarh",  358),
            ("Hamirpur",   262),
            ("Mahoba",     259),
        ],
        "note": "UP+MP. Bundelkhand Expressway (2020) and Jal Shakti mission visible in post-2019 uptick.",
    },
    "Vidarbha\n(Cotton Belt)": {
        "mean": 303,
        "color": PALETTE[1],
        "districts": [
            ("Buldana",  388),
            ("Akola",    298),
            ("Washim",   291),
            ("Wardha",   290),
            ("Amravati", 280),
            ("Yavatmal", 271),
        ],
        "note": "Farmer distress region. Lowest performing cluster. Cotton MSP and debt waiver effects modest.",
    },
}

# ── Chart generators ──────────────────────────────────────────────────────────

def chart_pipeline_rural():
    """Rural-specific pipeline diagram."""
    fig, ax = plt.subplots(figsize=(14, 3.5))
    ax.set_xlim(0, 14); ax.set_ylim(0, 4); ax.axis("off")
    steps = [
        ("VIIRS DNB", "500m monthly\n2014-2026", PALETTE[0]),
        ("GHS-SMOD\nMask", "Rural pixels\nonly (code<=13)", PALETTE[3]),
        ("Cloud\nCorrection", "xKDR algorithm\nMonsoon bias", PALETTE[2]),
        ("LED\nCorrection", "Rural LED curve\n(lower penetration)", PALETTE[4]),
        ("Pop Norm.", "Census CAGR\nper district", PALETTE[1]),
        ("GDP\nProxy", "Henderson b=0.95\nper-capita index", "#117A65"),
    ]
    for i, (title, sub, col) in enumerate(steps):
        x = i * 2.25 + 0.5
        rect = mpatches.FancyBboxPatch((x, 1.0), 1.8, 2.0,
                                       boxstyle="round,pad=0.1",
                                       facecolor=col, alpha=0.88,
                                       edgecolor="white", linewidth=2)
        ax.add_patch(rect)
        ax.text(x+0.9, 2.25, title, ha="center", va="center",
                fontsize=9.5, fontweight="bold", color="white")
        ax.text(x+0.9, 1.55, sub, ha="center", va="center",
                fontsize=7.5, color="white", alpha=0.92)
        if i < len(steps)-1:
            ax.annotate("", xy=(x+1.95, 2.0), xytext=(x+1.8, 2.0),
                        arrowprops=dict(arrowstyle="->", color="#444", lw=1.5))
    ax.set_title("Rural Analysis Pipeline: VIIRS + GHS Settlement Model Masking",
                 fontsize=12, fontweight="bold", pad=6)
    fig.tight_layout()
    return save(fig, "00_rural_pipeline.png")


def chart_smod_explainer():
    """Visual showing GHS-SMOD classification codes."""
    codes   = [10, 11, 12, 13, 21, 22, 23, 30]
    labels  = ["Water", "Very low\ndensity rural", "Low density\nrural",
               "Rural\ncluster", "Suburban /\nperi-urban",
               "Semi-dense\nurban", "Dense\nurban", "Urban\ncentre"]
    colors  = ["#5DADE2", "#A9DFBF", "#52BE80", "#1E8449",
               "#F7DC6F", "#F39C12", "#E74C3C", "#922B21"]
    include = [True, True, True, True, False, False, False, False]

    fig, ax = plt.subplots(figsize=(14, 3))
    ax.axis("off")
    for i, (code, label, col, inc) in enumerate(zip(codes, labels, colors, include)):
        x = i * 1.65 + 0.3
        rect = mpatches.FancyBboxPatch((x, 0.5), 1.4, 2.0,
                                       boxstyle="round,pad=0.05",
                                       facecolor=col, alpha=0.9,
                                       edgecolor="white", linewidth=2)
        ax.add_patch(rect)
        ax.text(x+0.7, 2.05, f"Code {code}", ha="center", va="center",
                fontsize=8, fontweight="bold", color="white")
        ax.text(x+0.7, 1.4, label, ha="center", va="center",
                fontsize=7.5, color="white")
        marker = "KEPT" if inc else "EXCLUDED"
        marker_col = "#1E8449" if inc else "#922B21"
        ax.text(x+0.7, 0.7, marker, ha="center", va="center",
                fontsize=8, fontweight="bold", color=marker_col,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.85))
    ax.set_xlim(0, 14); ax.set_ylim(0, 3)
    ax.set_title("GHS-SMOD Settlement Classification: Which Pixels Are 'Rural'",
                 fontsize=12, fontweight="bold", y=1.02)
    fig.tight_layout()
    return save(fig, "01_smod_explainer.png")


def chart_donut_comparison():
    """Urban vs rural growth bars for each district."""
    districts = [d[0] for d in DONUT]
    urban_g   = [d[1] for d in DONUT]
    rural_g   = [d[2] for d in DONUT]
    diff      = [r - u for u, r in zip(urban_g, rural_g)]

    x = np.arange(len(districts))
    w = 0.35
    fig, (ax_main, ax_diff) = plt.subplots(1, 2, figsize=(16, 7),
                                            gridspec_kw={"width_ratios": [2, 1]})

    # Main: side-by-side bars
    bars_u = ax_main.bar(x - w/2, urban_g, w, label="Urban core pixels",
                         color=PALETTE[0], alpha=0.88)
    bars_r = ax_main.bar(x + w/2, rural_g, w, label="Rural hinterland pixels",
                         color=PALETTE[1], alpha=0.88)
    for i, (u, r) in enumerate(zip(urban_g, rural_g)):
        ax_main.text(i-w/2, u+6, f"+{u}%", ha="center", fontsize=8.5,
                     color=PALETTE[0], fontweight="bold")
        ax_main.text(i+w/2, r+6, f"+{r}%", ha="center", fontsize=8.5,
                     color=PALETTE[1], fontweight="bold")
    ax_main.set_xticks(x)
    ax_main.set_xticklabels(districts, fontsize=11)
    ax_main.set_ylabel("Per-Capita GDP Growth % (2014-2026)", fontsize=11)
    ax_main.set_title("Urban Core vs Rural Hinterland\nPer-Capita GDP Growth within Same District",
                       fontsize=12, fontweight="bold")
    ax_main.legend(fontsize=10)
    ax_main.axhline(0, color="#888", linewidth=0.8)

    # Right: rural advantage
    colors_diff = [PALETTE[1] if d > 0 else PALETTE[2] for d in diff]
    sorted_pairs = sorted(zip(diff, districts, colors_diff), key=lambda x: x[0], reverse=True)
    diff_s  = [p[0] for p in sorted_pairs]
    names_s = [p[1] for p in sorted_pairs]
    cols_s  = [p[2] for p in sorted_pairs]
    bars_d = ax_diff.barh(names_s, diff_s, color=cols_s, height=0.6)
    for bar, val in zip(bars_d, diff_s):
        ax_diff.text(bar.get_width()+3, bar.get_y()+bar.get_height()/2,
                     f"+{val:.0f}pp", va="center", fontsize=9,
                     fontweight="bold", color="#333")
    ax_diff.axvline(0, color="#888", linewidth=0.8)
    ax_diff.set_xlabel("Rural advantage (percentage points)", fontsize=10)
    ax_diff.set_title("Rural Outperformance\n(Rural minus Urban growth)",
                       fontsize=11, fontweight="bold")

    for ax in (ax_main, ax_diff):
        ax.set_facecolor(BG)
        ax.grid(True, axis="y" if ax == ax_main else "x", color="#E0E0E0")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    ax_main.annotate(SOURCE, xy=(0, -0.14), xycoords="axes fraction",
                     fontsize=7.5, color="#777")
    fig.tight_layout()
    return save(fig, "02_donut_comparison.png")


def chart_cluster_overview():
    """Cluster mean rankings with district breakdown."""
    cluster_names = list(CLUSTERS.keys())
    means = [CLUSTERS[c]["mean"] for c in cluster_names]
    colors = [CLUSTERS[c]["color"] for c in cluster_names]

    sorted_pairs = sorted(zip(means, cluster_names, colors), reverse=True)
    means_s  = [p[0] for p in sorted_pairs]
    names_s  = [p[1] for p in sorted_pairs]
    cols_s   = [p[2] for p in sorted_pairs]

    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.barh(names_s, means_s, color=cols_s, height=0.6, alpha=0.9)
    for bar, val in zip(bars, means_s):
        ax.text(bar.get_width()+15, bar.get_y()+bar.get_height()/2,
                f"+{val:,}%", va="center", fontsize=11, fontweight="bold")
    median = float(np.median(means))
    ax.axvline(median, color="#888", linewidth=1.2, linestyle="--",
               label=f"Median ({median:.0f}%)")
    ax.set_xlabel("Mean Per-Capita GDP Growth % across cluster (2014-2026)", fontsize=11)
    ax.set_title("Rural India: Thematic Cluster Rankings\nPer-Capita GDP Growth via VIIRS (2014-2026)",
                 fontsize=13, fontweight="bold", pad=12)
    ax.legend(fontsize=10)
    ax.set_facecolor(BG)
    ax.grid(True, axis="x", color="#E0E0E0")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.annotate(SOURCE, xy=(0, -0.12), xycoords="axes fraction",
                fontsize=7.5, color="#777")
    fig.tight_layout()
    return save(fig, "03_cluster_overview.png")


def chart_cluster_detail(cluster_name, data):
    """Individual district breakdown for one cluster."""
    dists  = [d[0] for d in data["districts"]]
    vals   = [d[1] for d in data["districts"]]
    col    = data["color"]

    fig, ax = plt.subplots(figsize=(10, max(4, len(dists)*0.9)))
    bars = ax.barh(dists[::-1], vals[::-1], color=col, height=0.6, alpha=0.9)
    for bar, val in zip(bars, vals[::-1]):
        ax.text(bar.get_width()+10, bar.get_y()+bar.get_height()/2,
                f"+{val:,}%", va="center", fontsize=10, fontweight="bold")
    mean_val = data["mean"]
    ax.axvline(mean_val, color="#555", linewidth=1.2, linestyle="--",
               label=f"Cluster mean (+{mean_val:,}%)")
    ax.set_xlabel("Per-Capita GDP Growth % (2014-2026)", fontsize=11)
    short_name = cluster_name.replace("\n", " ")
    ax.set_title(f"{short_name}: District-Level Breakdown",
                 fontsize=12, fontweight="bold", pad=10)
    ax.legend(fontsize=9)
    ax.set_facecolor(BG)
    ax.grid(True, axis="x", color="#E0E0E0")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.annotate(SOURCE, xy=(0, -0.12), xycoords="axes fraction",
                fontsize=7.5, color="#777")
    fig.tight_layout()
    slug = short_name.split("(")[0].strip().lower().replace(" ", "_")
    return save(fig, f"04_{slug}_detail.png")


def chart_all_clusters_combined():
    """All districts from all clusters in one ranked chart."""
    all_items = []
    for cname, cdata in CLUSTERS.items():
        short = cname.split("(")[0].strip().replace("\n", "")
        for dist, val in cdata["districts"]:
            all_items.append((dist, val, short, cdata["color"]))

    all_items.sort(key=lambda x: x[1])

    names  = [f"{x[0]}\n({x[2]})" for x in all_items]
    vals   = [x[1] for x in all_items]
    colors = [x[3] for x in all_items]
    n = len(all_items)

    fig, ax = plt.subplots(figsize=(12, max(8, n * 0.52)))
    bars = ax.barh(names, vals, color=colors, height=0.72, alpha=0.9)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_width()+20, bar.get_y()+bar.get_height()/2,
                f"+{val:,}%", va="center", fontsize=8.5, fontweight="bold")
    ax.set_xlabel("Per-Capita GDP Growth % (2014-2026)", fontsize=11)
    ax.set_title("All Rural Districts Ranked: Per-Capita GDP Growth 2014-2026\nColoured by cluster",
                 fontsize=12, fontweight="bold", pad=12)

    # Legend for clusters
    handles = [mpatches.Patch(color=cdata["color"],
                              label=cname.replace("\n", " ").split("(")[0].strip())
               for cname, cdata in CLUSTERS.items()]
    ax.legend(handles=handles, fontsize=9, loc="lower right")

    for label in ax.get_yticklabels():
        label.set_fontsize(8.5)
    ax.set_facecolor(BG)
    ax.grid(True, axis="x", color="#E0E0E0")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.annotate(SOURCE, xy=(0, -0.04), xycoords="axes fraction",
                fontsize=7.5, color="#777")
    fig.tight_layout()
    return save(fig, "05_all_rural_districts.png")


# ── Generate all charts ───────────────────────────────────────────────────────
print("Generating charts...")
imgs = {
    "pipeline":    chart_pipeline_rural(),
    "smod":        chart_smod_explainer(),
    "donut":       chart_donut_comparison(),
    "clusters":    chart_cluster_overview(),
    "combined":    chart_all_clusters_combined(),
}
cluster_detail_imgs = {}
for cname, cdata in CLUSTERS.items():
    img = chart_cluster_detail(cname, cdata)
    cluster_detail_imgs[cname] = img

print(f"  {len(imgs) + len(cluster_detail_imgs)} charts saved.")


# ════════════════════════════════════════════════════════════════════════════
# PDF
# ════════════════════════════════════════════════════════════════════════════

class Report(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 8, "Rural India: Nighttime Lights Economic Analysis 2014-2026", 0, 0, "L")
        self.cell(0, 8, f"Page {self.page_no()}", 0, 1, "R")
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(150, 150, 150)
        self.cell(0, 8, SOURCE, 0, 0, "C")

    def cover(self):
        self.add_page()
        self.set_fill_color(27, 110, 60)   # dark green for rural theme
        self.rect(0, 0, 210, 297, "F")
        self.set_y(55)
        self.set_font("Helvetica", "B", 30)
        self.set_text_color(255, 255, 255)
        self.multi_cell(0, 13, "Rural India\nNighttime Lights\nEconomic Analysis",
                        align="C")
        self.ln(8)
        self.set_font("Helvetica", "", 15)
        self.set_text_color(180, 230, 200)
        self.multi_cell(0, 8, "Urban vs Rural Pixel-Level Comparison\nThematic Agrarian Cluster Analysis",
                        align="C")
        self.ln(12)
        self.set_font("Helvetica", "", 11)
        self.set_text_color(140, 210, 175)
        self.cell(0, 7, "Vidarbha  .  Bundelkhand  .  KBK Region  .  Tribal Belt  .  Marathwada",
                  new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(20)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(255, 255, 255)
        self.cell(0, 9, f"Generated {date.today().strftime('%B %d, %Y')}",
                  new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(4)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(160, 215, 185)
        self.cell(0, 7, "github.com/pojhafb/nightlights-econ",
                  new_x="LMARGIN", new_y="NEXT", align="C")

    def ch(self, num, title):
        self.set_font("Helvetica", "B", 15)
        self.set_text_color(27, 110, 60)
        self.set_fill_color(235, 250, 240)
        self.cell(0, 12, f"  {num}. {title}", new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def sec(self, title):
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(27, 110, 60)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(1)

    def body(self, text, size=10.5):
        self.set_font("Helvetica", "", size)
        self.set_text_color(40, 40, 40)
        for para in text.strip().split("\n\n"):
            self.multi_cell(0, 6, para.strip().replace("\n", " "))
            self.ln(3)

    def callout(self, text, color=(235, 250, 240)):
        self.set_fill_color(*color)
        self.set_font("Helvetica", "I", 10)
        self.set_text_color(40, 80, 50)
        self.multi_cell(0, 6, "  " + text.strip(), fill=True)
        self.ln(3)
        self.set_text_color(0, 0, 0)

    def img(self, path, caption="", h=120):
        self.image(path, x=15, w=180, h=h)
        if caption:
            self.set_font("Helvetica", "I", 8.5)
            self.set_text_color(100, 100, 100)
            self.cell(0, 6, caption, new_x="LMARGIN", new_y="NEXT", align="C")
            self.set_text_color(0, 0, 0)
        self.ln(3)

    def trow(self, cells, widths, bold=False, fill=False, fc=(240, 250, 243)):
        if fill:
            self.set_fill_color(*fc)
        self.set_font("Helvetica", "B" if bold else "", 9)
        for cell, w in zip(cells, widths):
            self.cell(w, 7, str(cell), border=1, fill=fill, align="C")
        self.ln()

    def finding(self, num, text):
        self.set_font("Helvetica", "B", 10.5)
        self.set_text_color(27, 110, 60)
        self.cell(8, 7, str(num) + ".")
        self.set_font("Helvetica", "", 10.5)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 7, text)
        self.ln(1)


pdf = Report()
pdf.set_auto_page_break(auto=True, margin=20)
pdf.set_margins(20, 20, 20)

# ── Cover ────────────────────────────────────────────────────────────────────
pdf.cover()

# ── Executive Summary ────────────────────────────────────────────────────────
pdf.add_page()
pdf.ch("1", "Executive Summary")
pdf.body("""
This report analyses economic growth in rural and non-urban India using NASA VIIRS satellite nighttime lights data (2014-2026). Two methodologies are applied:

Option 1 - District Donut: For 7 major Indian districts, VIIRS radiance is extracted separately for urban pixels and rural pixels using the JRC Global Human Settlement Settlement Model (GHS-SMOD). This separates the economic signal of city cores from the surrounding rural hinterland within the same administrative boundary.

Option 3 - Thematic Rural Clusters: 26 districts across 5 historically underserved agrarian regions are analysed: Vidarbha (cotton belt), Bundelkhand (drought belt), KBK region (Odisha), Tribal Belt (Jharkhand/Chhattisgarh), and Marathwada (drought-prone Maharashtra).
""")

pdf.sec("Key Findings")
pdf.finding("1", "Rural hinterland outperforms urban core in ALL 7 districts tested. The rural ring grows 110-384 percentage points faster than the city centre within the same district. Varanasi's rural hinterland (+753%) grows more than twice as fast as its city core (+369%).")
pdf.finding("2", "Tribal Belt districts (Jharkhand/Chhattisgarh) show the highest cluster growth (+1,516% mean). Dantewada alone posts +3,539% -- the most extreme figure in this dataset -- driven by near-zero 2014 baseline and security infrastructure investment in a Naxal-affected zone.")
pdf.finding("3", "KBK Region (Odisha's Kalahandi-Bolangir-Koraput) grows at +671%, outperforming both Marathwada (+560%) and Bundelkhand (+383%) despite being India's historically poorest region. The Odisha government's targeted SAADA programme and KALIA farmer scheme are visible in the satellite record.")
pdf.finding("4", "Vidarbha (cotton belt, +303%) is the weakest-performing rural cluster -- consistent with the persistent agrarian distress narrative. Cotton MSP interventions and debt waivers have not produced measurable nighttime lights growth relative to other rural regions.")
pdf.finding("5", "The rural LED correction used here is lower than the urban correction (peak ~74% LED penetration by 2026 vs ~97% for urban). SLNP targeted municipal street lights, not rural areas, making raw rural VIIRS signals more reliable with less correction needed.")

pdf.ln(3)
pdf.callout("Note on Dantewada (+3,539%): This figure should not be read as genuine sustained economic growth. It reflects an extreme low-base effect -- Dantewada was among the darkest districts in India in 2014 (Maoist conflict suppressed all development activity). Any new lights -- CRPF forward bases, a paved road, newly electrified hamlets -- produce enormous percentage gains from near-zero. The signal confirms infrastructure reach, not necessarily civilian economic prosperity.", color=(255, 245, 200))

# ── Methodology ──────────────────────────────────────────────────────────────
pdf.add_page()
pdf.ch("2", "Methodology")

pdf.sec("2.1  GHS Settlement Model (SMOD) for Urban/Rural Separation")
pdf.img(imgs["smod"], "Figure 1: GHS-SMOD classification codes -- codes <=13 retained as rural", h=55)
pdf.body("""
The JRC Global Human Settlement Settlement Model (GHS-SMOD, 2020, 1km resolution) classifies each pixel into one of 8 settlement density classes. For this analysis, pixels with codes <=13 (water, very low density rural, low density rural, rural cluster) are defined as 'rural'. Pixels with codes 21-30 (suburban, semi-dense urban, dense urban, urban centre) are defined as 'urban'.

For the district donut analysis, VIIRS radiance is extracted twice for each district: once masked to retain only urban pixels, and once masked to retain only rural pixels. The resulting time series are then processed independently through the full pipeline (cloud correction, LED correction, GDP proxy).

This approach is more principled than administrative boundaries because it uses satellite-derived settlement data to define urban vs rural, rather than relying on municipal boundaries that vary in size and definition across states.
""")

pdf.img(imgs["pipeline"], "Figure 2: Rural analysis pipeline (identical to urban pipeline but with GHS-SMOD mask applied)", h=55)

pdf.sec("2.2  LED Correction for Rural Areas")
pdf.body("""
The LED correction applied to rural areas uses a lower penetration curve than the urban analysis. India's SLNP programme primarily targeted municipal street lights in towns and cities. Rural electrification schemes (DDUGJY, Saubhagya) installed grid connections but with far fewer LED street lights per capita.

Rural LED penetration estimate used: ~0% in 2014, reaching ~74% by 2026 (vs ~97% for major urban areas). This lower correction means raw rural radiance signals are slightly more reliable than urban signals -- the LED spectral shift bias is smaller.

The Saubhagya scheme (2017-2019) is handled as a one-time electrification event for specific states rather than as LED correction, since it brought grid power to previously unelectrified households.
""")

# ── Option 1: Donut ──────────────────────────────────────────────────────────
pdf.add_page()
pdf.ch("3", "Option 1: Urban Core vs Rural Hinterland")
pdf.body("""
The district donut analysis separates the VIIRS signal within 7 major Indian districts into urban core pixels (GHS-SMOD code > 13) and rural hinterland pixels (code <=13). All other pipeline steps are identical -- cloud correction, LED correction at the appropriate penetration rate, population normalization using Census 2011-based district CAGR, and PPP adjustment.
""")
pdf.img(imgs["donut"], "Figure 3: Urban vs Rural per-capita GDP growth (2014-2026) within the same district boundary", h=120)

pdf.sec("3.1  District-by-District Results")
widths = [42, 30, 30, 32, 40]
pdf.trow(["District", "Urban %", "Rural %", "Rural Adv.", "Interpretation"],
         widths, bold=True, fill=True, fc=(27, 110, 60))
pdf.set_text_color(255, 255, 255)
pdf.set_text_color(0, 0, 0)
rows = [
    ("Varanasi",   "+369%", "+753%", "+384pp", "Rural pilgrimage hinterland explodes"),
    ("Patna",      "+338%", "+672%", "+334pp", "Bihar peri-urban industrial strip"),
    ("Khordha",    "+137%", "+405%", "+268pp", "Bhubaneswar Smart City rural spillover"),
    ("Pune",       "+234%", "+489%", "+256pp", "Chakan/Talegaon auto corridor"),
    ("Coimbatore", "+212%", "+440%", "+228pp", "Tiruppur textile ring growth"),
    ("Lucknow",    "+116%", "+304%", "+189pp", "UP state capital hinterland"),
    ("Jaipur",     "+157%", "+267%", "+110pp", "Tourism and handicraft rural towns"),
]
for i, row in enumerate(rows):
    pdf.trow(row, widths, fill=(i%2==0))
pdf.ln(4)

pdf.body("""
The consistent rural outperformance across all 7 districts is one of the most striking findings in this entire analysis. Several drivers likely explain this:

Peri-urban industrialisation: Manufacturing corridors have moved outward from city cores due to land cost, labour availability, and industrial policy (Pune's Chakan belt, Coimbatore's Tiruppur ring, Patna's Hajipur EPIP zone). These are classified as rural by SMOD but generate intense nighttime lighting from factories and worker housing.

Rural electrification catch-up: Saubhagya scheme (2017-2019) brought first-time grid connections to ~28 million rural households. Previously dark villages suddenly show up in the VIIRS signal. City pixels were already electrified in 2014 -- they had no equivalent catch-up effect.

Agricultural market modernisation: Mandis, cold storage facilities, and agri-processing units generate concentrated lighting in otherwise rural areas. The eNAM (electronic national agriculture market) rollout post-2016 encouraged physical market upgrades.

PMGSY road lighting: Rural road construction under the Pradhan Mantri Gram Sadak Yojana includes street lighting at junctions and villages, directly adding to VIIRS-detectable radiance.
""")

# ── Option 3: Clusters ───────────────────────────────────────────────────────
pdf.add_page()
pdf.ch("4", "Option 3: Thematic Rural Cluster Analysis")
pdf.body("""
Five historically underserved agrarian regions of India are analysed through their constituent districts. These regions were chosen because they represent distinct types of rural economic challenge -- drought stress, commodity dependence, conflict, and extreme poverty -- and because they are frequently discussed in policy contexts without reliable economic data.
""")
pdf.img(imgs["clusters"], "Figure 4: Rural cluster rankings -- mean per-capita GDP growth across districts (2014-2026)", h=85)
pdf.img(imgs["combined"], "Figure 5: All 26 rural districts ranked individually", h=155)

# Cluster sections
pdf.add_page()
cluster_items = list(CLUSTERS.items())

for i, (cname, cdata) in enumerate(cluster_items):
    short = cname.replace("\n", " ")
    pdf.sec(f"4.{i+1}  {short}")
    pdf.img(cluster_detail_imgs[cname],
            f"Figure {6+i}: {short} -- district breakdown",
            h=85 if len(cdata['districts']) <= 4 else 110)

    note = cdata["note"]
    dists_text = ", ".join(f"{d} (+{v:,}%)" for d, v in sorted(cdata["districts"], key=lambda x: -x[1]))
    cluster_narrative = {
        "Tribal Belt\n(Jharkhand/CG)": """The tribal belt of Jharkhand and Chhattisgarh represents India's most extreme low-base case. Dantewada and Bastar districts were effectively economic dark zones in 2014 -- active Maoist conflict suppressed all infrastructure activity. The +3,539% figure for Dantewada and +1,016% for Bastar must be interpreted as the scale of the security-infrastructure push that followed the CRPF surge operations of 2017-2021, combined with the first-time electrification of remote tribal hamlets under Saubhagya. Gumla (+1,114%) in Jharkhand shows similar dynamics. These are real infrastructure gains, but conflating them with civilian GDP growth would be misleading. Pashchim Singhbhum (+393%) -- home to Tata Steel's Jamshedpur -- performs more moderately because it had a higher 2014 baseline.""",

        "KBK Region\n(Odisha)": """The Kalahandi-Bolangir-Koraput (KBK) region of Odisha has been India's symbol of extreme poverty since the 1970s famine coverage. The +671% cluster mean represents genuine economic progress that contradicts the dominant narrative. The Odisha state government's targeted KBK Special Area Development Authority (SAADA) programme, combined with the KALIA direct benefit scheme for farmers and sustained road investment, appears to have produced measurable nighttime lights growth. Nuapada's +853% is the strongest, reflecting its particularly low 2014 baseline and the PMGSY road connectivity that reached it from 2016. This data supports the view that Odisha's governance improvements over the past decade have had real economic consequences.""",

        "Marathwada\n(Drought)": """Marathwada's +560% cluster mean is higher than might be expected given the region's recurring drought coverage and political attention. Osmanabad (+635%) and Latur (+622%) lead, both benefiting from the Jalyukt Shivar Abhiyan (watershed development programme, 2015-2019) and the Marathwada Water Grid project. The Latur earthquake (1993) created a generation of government investment in the region that has continued. Importantly, the sugar cooperative economy -- Marathwada is a major sugarcane belt -- generates intense agro-processing radiance that VIIRS captures well. The Bid district's +521% reflects the growth of the solar pump programme for irrigation.""",

        "Bundelkhand\n(Drought Belt)": """Bundelkhand's +383% sits in the middle of the cluster rankings. The intra-cluster dispersion is wide: Lalitpur (+583%) leads while Mahoba (+259%) and Hamirpur (+262%) lag. Lalitpur's outperformance reflects its position on the Bundelkhand Expressway corridor (operational 2020) and the Ken-Betwa river link project preparatory work. Jhansi (+382%) is the urban anchor of the region and benefits from the Defence Industrial Corridor designation (2018). The overall cluster performance is constrained by persistent water scarcity -- Bundelkhand receives <800mm annual rainfall and groundwater depletion continues despite PMKSY investment.""",

        "Vidarbha\n(Cotton Belt)": """Vidarbha's +303% is the lowest among the five clusters, and the district range is narrow (Buldana +388% to Yavatmal +271%), suggesting uniformly modest growth. This is consistent with the cotton belt's structural challenges: price volatility, Bt cotton input costs, and groundwater depletion. Government interventions (crop insurance under PMFBY, MSP procurement) have not translated into nighttime lights growth at the same rate as connectivity or electrification investments in other regions. The relatively higher performance of Buldana (+388%) reflects its position on the Mumbai-Nagpur Samruddhi Mahamarg expressway corridor, which runs through its southern tip. Yavatmal's lowest score (+271%) is notable -- this is the epicentre of farmer suicides in India, and the data does not show any comparable recovery signal.""",
    }

    pdf.body(f"Districts: {dists_text}\n\n{cluster_narrative.get(cname, note)}")
    if i < len(cluster_items) - 1:
        pdf.ln(2)

# ── Policy Implications ───────────────────────────────────────────────────────
pdf.add_page()
pdf.ch("5", "Policy Implications")
pdf.body("""
1. Rural India is not a monolith. The range from +3,539% (Dantewada) to +259% (Mahoba) within the same broad 'rural' category underscores that geography, conflict history, baseline electrification, and specific government programmes produce radically different outcomes. National rural policy that treats these regions identically is unlikely to be effective.

2. Connectivity infrastructure produces the clearest signal. Districts on or near expressways (Lalitpur/Bundelkhand Expressway, Buldana/Samruddhi Mahamarg) consistently outperform their regional peers. This is consistent with the broader literature on infrastructure multipliers in rural economies.

3. The peri-urban manufacturing corridor is invisible in city-level analysis. The donut analysis reveals that growth rates 2-3x higher than city cores are occurring in the rural rings of every major district. This industrial suburbanisation is not captured by either urban or rural statistics as typically reported.

4. Vidarbha needs a different policy instrument. LED connectivity and road investment -- which have lifted other rural regions -- have not helped the cotton belt as much. The problem is structural: the commodity price channel dominates. Nighttime lights track commercial activity, and if farm income is squeezed, commercial activity in village centres stagnates regardless of infrastructure quality.

5. Tribal belt figures require careful interpretation. The extreme growth rates in Dantewada, Bastar, and Gumla reflect security-driven state capacity expansion, not necessarily improvements in civilian livelihoods. Future analysis should cross-reference with forest cover loss, displacement data, and NREGA job card utilisation to separate these effects.
""")

pdf.ch("6", "Limitations")
pdf.body("""
GHS-SMOD vintage: The 2020 SMOD vintage is used for both the urban/rural masking of 2014 and 2026 data. Settlement boundaries shift over time -- areas classified as rural in 2020 may have been even more rural in 2014 or may have urbanised since. This introduces minor classification error at the urban-rural fringe.

Resolution mismatch: SMOD operates at 1km while VIIRS is at 500m. The mask is resampled to 500m for application, which may create edge artefacts near settlement boundaries.

Conflict zones: In Naxal-affected districts, nighttime lights are partly driven by security force infrastructure (forward operating bases, helicopter pads, camp lighting). This is non-civilian economic activity and inflates growth estimates in these areas.

Population data: District population CAGRs are derived from 2001-2011 Census data and projected forward 15 years. Rural-urban migration patterns have likely accelerated since 2011, particularly in Bundelkhand and Vidarbha, making population-normalised comparisons uncertain.

Missing Bolangir: Bolangir district (part of KBK) was fetched but excluded from final analysis due to boundary matching issues in GAUL 2015. The cluster mean is based on 3 rather than 4 districts.
""")

pdf.ch("7", "Data Sources")
pdf.body("""
Satellite data:
- VIIRS DNB: NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG via Google Earth Engine
- GHS-SMOD: JRC/GHSL/P2023A/GHS_SMOD/2020 via Google Earth Engine (1km)
- GHS-POP: JRC/GHSL/P2023A/GHS_POP for population baseline

Economic / administrative:
- PPP factors: World Bank API indicator PA.NUS.PPP
- District boundaries: FAO/GAUL/2015/level2 via Google Earth Engine
- Census populations: Census of India 2001, 2011

Programme references:
- Saubhagya (PM Sahaj Bijli Har Ghar Yojana): Ministry of Power
- PMGSY (Pradhan Mantri Gram Sadak Yojana): Ministry of Rural Development
- KALIA scheme: Odisha government
- KBK SAADA programme: Odisha government
- Bundelkhand Expressway: UPEIDA, Govt. of Uttar Pradesh
- Jalyukt Shivar Abhiyan: Maharashtra government

Academic references:
- Henderson, Storeygard, Weil (2012). Measuring Economic Growth from Outer Space. AER 102(2).
- Schiavina et al. (2023). GHS-SMOD R2023A. European Commission JRC.
- Patnaik et al. (2021). But clouds got in my way. xKDR Working Paper 7.
""")

print("Building PDF...")
pdf.output(str(PDF_PATH))
sz = PDF_PATH.stat().st_size // 1024
print(f"\nReport saved: {PDF_PATH}  ({sz} KB)")
