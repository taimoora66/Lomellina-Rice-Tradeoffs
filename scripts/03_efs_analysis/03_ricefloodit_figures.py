from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


ROOT = Path(".")
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"

FIGURES.mkdir(parents=True, exist_ok=True)

annual = pd.read_csv(
    TABLES / "RiceFloodIT_annual_FF_summary.csv"
)

ws = pd.read_csv(
    TABLES / "RiceFloodIT_district_WS_2000_2021.csv"
)

sub = pd.read_csv(
    TABLES / "RiceFloodIT_subdistrict_FF_annual.csv"
)


# ============================================================
# FIGURE 1
# ============================================================

fig, ax = plt.subplots(figsize=(8.2, 5.0))

ax.plot(
    annual["year"],
    annual["mean_ff_balanced"],
    marker="o",
    markersize=4.5,
    linewidth=2.0,
    label="Balanced panel — primary (n = 2,419)"
)

ax.plot(
    annual["year"],
    annual["mean_ff_full"],
    marker="s",
    markersize=4.0,
    linewidth=1.5,
    linestyle="--",
    label="Changing-support sample — sensitivity"
)

ax.set_xlabel("Year")
ax.set_ylabel("Mean sowing-period flooding fraction (FFavg)")
ax.set_title("Annual rice-field flooding fraction, 2000–2021")

ax.set_ylim(0, 0.45)
ax.set_xlim(1999.5, 2021.5)
ax.set_xticks(range(2000, 2022, 2))

ax.grid(axis="y", alpha=0.25, linewidth=0.7)
ax.legend(frameon=False, loc="upper right")

fig.tight_layout()

fig.savefig(
    FIGURES / "Fig01_RiceFloodIT_balanced_vs_full.png",
    dpi=400,
    bbox_inches="tight"
)

fig.savefig(
    FIGURES / "Fig01_RiceFloodIT_balanced_vs_full.pdf",
    bbox_inches="tight"
)

plt.close(fig)


# ============================================================
# FIGURE 2
# ============================================================

ws = ws.sort_values("year")

fig, ax = plt.subplots(figsize=(8.2, 5.0))

ax.plot(
    ws["year"],
    ws["ws"],
    marker="o",
    markersize=4.5,
    linewidth=2.0
)

ax.set_xlabel("Year")
ax.set_ylabel("Estimated water-seeded rice proportion (WS)")
ax.set_title(
    "Remote-sensing estimate of water-seeded rice proportion, 2000–2021"
)

ax.set_ylim(0, 1)
ax.set_xlim(1999.5, 2021.5)
ax.set_xticks(range(2000, 2022, 2))

ax.grid(axis="y", alpha=0.25, linewidth=0.7)

fig.tight_layout()

fig.savefig(
    FIGURES / "Fig02_RiceFloodIT_water_seeded_proportion.png",
    dpi=400,
    bbox_inches="tight"
)

fig.savefig(
    FIGURES / "Fig02_RiceFloodIT_water_seeded_proportion.pdf",
    bbox_inches="tight"
)

plt.close(fig)


# ============================================================
# FIGURE 3
# Balanced-panel subdistrict trajectories
# ============================================================

fig, ax = plt.subplots(figsize=(9.2, 5.7))

for district in sorted(sub["subdistrict"].unique()):

    d = (
        sub.loc[sub["subdistrict"] == district]
        .sort_values("year")
    )

    ax.plot(
        d["year"],
        d["mean_ff"],
        marker="o",
        markersize=2.8,
        linewidth=1.35,
        label=f"Subdistrict {district}"
    )

ax.set_xlabel("Year")
ax.set_ylabel("Mean sowing-period flooding fraction (FFavg)")
ax.set_title(
    "Spatial heterogeneity in balanced-panel flooding trajectories"
)

ax.set_ylim(0, 0.75)
ax.set_xlim(1999.5, 2021.5)
ax.set_xticks(range(2000, 2022, 2))

ax.grid(
    axis="y",
    alpha=0.25,
    linewidth=0.7
)

ax.legend(
    frameon=False,
    title="Subdistrict",
    loc="center left",
    bbox_to_anchor=(1.01, 0.5)
)

fig.tight_layout()

fig.savefig(
    FIGURES / "Fig03_RiceFloodIT_subdistrict_FF.png",
    dpi=400,
    bbox_inches="tight"
)

fig.savefig(
    FIGURES / "Fig03_RiceFloodIT_subdistrict_FF.pdf",
    bbox_inches="tight"
)

plt.close(fig)


print()
print("Figures regenerated successfully.")
