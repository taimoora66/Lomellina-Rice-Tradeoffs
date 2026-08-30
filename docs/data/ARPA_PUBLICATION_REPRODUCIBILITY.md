# ARPA data reproducibility — groundwater publication track

**Status:** recovery audit; not yet final protocol freeze.
**Last updated:** 2026-08-31.

## Scope

This record covers the open ARPA Lombardia groundwater and meteorological inputs used in the exploratory rice-hydroperiod × groundwater analyses conducted on 2026-08-30/31.

## Groundwater

Recovery copy SHA-256: `75325a95e17c3ae689115521379e8ea8843bcb713b6e7b689922d4633809458e`.

Observed properties checked during recovery:

- 5,946 raw observations;
- 68 stations;
- earliest record 2008-01-07 and latest record 2023-12-28;
- no records before 2008 in this workbook;
- 37 stations classified as superficial (`GWB ISS ...`);
- 249 duplicated station-date rows in the raw workbook, overwhelmingly exact duplicates;
- one conflicting station-date (`PO018048NRP001`, 2018-02-28: 2.90 m versus 3.32 m) is excluded rather than averaged;
- groundwater outcome is `Soggiacenza m da Qr`: larger values mean deeper groundwater.

**Unresolved provenance gate:** record the exact ARPA catalogue/download URL and dataset revision metadata. The checksum identifies the recovery copy but is not a substitute for source provenance.

## Meteorology

All meteorological measurements are open Socrata records. Dataset IDs and recovery-copy checksums are in `docs/data/ARPA_OPEN_DATA_MANIFEST.csv`.

Cleaning rules established during exploration:

- retain `VA` observations;
- temperature `-999` is a missing-value sentinel and must become NA;
- aggregate high-frequency measurements to daily values only after checking expected sensor frequency;
- require at least 80% valid observations within a day and at least 80% valid days in an analysis window;
- precipitation is summed; temperature uses daily means then time-window means;
- local groundwater-well weather exposure was provisionally assigned from the three nearest valid stations within 50 km, inverse-distance-squared weighted, requiring at least two stations.

The final analysis must test the sensitivity of this weather assignment *without selecting the rule on the groundwater result*.

## Raw-data policy

Large raw ARPA files are not versioned in Git. Git stores:

1. immutable source identifiers and query logic;
2. checksums for the recovery copies;
3. cleaning scripts;
4. compact diagnostics and analytical outputs.

`00_download_arpa_meteo.py` reconstructs the six meteorological files needed for 2008–2021 directly from ARPA's public SODA2 endpoints and paginates requests to avoid silent row limits.
