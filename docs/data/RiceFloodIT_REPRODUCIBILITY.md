
## Superseded diagnostic

The initial raw-series moving-block bootstrap implementation was
rejected because it resampled raw observations and reassigned them to
the original chronological positions, thereby destroying the fitted
long-term trend.

Its resulting near-zero bootstrap slope distribution must not be used
for scientific inference.

It was replaced by residual block bootstrap around the fitted temporal
trend in:

scripts/03_efs_analysis/02_ricefloodit_temporal_robustness.py

Authoritative output:

outputs/tables/RiceFloodIT_temporal_robustness_corrected.csv
