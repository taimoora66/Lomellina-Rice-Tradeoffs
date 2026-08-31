"""Clean ARPA Pavia groundwater observations and build reproducible annual measures.

This is a QA/data-preparation step only. It does not fit groundwater–flooding models.

Run from repository root:
    python scripts/04_publication_groundwater/01_groundwater_clean.py

Expected raw input (not tracked by Git):
    data/raw/arpa/groundwater_pavia.xlsx

Outputs:
    data/processed/publication_groundwater/groundwater_clean.csv
    data/processed/publication_groundwater/groundwater_station_metadata.csv
    data/processed/publication_groundwater/groundwater_annual_measures.csv
    outputs/diagnostics/publication_groundwater/groundwater_qa.csv
    outputs/diagnostics/publication_groundwater/groundwater_duplicate_audit.csv
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/arpa/groundwater_pavia.xlsx"
OUT = ROOT / "data/processed/publication_groundwater"
DIAG = ROOT / "outputs/diagnostics/publication_groundwater"
OUT.mkdir(parents=True, exist_ok=True)
DIAG.mkdir(parents=True, exist_ok=True)

STATION = "CODICE"
DATE = "Data"
DEPTH = "Soggiacenza m da Qr"
GWB = "GroundWater Body (GWB_2015)"


def _qa(rows: list[dict], metric: str, value, note: str = "") -> None:
    rows.append({"metric": metric, "value": value, "note": note})


def main() -> None:
    if not RAW.exists():
        raise FileNotFoundError(
            f"Missing {RAW}. Place the open ARPA Pavia groundwater workbook at this path."
        )

    raw = pd.read_excel(RAW)
    required = {
        STATION, "PROVINCIA", "COMUNE", DEPTH, DATE, "ANNO", "X_WGS84", "Y_WGS84",
        "QUOTA_MISURA_m s.l.m. (Qr)", "PROFONDITA' m", "FILTRI_TOP m", "FILTRI_BOT m", GWB,
    }
    missing = required.difference(raw.columns)
    if missing:
        raise ValueError(f"Groundwater workbook missing required columns: {sorted(missing)}")

    raw[DATE] = pd.to_datetime(raw[DATE], errors="coerce")
    raw[DEPTH] = pd.to_numeric(raw[DEPTH], errors="coerce")
    raw["ANNO"] = pd.to_numeric(raw["ANNO"], errors="coerce").astype("Int64")

    qa: list[dict] = []
    _qa(qa, "raw_rows", len(raw))
    _qa(qa, "raw_stations", raw[STATION].nunique())
    _qa(qa, "raw_min_date", raw[DATE].min().date().isoformat())
    _qa(qa, "raw_max_date", raw[DATE].max().date().isoformat())
    _qa(qa, "missing_depth", int(raw[DEPTH].isna().sum()))
    _qa(qa, "missing_date", int(raw[DATE].isna().sum()))
    _qa(qa, "year_date_mismatches", int((raw["ANNO"] != raw[DATE].dt.year).fillna(False).sum()))

    # Duplicate station-date audit. Exact duplicates are collapsed. Any station-date
    # with conflicting groundwater-depth values is excluded entirely rather than averaged.
    g = raw.groupby([STATION, DATE], dropna=False)
    sizes = g.size().rename("rows")
    ndepth = g[DEPTH].nunique(dropna=False).rename("n_unique_depth")
    audit = pd.concat([sizes, ndepth], axis=1).reset_index()
    audit = audit[audit["rows"] > 1].copy()
    audit["conflicting_depth"] = audit["n_unique_depth"] > 1
    audit.to_csv(DIAG / "groundwater_duplicate_audit.csv", index=False)

    conflict_keys = pd.MultiIndex.from_frame(
        audit.loc[audit["conflicting_depth"], [STATION, DATE]]
    )
    raw_keys = pd.MultiIndex.from_frame(raw[[STATION, DATE]])
    clean = raw.loc[~raw_keys.isin(conflict_keys)].copy()
    clean = clean.sort_values([STATION, DATE]).drop_duplicates([STATION, DATE], keep="first")

    clean = clean.rename(columns={
        STATION: "station",
        "PROVINCIA": "province",
        "COMUNE": "commune",
        DEPTH: "gw_depth_m",
        DATE: "date",
        "ANNO": "year_reported",
        "X_WGS84": "utm_e",
        "Y_WGS84": "utm_n",
        "QUOTA_MISURA_m s.l.m. (Qr)": "measuring_point_elev_masl",
        "PROFONDITA' m": "well_depth_m",
        "FILTRI_TOP m": "screen_top_m",
        "FILTRI_BOT m": "screen_bottom_m",
        GWB: "gwb",
    })
    clean["year"] = clean["date"].dt.year.astype(int)
    clean["month"] = clean["date"].dt.month.astype(int)
    clean["doy"] = clean["date"].dt.dayofyear.astype(int)
    clean["aquifer_group"] = np.select(
        [
            clean["gwb"].astype(str).str.startswith("GWB ISS"),
            clean["gwb"].astype(str).str.startswith("GWB ISI"),
            clean["gwb"].astype(str).str.startswith("GWB ISP"),
        ],
        ["ISS", "ISI", "ISP"],
        default="OTHER",
    )
    clean.to_csv(OUT / "groundwater_clean.csv", index=False)

    meta_cols = [
        "station", "province", "commune", "utm_e", "utm_n", "measuring_point_elev_masl",
        "well_depth_m", "screen_top_m", "screen_bottom_m", "gwb", "aquifer_group",
    ]
    # Metadata must be invariant within station after cleaning.
    conflicts = []
    for c in meta_cols[1:]:
        nun = clean.groupby("station")[c].nunique(dropna=False)
        if (nun > 1).any():
            conflicts.extend([(c, s, int(n)) for s, n in nun[nun > 1].items()])
    if conflicts:
        raise ValueError(f"Station metadata are not invariant: {conflicts[:10]}")
    station_meta = clean.sort_values("date").drop_duplicates("station")[meta_cols]
    station_meta.to_csv(OUT / "groundwater_station_metadata.csv", index=False)

    # Annual measurement table for the discovery period. We deliberately retain multiple
    # transparent candidate summaries; model choice happens later in a separate freeze step.
    iss = clean[(clean["aquifer_group"] == "ISS") & clean["year"].between(2008, 2021)].copy()
    grid = pd.MultiIndex.from_product(
        [sorted(station_meta.loc[station_meta["aquifer_group"] == "ISS", "station"]), range(2008, 2022)],
        names=["station", "year"],
    ).to_frame(index=False)

    monthly = (
        iss.groupby(["station", "year", "month"])["gw_depth_m"]
        .mean().unstack("month")
        .rename(columns={m: f"gw_m{m:02d}_mean_m" for m in range(1, 13)})
        .reset_index()
    )

    def yearly_record(g: pd.DataFrame) -> pd.Series:
        g = g.sort_values("date")
        janfeb = g[g["month"].isin([1, 2])]
        janmar = g[g["month"].isin([1, 2, 3])]
        aprmay = g[g["month"].isin([4, 5])]
        aug = g[g["month"] == 8]
        jja = g[g["month"].isin([6, 7, 8])]
        out = {
            "gw_obs_n": len(g),
            "gw_janfeb_n": len(janfeb),
            "gw_janfeb_mean_m": janfeb["gw_depth_m"].mean(),
            "gw_janmar_mean_m": janmar["gw_depth_m"].mean(),
            "gw_aprmay_mean_m": aprmay["gw_depth_m"].mean(),
            "gw_jja_mean_m": jja["gw_depth_m"].mean(),
            "gw_aug_n": len(aug),
            "gw_aug_mean_m": aug["gw_depth_m"].mean(),
        }
        if len(janfeb):
            r = janfeb.iloc[-1]
            out.update({
                "gw_pre_last_janfeb_m": r["gw_depth_m"],
                "gw_pre_last_janfeb_date": r["date"].date().isoformat(),
                "gw_pre_last_janfeb_doy": r["doy"],
            })
        else:
            out.update({"gw_pre_last_janfeb_m": np.nan, "gw_pre_last_janfeb_date": None, "gw_pre_last_janfeb_doy": np.nan})
        if len(aug):
            first = aug.iloc[0]
            last = aug.iloc[-1]
            target = pd.Timestamp(year=int(g["date"].dt.year.iloc[0]), month=8, day=23)
            nearest = aug.iloc[(aug["date"] - target).abs().argmin()]
            out.update({
                "gw_aug_first_m": first["gw_depth_m"],
                "gw_aug_first_date": first["date"].date().isoformat(),
                "gw_aug_first_doy": first["doy"],
                "gw_aug_last_m": last["gw_depth_m"],
                "gw_aug_last_date": last["date"].date().isoformat(),
                "gw_aug_nearest_aug23_m": nearest["gw_depth_m"],
                "gw_aug_nearest_aug23_date": nearest["date"].date().isoformat(),
                "gw_aug_nearest_aug23_doy": nearest["doy"],
            })
        else:
            out.update({
                "gw_aug_first_m": np.nan, "gw_aug_first_date": None, "gw_aug_first_doy": np.nan,
                "gw_aug_last_m": np.nan, "gw_aug_last_date": None,
                "gw_aug_nearest_aug23_m": np.nan, "gw_aug_nearest_aug23_date": None,
                "gw_aug_nearest_aug23_doy": np.nan,
            })
        return pd.Series(out)

    annual = iss.groupby(["station", "year"], group_keys=False).apply(yearly_record, include_groups=False).reset_index()
    annual = grid.merge(annual, on=["station", "year"], how="left").merge(monthly, on=["station", "year"], how="left")
    annual = annual.merge(station_meta, on="station", how="left")
    annual.to_csv(OUT / "groundwater_annual_measures.csv", index=False)

    _qa(qa, "duplicate_station_date_groups", len(audit))
    _qa(qa, "conflicting_station_date_groups", int(audit["conflicting_depth"].sum()))
    _qa(qa, "clean_rows", len(clean))
    _qa(qa, "clean_stations", clean["station"].nunique())
    _qa(qa, "iss_stations", station_meta.loc[station_meta["aquifer_group"] == "ISS", "station"].nunique())
    _qa(qa, "iss_clean_rows_all_years", int((clean["aquifer_group"] == "ISS").sum()))
    _qa(qa, "iss_discovery_station_year_grid", len(grid))
    _qa(qa, "iss_discovery_observed_station_years", annual["gw_obs_n"].notna().sum())
    _qa(qa, "iss_discovery_janfeb_plus_aug_station_years", int((annual["gw_janfeb_n"].fillna(0).gt(0) & annual["gw_aug_n"].fillna(0).gt(0)).sum()))
    _qa(qa, "gw_depth_min_m", clean["gw_depth_m"].min())
    _qa(qa, "gw_depth_median_m", clean["gw_depth_m"].median())
    _qa(qa, "gw_depth_max_m", clean["gw_depth_m"].max())
    _qa(qa, "negative_depth_rows", int((clean["gw_depth_m"] < 0).sum()))

    pd.DataFrame(qa).to_csv(DIAG / "groundwater_qa.csv", index=False)

    print("Groundwater QA complete")
    for r in qa:
        print(f"  {r['metric']}: {r['value']}")
    print(f"Wrote {OUT / 'groundwater_clean.csv'}")
    print(f"Wrote {OUT / 'groundwater_annual_measures.csv'}")


if __name__ == "__main__":
    main()
