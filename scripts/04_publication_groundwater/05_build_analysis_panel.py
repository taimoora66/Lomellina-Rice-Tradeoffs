"""Build the analysis-ready discovery panel from independently reconstructed components.

No regression is fitted here. This script joins:
- cleaned ISS groundwater annual measures,
- RiceFloodIT 2/5/10-km exposures,
- validated ARPA monthly meteorology linked by a fixed spatial rule.

Run from repository root after scripts 01–04.
"""
from __future__ import annotations

from pathlib import Path
import calendar
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
GW = ROOT / "data/processed/publication_groundwater/groundwater_annual_measures.csv"
FF = ROOT / "data/processed/publication_groundwater/well_ricefloodit_exposures.csv"
WX = ROOT / "data/processed/publication_groundwater/weather_sensor_monthly.csv"
WX_META = ROOT / "data/raw/arpa/weather_station_master.csv"
OUT = ROOT / "data/processed/publication_groundwater/discovery_panel_2008_2021.csv"
QA_OUT = ROOT / "outputs/diagnostics/publication_groundwater/panel_qa.csv"
OUT.parent.mkdir(parents=True, exist_ok=True)
QA_OUT.parent.mkdir(parents=True, exist_ok=True)

NEAREST_N = 3
MAX_KM = 50.0
MIN_STATIONS = 2


def link_months(panel: pd.DataFrame, monthly: pd.DataFrame, meta: pd.DataFrame, variable: str, type_name: str, prefix: str) -> pd.DataFrame:
    wc = meta[meta["Tipologia"].eq(type_name)][["IdSensore", "UTM_Est", "UTM_Nord", "NomeStazione"]].copy()
    wc["IdSensore"] = pd.to_numeric(wc["IdSensore"], errors="coerce").astype("Int64")
    wc = wc.dropna(subset=["IdSensore", "UTM_Est", "UTM_Nord"]).drop_duplicates("IdSensore")
    mm = monthly[monthly["variable"].eq(variable)].copy()
    wc = wc[wc["IdSensore"].isin(mm["idsensore"].dropna().unique())]
    lookup = {(int(y), int(m)): g.set_index("idsensore")["value"] for (y, m), g in mm.groupby(["year", "month"])}

    rows = []
    for r in panel[["station", "year", "utm_e", "utm_n"]].itertuples(index=False):
        rec = {"station": r.station, "year": int(r.year)}
        for month in range(1, 9):
            a = lookup.get((int(r.year), month), pd.Series(dtype=float)).dropna()
            cand = wc[wc["IdSensore"].isin(a.index)].copy()
            if len(cand):
                cand["dist_km"] = np.hypot(cand["UTM_Est"] - r.utm_e, cand["UTM_Nord"] - r.utm_n) / 1000.0
                cand = cand[cand["dist_km"] <= MAX_KM].sort_values("dist_km").head(NEAREST_N)
            if len(cand) >= MIN_STATIONS:
                vals = a.reindex(cand["IdSensore"]).astype(float).to_numpy()
                dd = cand["dist_km"].astype(float).to_numpy()
                weights = 1.0 / np.maximum(dd, 0.5) ** 2
                weights /= weights.sum()
                rec[f"{prefix}{month}"] = float(np.sum(vals * weights))
                rec[f"{prefix}{month}_n"] = len(cand)
                rec[f"{prefix}{month}_dmax_km"] = float(dd.max())
            else:
                rec[f"{prefix}{month}"] = np.nan
                rec[f"{prefix}{month}_n"] = len(cand)
                rec[f"{prefix}{month}_dmax_km"] = np.nan
        rows.append(rec)
    return pd.DataFrame(rows)


def main() -> None:
    gw = pd.read_csv(GW)
    ff = pd.read_csv(FF)
    wx = pd.read_csv(WX)
    meta = pd.read_csv(WX_META)

    p = gw.merge(ff, on=["station", "year"], how="left", validate="one_to_one", suffixes=("", "_ff"))
    p = p[p["aquifer_group"] == "ISS"].copy()

    precip = link_months(p, wx, meta, "precip", "Precipitazione", "P")
    temp = link_months(p, wx, meta, "temp", "Temperatura", "T")
    p = p.merge(precip, on=["station", "year"], how="left", validate="one_to_one")
    p = p.merge(temp, on=["station", "year"], how="left", validate="one_to_one")

    # Cumulative meteorology from April to target month, matching the exploratory linkage rule.
    for target in [6, 7, 8]:
        months = list(range(4, target + 1))
        p[f"P_A{target}"] = p[[f"P{m}" for m in months]].sum(axis=1, min_count=len(months))
        days = np.array([calendar.monthrange(int(y), m)[1] for y in [2001] for m in months], dtype=float)
        vals = p[[f"T{m}" for m in months]].to_numpy(dtype=float)
        p[f"T_A{target}"] = np.where(np.isfinite(vals).all(axis=1), (vals * days).sum(axis=1) / days.sum(), np.nan)

    # Explicitly named candidate outcomes/baselines. No model selection occurs here.
    p["gw_aug_depth_m"] = p["gw_aug_mean_m"]
    p["gw_pre_depth_m"] = p["gw_pre_last_janfeb_m"]
    p["gw_spring_to_aug_change_m"] = p["gw_aug_mean_m"] - p["gw_aprmay_mean_m"]

    # Recompute anomalies after the merge to protect against accidental stale intermediates.
    for r in [2, 5, 10]:
        p[f"ff_{r}_station_mean_check"] = p.groupby("station")[f"ff_{r}"].transform("mean")
        p[f"ff_{r}_anom_check"] = p[f"ff_{r}"] - p[f"ff_{r}_station_mean_check"]

    p["has_pre_gw"] = p["gw_pre_depth_m"].notna()
    p["has_aug_gw"] = p["gw_aug_depth_m"].notna()
    p["has_ff10"] = p["ff_10"].notna()
    p["has_weather_A8"] = p[["P_A8", "T_A8"]].notna().all(axis=1)
    p["candidate_primary_complete"] = p[["gw_pre_depth_m", "gw_aug_depth_m", "ff_10", "P_A8", "T_A8"]].notna().all(axis=1)
    p = p.sort_values(["station", "year"])
    p.to_csv(OUT, index=False)

    qa = [
        {"metric": "rows", "value": len(p)},
        {"metric": "wells", "value": p["station"].nunique()},
        {"metric": "years", "value": p["year"].nunique()},
        {"metric": "pre_plus_aug_rows", "value": int((p["has_pre_gw"] & p["has_aug_gw"]).sum())},
        {"metric": "candidate_primary_complete_rows", "value": int(p["candidate_primary_complete"].sum())},
        {"metric": "candidate_primary_complete_wells", "value": int(p.loc[p["candidate_primary_complete"], "station"].nunique())},
    ]
    for y, n in p.loc[p["candidate_primary_complete"]].groupby("year").size().items():
        qa.append({"metric": f"candidate_primary_complete_year_{int(y)}", "value": int(n)})
    pd.DataFrame(qa).to_csv(QA_OUT, index=False)
    print("Discovery panel construction complete")
    for r in qa:
        print(f"  {r['metric']}: {r['value']}")
    print("No regression was fitted. Next stage is model/inference freeze and rerun.")


if __name__ == "__main__":
    main()
