from __future__ import annotations

from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

INPUT = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "cmr_mod09a1_2021_h18v04_granules.csv"
)

OUTPUT = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "modis_access_audit_2021.csv"
)

START_DATE = pd.Timestamp("2021-03-01", tz="UTC")
END_DATE = pd.Timestamp("2021-06-30 23:59:59", tz="UTC")


def classify_link(url: str) -> str:
    u = url.lower()

    if u.startswith("s3://"):
        return "s3"

    if u.startswith("https://"):
        return "https"

    if u.startswith("http://"):
        return "http"

    return "other"


def main() -> None:
    df = pd.read_csv(INPUT)

    df["start_time"] = pd.to_datetime(
        df["start_time"],
        utc=True,
        errors="raise",
    )

    # This is the candidate RiceFloodIT temporal rule:
    # composite START date must fall within March-June.
    selected = df.loc[
        df["start_time"].between(
            START_DATE,
            END_DATE,
            inclusive="both",
        )
    ].copy()

    if len(selected) != 15:
        raise AssertionError(
            "Expected exactly 15 March-June start-date "
            f"granules; found {len(selected)}."
        )

    rows = []

    scheme_counts = Counter()
    host_counts = Counter()

    for _, record in selected.iterrows():
        links_text = record.get("download_links", "")

        if pd.isna(links_text):
            links = []
        else:
            links = [
                x.strip()
                for x in str(links_text).split(" | ")
                if x.strip()
            ]

        for link in links:
            parsed = urlparse(link)

            scheme = classify_link(link)
            host = parsed.netloc

            scheme_counts[scheme] += 1
            host_counts[host] += 1

            rows.append(
                {
                    "producer_granule_id":
                        record["producer_granule_id"],
                    "start_time":
                        record["start_time"].isoformat(),
                    "tile":
                        record["tile"],
                    "scheme":
                        scheme,
                    "host":
                        host,
                    "url":
                        link,
                }
            )

    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT, index=False)

    print("MOD09A1 access-link audit")
    print(f"  input CMR granules: {len(df)}")
    print(
        "  selected March-June start-date "
        f"granules: {len(selected)}"
    )

    print("")
    print("  selected acquisition dates:")

    for value in selected["start_time"]:
        print(f"    {value.date()}")

    print("")
    print("  link schemes:")

    if scheme_counts:
        for key, value in sorted(scheme_counts.items()):
            print(f"    {key}: {value}")
    else:
        print("    NONE")

    print("")
    print("  link hosts:")

    if host_counts:
        for key, value in sorted(host_counts.items()):
            print(f"    {key}: {value}")
    else:
        print("    NONE")

    print("")
    print(f"  wrote: {OUTPUT}")

    print("")
    print(
        "No remote file content was downloaded."
    )


if __name__ == "__main__":
    main()