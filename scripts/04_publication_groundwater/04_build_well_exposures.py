"""Build RiceFloodIT well-buffer exposure histories for all ISS wells, 2008–2021.

Primary purpose: reproduce the 2/5/10-km exposure fields used during exploration while
making their construction explicit and auditable.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
FF_IN = ROOT / "data/processed/publication_groundwater/ricefloodit_georef.csv"
GW_META = ROOT / "data/processed/publication_groundwater/groundwater_station_metadata.csv"
OUT = ROOT / "data/processed/publication_groundwater/well_ricefloodit_exposures.csv"
QA_OUT = ROOT / "outputs/diagnostics/publication_groundwater/exposure_qa.csv"
OUT.parent.mkdir(parents=True, exist_ok=True)
QA_OUT.parent.mkdir(parents=True, exist_ok=True)
RADII_KM = [2, 5, 10]


def main() -> None:
    ff = pd.read_csv(FF_IN)
    gw = pd.read_csv(GW_META)
    gw = gw[gw["aquifer_group"] == "ISS"].copy()
    pix = ff[["x", "y", "utm_e", "utm_n"]].drop_duplicates().reset_index(drop=True)
    tree = cKDTree(pix[["utm_e", "utm_n"]].to_numpy())

    # Map pixel coordinates to a stable integer key for fast yearly selection.
    pix["pixel_id"] = np.arange(len(pix))
    ff = ff.merge(pix[["x", "y", "pixel_id"]], on=["x", "y"], how="left", validate="many_to_one")
    by_year = {int(y): d.set_index("pixel_id") for y, d in ff[ff["year"].between(2008, 2021)].groupby("year")}

    rows = []
    for w in gw.itertuples(index=False):
        memberships = {
            r: tree.query_ball_point([float(w.utm_e), float(w.utm_n)], r * 1000.0)
            for r in RADII_KM
        }
        for year in range(2008, 2022):
            rec = {"station": w.station, "year": year}
            yr = by_year.get(year)
            for r in RADII_KM:
                ids = memberships[r]
                q = yr.loc[yr.index.intersection(ids)].copy() if yr is not None else pd.DataFrame()
                if len(q):
                    rec[f"ff_{r}"] = q["ff"].mean()
                    ww = pd.to_numeric(q["count"], errors="coerce").fillna(0.0)
                    rec[f"ffw_{r}"] = np.average(q["ff"], weights=ww) if ww.sum() > 0 else np.nan
                    qb = q[q["balanced_pixel"].astype(bool)]
                    rec[f"ffb_{r}"] = qb["ff"].mean() if len(qb) else np.nan
                    rec[f"n_{r}"] = len(q)
                    rec[f"nbal_{r}"] = len(qb)
                    rec[f"countsum_{r}"] = ww.sum()
                else:
                    for stem in ["ff", "ffw", "ffb"]:
                        rec[f"{stem}_{r}"] = np.nan
                    rec[f"n_{r}"] = 0
                    rec[f"nbal_{r}"] = 0
                    rec[f"countsum_{r}"] = 0
            rows.append(rec)

    out = pd.DataFrame(rows).sort_values(["station", "year"])
    for r in RADII_KM:
        out[f"ff_{r}_station_mean"] = out.groupby("station")[f"ff_{r}"].transform("mean")
        out[f"ff_{r}_anom"] = out[f"ff_{r}"] - out[f"ff_{r}_station_mean"]
    out.to_csv(OUT, index=False)

    qa = []
    for r in RADII_KM:
        qa += [
            {"metric": f"median_pixels_{r}km", "value": float(out[f"n_{r}"].replace(0, np.nan).median())},
            {"metric": f"median_balanced_pixels_{r}km", "value": float(out[f"nbal_{r}"].replace(0, np.nan).median())},
            {"metric": f"station_years_with_ff_{r}km", "value": int(out[f"ff_{r}"].notna().sum())},
        ]
    qa.extend([
        {"metric": "rows", "value": len(out)},
        {"metric": "wells", "value": out["station"].nunique()},
        {"metric": "years", "value": out["year"].nunique()},
    ])
    pd.DataFrame(qa).to_csv(QA_OUT, index=False)
    print("Well-buffer exposure construction complete")
    for r in qa:
        print(f"  {r['metric']}: {r['value']}")


if __name__ == "__main__":
    main()
