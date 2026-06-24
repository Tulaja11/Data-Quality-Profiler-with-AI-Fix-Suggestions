"""
profiler.py
Core data quality analysis — runs entirely with pandas, no API needed.
Detects: nulls, duplicates, type issues, outliers, formatting inconsistencies,
         constant columns, column name issues.
"""

import pandas as pd
import numpy as np
import re


def profile_dataframe(df: pd.DataFrame) -> dict:
    issues = []
    column_profiles = {}

    # ── 1. Duplicate rows ─────────────────────────────────────────────────────
    dup_count = df.duplicated().sum()
    if dup_count > 0:
        issues.append({
            "severity": "critical",
            "title": f"Duplicate Rows — {dup_count} exact duplicates found",
            "detail": f"{dup_count} rows are exact copies of another row. These skew aggregations and counts.",
            "type": "duplicates",
            "affected": "all",
            "count": int(dup_count),
        })

    # Also check near-duplicates excluding likely ID columns
    id_cols = [c for c in df.columns if any(k in c.lower() for k in ["id", "key", "uuid", "code", "no", "num", "number"])]
    non_id_cols = [c for c in df.columns if c not in id_cols]
    if non_id_cols and len(non_id_cols) < len(df.columns):
        near_dup_count = df[non_id_cols].duplicated().sum()
        if near_dup_count > 0:
            issues.append({
                "severity": "warning",
                "title": f"Near-Duplicate Rows — {near_dup_count} rows share identical data (different ID only)",
                "detail": f"{near_dup_count} row(s) have matching values in all non-ID columns. Possible duplicate records with reassigned IDs. Columns checked: {non_id_cols}",
                "type": "near_duplicates",
                "affected": "all",
                "count": int(near_dup_count),
            })

    # ── 2. Column name issues ─────────────────────────────────────────────────
    bad_col_names = []
    flagged_cols = set()
    for col in df.columns:
        if re.search(r'\s', col):
            bad_col_names.append(f"'{col}' (has spaces)")
            flagged_cols.add(col)
        if re.search(r'[^a-zA-Z0-9_\s]', col) and col not in flagged_cols:
            bad_col_names.append(f"'{col}' (special chars)")
            flagged_cols.add(col)

    if bad_col_names:
        issues.append({
            "severity": "warning",
            "title": f"Column Name Issues — {len(bad_col_names)} column(s) have problematic names",
            "detail": "Columns with spaces or special characters cause errors in pandas dot-notation. Affected: " + ", ".join(bad_col_names[:5]),
            "type": "column_names",
            "affected": bad_col_names,
        })

    # ── Per-column analysis ───────────────────────────────────────────────────
    total_missing = 0

    for col in df.columns:
        col_issues = []
        series = df[col]
        dtype = str(series.dtype)

        # Null / missing
        null_count = series.isna().sum()
        # Also catch string "NULL", "NA", "NaN", ""
        if series.dtype == object:
            str_nulls = series.astype(str).str.strip().str.upper().isin(["NULL", "NA", "NAN", "NONE", ""]).sum()
            null_count = max(null_count, int(str_nulls))

        null_pct = (null_count / len(series)) * 100 if len(series) > 0 else 0
        total_missing += int(null_count)

        if null_pct == 100:
            col_issues.append(f"Entirely empty column — consider dropping it")
            issues.append({
                "severity": "critical",
                "title": f"'{col}' — Column is 100% empty",
                "detail": "Every value is null/missing. This column has no useful data.",
                "type": "all_null",
                "affected": col,
                "count": int(null_count),
            })
        elif null_pct > 50:
            col_issues.append(f"{null_pct:.1f}% missing — high null rate")
            issues.append({
                "severity": "critical",
                "title": f"'{col}' — {null_pct:.1f}% values missing",
                "detail": f"{null_count} out of {len(series)} values are null. Consider dropping or imputing this column.",
                "type": "high_nulls",
                "affected": col,
                "count": int(null_count),
            })
        elif null_pct > 0:
            col_issues.append(f"{null_pct:.1f}% missing ({null_count} values)")
            issues.append({
                "severity": "warning",
                "title": f"'{col}' — {null_count} missing values ({null_pct:.1f}%)",
                "detail": f"Missing values detected. Fill with mean/median (numeric) or mode/placeholder (categorical).",
                "type": "nulls",
                "affected": col,
                "count": int(null_count),
            })

        # Unique count
        unique_count = series.nunique()

        # Constant column
        if unique_count <= 1 and len(series) > 1:
            col_issues.append("Constant column — same value everywhere")
            issues.append({
                "severity": "warning",
                "title": f"'{col}' — Constant column (only 1 unique value)",
                "detail": "This column has the same value in every row and adds no information for analysis.",
                "type": "constant",
                "affected": col,
            })

        # Numeric column checks
        stats = {}
        if dtype in ["int64", "float64"] or pd.api.types.is_numeric_dtype(series):
            clean = series.dropna()
            if len(clean) > 4:
                q1, q3 = clean.quantile(0.25), clean.quantile(0.75)
                iqr = q3 - q1
                lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                outliers = clean[(clean < lower) | (clean > upper)]
                if len(outliers) > 0:
                    col_issues.append(f"{len(outliers)} outlier(s) detected (IQR method)")
                    issues.append({
                        "severity": "warning",
                        "title": f"'{col}' — {len(outliers)} outlier(s) detected",
                        "detail": f"Values outside [{lower:.2f}, {upper:.2f}] (IQR method). Max={clean.max():.2f}, Min={clean.min():.2f}. Review if these are data entry errors.",
                        "type": "outliers",
                        "affected": col,
                        "count": int(len(outliers)),
                    })

                stats = {
                    "min": round(float(clean.min()), 4),
                    "max": round(float(clean.max()), 4),
                    "mean": round(float(clean.mean()), 4),
                    "median": round(float(clean.median()), 4),
                    "std": round(float(clean.std()), 4),
                }

        # String column checks
        if series.dtype == object:
            non_null = series.dropna().astype(str)
            if len(non_null) > 0:

                # Mixed case inconsistency (e.g., "Sales" and "sales" and "SALES")
                lower_vals = non_null.str.lower().unique()
                actual_vals = non_null.unique()
                if len(actual_vals) > len(lower_vals):
                    col_issues.append("Inconsistent casing (e.g. 'Sales' vs 'sales')")
                    issues.append({
                        "severity": "warning",
                        "title": f"'{col}' — Inconsistent text casing",
                        "detail": f"Same values appear in different cases (e.g. 'Engineering' and 'engineering'). Standardise with .str.lower() or .str.title().",
                        "type": "casing",
                        "affected": col,
                    })

                # Leading/trailing whitespace
                stripped = non_null.str.strip()
                if (stripped != non_null).any():
                    col_issues.append("Leading/trailing whitespace found")
                    issues.append({
                        "severity": "info",
                        "title": f"'{col}' — Whitespace in values",
                        "detail": "Some values have leading or trailing spaces which cause mismatches in filters and joins. Fix with .str.strip().",
                        "type": "whitespace",
                        "affected": col,
                    })

                # Try to detect numeric stored as string
                numeric_tryparse = pd.to_numeric(non_null, errors="coerce")
                numeric_ratio = numeric_tryparse.notna().sum() / len(non_null)
                if numeric_ratio > 0.8 and dtype == "object":
                    col_issues.append("Numeric data stored as text — should be int/float")
                    issues.append({
                        "severity": "warning",
                        "title": f"'{col}' — Numeric data stored as text",
                        "detail": f"{numeric_ratio*100:.0f}% of values look numeric but column is stored as object/string. Convert with pd.to_numeric().",
                        "type": "wrong_dtype",
                        "affected": col,
                    })

                # Date detection
                if any(kw in col.lower() for kw in ["date", "time", "dt", "created", "updated", "at"]):
                    parsed = pd.to_datetime(non_null, errors="coerce", infer_datetime_format=True)
                    fail_ratio = parsed.isna().sum() / len(non_null)
                    if fail_ratio > 0.1 and dtype == "object":
                        col_issues.append("Inconsistent date formats")
                        issues.append({
                            "severity": "warning",
                            "title": f"'{col}' — Inconsistent date formats",
                            "detail": f"{fail_ratio*100:.0f}% of date values could not be parsed — mixed formats likely (e.g. 'MM-DD-YYYY' vs 'YYYY-MM-DD'). Standardise with pd.to_datetime().",
                            "type": "date_format",
                            "affected": col,
                        })

        # Sample values
        sample_vals = series.dropna().head(5).tolist()

        column_profiles[col] = {
            "dtype": dtype,
            "null_count": int(null_count),
            "null_pct": round(null_pct, 2),
            "unique_count": int(unique_count),
            "sample_values": [str(v) for v in sample_vals],
            "stats": stats,
            "issues": col_issues,
        }

    # ── Quality Score ─────────────────────────────────────────────────────────
    # The old approach subtracted a flat amount per issue with no normalization
    # for dataset width - so a 9-column CSV with a few completely normal minor
    # issues (one stray null, one outlier) could rack up 70+ points of flat
    # deductions and bottom out near 0, regardless of how clean the data
    # actually was. Wider datasets were structurally punished no matter what.
    #
    # Fixed approach: measure each quality dimension as a RATE (how much of
    # the data is actually affected), not a raw issue count. This is the same
    # idea real data-quality frameworks use - completeness, validity,
    # uniqueness, consistency - each naturally bounded 0-100, then combined
    # as a weighted average so the final score can't blow past either end.
    n_rows = len(df)
    n_cols = len(df.columns) if len(df.columns) > 0 else 1

    # Completeness: average non-null rate across columns (not "how many
    # columns have any null at all", which punishes wide tables unfairly)
    null_rates = [column_profiles[c]["null_pct"] / 100 for c in column_profiles]
    completeness = 100 * (1 - (sum(null_rates) / len(null_rates) if null_rates else 0))

    # Uniqueness: based on the actual exact-duplicate row RATE, not a flat
    # penalty regardless of dataset size
    dup_rate = dup_count / n_rows if n_rows else 0
    uniqueness = 100 * (1 - min(1.0, dup_rate))

    # Validity: share of columns affected by a "data is wrong" issue
    # (outliers, wrong dtype, bad dates, all/high nulls) - not stacked counts
    validity_types = {"outliers", "wrong_dtype", "date_format", "all_null", "high_nulls"}
    invalid_cols = {i["affected"] for i in issues if i["type"] in validity_types and isinstance(i["affected"], str)}
    validity = 100 * (1 - len(invalid_cols) / n_cols)

    # Consistency: share of columns affected by a "data is messy but not
    # wrong" issue (inconsistent casing, whitespace, constant columns)
    consistency_types = {"casing", "whitespace", "constant"}
    inconsistent_cols = {i["affected"] for i in issues if i["type"] in consistency_types and isinstance(i["affected"], str)}
    consistency = 100 * (1 - len(inconsistent_cols) / n_cols)

    dimension_scores = {
        "completeness": round(float(completeness), 1),
        "validity": round(float(validity), 1),
        "uniqueness": round(float(uniqueness), 1),
        "consistency": round(float(consistency), 1),
    }

    weighted_score = (
        completeness * 0.35
        + validity * 0.30
        + uniqueness * 0.20
        + consistency * 0.15
    )

    # Small, capped flat penalty for dataset-level structural issues that
    # don't map cleanly onto a single column (bad column names, near-dupes).
    # Capped at 5 total so they nudge the score, not dominate it.
    structural_issue_types = {"column_names", "near_duplicates"}
    structural_penalty = min(5, sum(3 for i in issues if i["type"] in structural_issue_types))

    quality_score = max(0, min(100, round(weighted_score - structural_penalty)))

    return {
        "issues": issues,
        "column_profiles": column_profiles,
        "total_missing": int(total_missing),
        "duplicate_rows": int(dup_count),
        "quality_score": int(quality_score),
        "dimension_scores": dimension_scores,
        "row_count": len(df),
        "col_count": len(df.columns),
    }

