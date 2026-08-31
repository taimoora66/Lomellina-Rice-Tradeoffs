"""Clean open ARPA Lombardia meteorological observations to validated sensor-month values.

Prerequisite:
    python scripts/04_publication_groundwater/00_download_arpa_meteo.py

Run:
    python scripts/04_publication_groundwater/03_weather_clean_aggregate.py
"""
from __future__ import annotations

from pathlib import Path
import calendar
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data/raw/arpa_meteo"
OUT = ROOT / "data/processed/publication_groundwater/weather_sensor_monthly.csv"
QA_OUT = ROOT / "outputs/diagnostics/publication_groundwater/weather_qa.csv"
OUT.parent.mkdir(parents=True, exist_ok=True)
QA_OUT.parent.mkdir(parents=True, exist_ok=True)

FILES = {
    "precip": ["precip_2008_2010.csv", "precip_2011_2020.csv", "precip_2021.csv"],
    "temp": ["temp_2008_2010.csv", "temp_2011_2020.csv", "temp_2021.csv"],
}
COMMON_CADENCES = np.array([8, 12, 24, 48, 72, 96, 144, 288])


def read_daily(paths: list[Path], variable: str) -> tuple[pd.DataFrame, list[dict]]:
    all_parts = []
    qa = []
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Missing {path}; run 00_download_arpa_meteo.py first.")
        parts = []
        raw_rows = 0
        for d in pd.read_csv(path, usecols=["idsensore", "data", "valore", "stato"], chunksize=400_000):
            raw_rows += len(d)
            d["data"] = pd.to_datetime(d["data"], errors="coerce")
            d = d[d["data"].dt.year.between(2008, 2021)]
            d["idsensore"] = pd.to_numeric(d["idsensore"], errors="coerce").astype("Int64")
            d["valore"] = pd.to_numeric(d["valore"], errors="coerce")
            if variable == "temp":
                d.loc[d["valore"].eq(-999), "valore"] = np.nan
            d.loc[d["stato"].ne("VA"), "valore"] = np.nan
            d["date"] = d["data"].dt.floor("D")
            z = d.groupby(["idsensore", "date"], as_index=False).agg(
                n=("valore", "count"), s=("valore", "sum"), mean=("valore", "mean")
            )
            parts.append(z)
        z = pd.concat(parts, ignore_index=True)
        if variable == "precip":
            z = z.groupby(["idsensore", "date"], as_index=False).agg(n=("n", "sum"), s=("s", "sum"))
        else:
            z["weighted_sum"] = z["mean"] * z["n"]
            z = z.groupby(["idsensore", "date"], as_index=False).agg(n=("n", "sum"), weighted_sum=("weighted_sum", "sum"))
            z["mean"] = z["weighted_sum"] / z["n"].replace(0, np.nan)
        all_parts.append(z)
        qa.append({"metric": f"raw_rows_{path.stem}", "value": raw_rows})

    z = pd.concat(all_parts, ignore_index=True)
    if variable == "precip":
        z = z.groupby(["idsensore", "date"], as_index=False).agg(n=("n", "sum"), s=("s", "sum"))
    else:
        z["weighted_sum"] = z["mean"] * z["n"]
        z = z.groupby(["idsensore", "date"], as_index=False).agg(n=("n", "sum"), weighted_sum=("weighted_sum", "sum"))
        z["mean"] = z["weighted_sum"] / z["n"].replace(0, np.nan)

    z["year"] = z["date"].dt.year
    z["month"] = z["date"].dt.month
    cadence = z.groupby(["idsensore", "year"])["n"].quantile(0.90).reset_index(name="q90")
    cadence["expected"] = cadence["q90"].apply(
        lambda q: COMMON_CADENCES[np.argmin(np.abs(COMMON_CADENCES - q))] if pd.notna(q) else np.nan
    )
    z = z.merge(cadence[["idsensore", "year", "expected"]], on=["idsensore", "year"], how="left")
    z["valid_day"] = z["n"] >= 0.8 * z["expected"]
    z["value"] = z["s"] if variable == "precip" else z["mean"]
    z.loc[~z["valid_day"], "value"] = np.nan
    return z, qa


def monthly(daily: pd.DataFrame, variable: str) -> pd.DataFrame:
    fn = "sum" if variable == "precip" else "mean"
    m = daily.groupby(["idsensore", "year", "month"], as_index=False).agg(
        value=("value", fn), valid_days=("value", "count")
    )
    m["days_in_month"] = [calendar.monthrange(int(y), int(mo))[1] for y, mo in zip(m["year"], m["month"])]
    m["coverage"] = m["valid_days"] / m["days_in_month"]
    m.loc[m["coverage"] < 0.8, "value"] = np.nan
    m["variable"] = variable
    return m[["variable", "idsensore", "year", "month", "value", "valid_days", "days_in_month", "coverage"]]


def main() -> None:
    qa = []
    monthly_parts = []
    for variable, names in FILES.items():
        daily, q = read_daily([RAW_DIR / n for n in names], variable)
        qa.extend(q)
        m = monthly(daily, variable)
        monthly_parts.append(m)
        qa.extend([
            {"metric": f"sensor_month_rows_{variable}", "value": len(m)},
            {"metric": f"valid_sensor_months_{variable}", "value": int(m["value"].notna().sum())},
            {"metric": f"unique_sensors_{variable}", "value": m["idsensore"].nunique()},
        ])
    out = pd.concat(monthly_parts, ignore_index=True).sort_values(["variable", "idsensore", "year", "month"])
    out.to_csv(OUT, index=False)
    pd.DataFrame(qa).to_csv(QA_OUT, index=False)
    print("Weather aggregation complete")
    for r in qa:
        print(f"  {r['metric']}: {r['value']}")


if __name__ == "__main__":
    main()
