"""Design C — C2P-C1 post-extraction QA diagnostic.

Uses ONLY already-generated C2P-C point samples.
No raster redownload, no groundwater, no flood outcomes, no model fitting.
"""

from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DIAG = ROOT / "outputs" / "diagnostics" / "design_c"
P = DIAG / "c2pc_sentinel2_boa_point_samples.csv"

OUT_TXT = DIAG / "c2pc1_reflectance_qa_diagnostic.txt"
OUT_CSV = DIAG / "c2pc1_overlap_spread_quantiles.csv"
OUT_OOR = DIAG / "c2pc1_out_of_range_index_cases.csv"

BANDS = ["B02","B03","B04","B8A","B11","B12"]
INDEX_SPECS = {
    "NDVI": ("B8A_boa", "B04_boa"),
    "NDWI": ("B03_boa", "B8A_boa"),
    "MNDWI": ("B03_boa", "B11_boa"),
    "LSWI": ("B8A_boa", "B11_boa"),
}

if not P.exists():
    raise FileNotFoundError(P)

d = pd.read_csv(P)

lines = []
lines.append("DESIGN C - C2P-C1 REFLECTANCE QA DIAGNOSTIC")
lines.append("=" * 78)
lines.append("")
lines.append(f"Rows: {len(d)}")
lines.append(f"Targets: {d['target_id'].nunique()}")
lines.append("No imagery reread. No groundwater. No flood outcomes.")
lines.append("")

lines.append("REFLECTANCE DISTRIBUTIONS")
lines.append("-" * 78)
for b in BANDS:
    x = pd.to_numeric(d[f"{b}_boa"], errors="coerce")
    xf = x[np.isfinite(x)]
    lines.append(
        f"{b}: n={len(xf)} neg={(xf < 0).sum()} "
        f"zero={(xf == 0).sum()} gt1={(xf > 1).sum()} gt1.5={(xf > 1.5).sum()} "
        f"min={xf.min() if len(xf) else np.nan:.6f} "
        f"p01={xf.quantile(.01) if len(xf) else np.nan:.6f} "
        f"median={xf.median() if len(xf) else np.nan:.6f} "
        f"p99={xf.quantile(.99) if len(xf) else np.nan:.6f} "
        f"max={xf.max() if len(xf) else np.nan:.6f}"
    )

oor_rows = []
lines.append("")
lines.append("OUT-OF-RANGE NORMALIZED-DIFFERENCE DIAGNOSIS")
lines.append("-" * 78)

for idx, (ac, bc) in INDEX_SPECS.items():
    y = pd.to_numeric(d[idx], errors="coerce")
    a = pd.to_numeric(d[ac], errors="coerce")
    b = pd.to_numeric(d[bc], errors="coerce")
    den = a + b

    mask = np.isfinite(y) & ((y < -1.000001) | (y > 1.000001))
    n = int(mask.sum())
    neg_input = int((mask & ((a < 0) | (b < 0))).sum())
    opposite = int((mask & ((a * b) < 0)).sum())
    near_zero_den = int((mask & (den.abs() < 0.02)).sum())

    lines.append(
        f"{idx}: out_of_range={n}; with_negative_input={neg_input}; "
        f"opposite_sign_inputs={opposite}; |denominator|<0.02={near_zero_den}"
    )

    if n:
        tmp = d.loc[mask, [
            "target_id","support_id","lon","lat","scl_code",
            "optical_usable_for_indices", ac, bc, idx
        ]].copy()
        tmp["index_name"] = idx
        tmp["denominator"] = den[mask]
        tmp["numerator"] = (a-b)[mask]
        oor_rows.append(tmp)

if oor_rows:
    pd.concat(oor_rows, ignore_index=True).to_csv(OUT_OOR, index=False)
else:
    pd.DataFrame().to_csv(OUT_OOR, index=False)

lines.append("")
lines.append("OVERLAP REFLECTANCE SPREAD DIAGNOSTICS")
lines.append("-" * 78)
qrows = []

for b in BANDS:
    spread = pd.to_numeric(d[f"{b}_overlap_spread"], errors="coerce")
    contrib = pd.to_numeric(d[f"{b}_contributing_tiles_n"], errors="coerce")
    x = spread[(contrib > 1) & np.isfinite(spread)]

    if len(x):
        qs = {
            "band": b,
            "n_overlap": int(len(x)),
            "zero_spread_n": int((x == 0).sum()),
            "gt_1e6_n": int((x > 1e-6).sum()),
            "gt_1e4_n": int((x > 1e-4).sum()),
            "gt_5e4_n": int((x > 5e-4).sum()),
            "gt_1e3_n": int((x > 1e-3).sum()),
            "gt_5e3_n": int((x > 5e-3).sum()),
            "p50": float(x.quantile(.50)),
            "p90": float(x.quantile(.90)),
            "p95": float(x.quantile(.95)),
            "p99": float(x.quantile(.99)),
            "max": float(x.max()),
        }
        qrows.append(qs)
        lines.append(
            f"{b}: overlap_n={qs['n_overlap']} zero={qs['zero_spread_n']} "
            f"p50={qs['p50']:.6f} p90={qs['p90']:.6f} p95={qs['p95']:.6f} "
            f"p99={qs['p99']:.6f} max={qs['max']:.6f}; "
            f">1e-4={qs['gt_1e4_n']} >5e-4={qs['gt_5e4_n']} "
            f">1e-3={qs['gt_1e3_n']} >5e-3={qs['gt_5e3_n']}"
        )

pd.DataFrame(qrows).to_csv(OUT_CSV, index=False)

all6 = d["all_six_bands_present"].astype(bool)
scl = d["scl_confirmed_usable"].astype(bool)
sclamb = d["scl_overlap_ambiguous"].astype(bool)
old_amb = d["any_reflectance_overlap_ambiguous"].astype(bool)

base = all6 & scl & ~sclamb
lost = base & old_amb

lines.append("")
lines.append("OLD OVERLAP-GATE IMPACT")
lines.append("-" * 78)
lines.append(f"Rows eligible before reflectance-overlap gate: {int(base.sum())}")
lines.append(f"Rows excluded only by old >1e-6 overlap gate: {int(lost.sum())}")
lines.append(
    f"Share of otherwise eligible rows excluded: "
    f"{(lost.sum()/base.sum()) if base.sum() else np.nan:.6f}"
)

lines.append("")
lines.append("INTERPRETATION")
lines.append("-" * 78)
lines.append(
    "Normalized-difference indices are constrained to [-1,1] only when both "
    "input reflectances are non-negative. PB05 BOA reflectance can legitimately "
    "be slightly negative after additive-offset reconstruction. Therefore an "
    "out-of-range normalized-difference value is not by itself evidence of "
    "failed extraction; it should be flagged as index-invalid when caused by "
    "negative input reflectance or a very small denominator."
)
lines.append(
    "The previous 1e-6 cross-tile reflectance agreement threshold was intentionally "
    "conservative but is not yet a justified exclusion rule. Its spread distribution "
    "must be inspected before freezing an overlap rule."
)

text = "\n".join(lines) + "\n"
OUT_TXT.write_text(text, encoding="utf-8")
print(text)
print(f"Wrote: {OUT_TXT}")
print(f"Wrote: {OUT_CSV}")
print(f"Wrote: {OUT_OOR}")
