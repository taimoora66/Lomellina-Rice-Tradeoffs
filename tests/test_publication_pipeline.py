from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / "outputs" / "diagnostics" / "publication_groundwater"


def qa_value(filename: str, metric: str) -> float:
    df = pd.read_csv(QA / filename)
    row = df.loc[df["metric"] == metric, "value"]

    if len(row) != 1:
        raise AssertionError(
            f"Expected exactly one value for {metric!r} in {filename}, "
            f"found {len(row)}"
        )

    return float(row.iloc[0])


def test_groundwater_reconstruction():
    assert qa_value("groundwater_qa.csv", "raw_rows") == 5946
    assert qa_value("groundwater_qa.csv", "raw_stations") == 68
    assert qa_value(
        "groundwater_qa.csv",
        "duplicate_station_date_groups",
    ) == 249
    assert qa_value(
        "groundwater_qa.csv",
        "conflicting_station_date_groups",
    ) == 1
    assert qa_value("groundwater_qa.csv", "clean_rows") == 5696
    assert qa_value("groundwater_qa.csv", "iss_stations") == 37
    assert qa_value(
        "groundwater_qa.csv",
        "iss_clean_rows_all_years",
    ) == 3084


def test_ricefloodit_reconstruction():
    assert qa_value("ricefloodit_georef_qa.csv", "rows") == 80926
    assert qa_value("ricefloodit_georef_qa.csv", "years") == 22
    assert qa_value(
        "ricefloodit_georef_qa.csv",
        "unique_pixels",
    ) == 4331
    assert qa_value(
        "ricefloodit_georef_qa.csv",
        "balanced_pixels",
    ) == 2419


def test_exposure_panel():
    assert qa_value("exposure_qa.csv", "rows") == 518
    assert qa_value("exposure_qa.csv", "wells") == 37
    assert qa_value("exposure_qa.csv", "years") == 14
    assert qa_value(
        "exposure_qa.csv",
        "station_years_with_ff_10km",
    ) == 479


def test_discovery_panel():
    assert qa_value("panel_qa.csv", "rows") == 518
    assert qa_value("panel_qa.csv", "wells") == 37
    assert qa_value("panel_qa.csv", "years") == 14
    assert qa_value("panel_qa.csv", "pre_plus_aug_rows") == 221
    assert qa_value(
        "panel_qa.csv",
        "candidate_primary_complete_rows",
    ) == 194
    assert qa_value(
        "panel_qa.csv",
        "candidate_primary_complete_wells",
    ) == 32