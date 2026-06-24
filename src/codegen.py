"""
codegen.py
Generates pandas fix code locally from profile results — no API needed.
"""

def generate_fix_code(df_info: dict, issues: list, col_profiles: dict) -> str:
    """Generate a complete pandas fix script from profiler output."""
    
    lines = []
    lines.append("import pandas as pd")
    lines.append("import numpy as np")
    lines.append("")
    lines.append("# ── Load data ────────────────────────────────────────────")
    lines.append("df = pd.read_csv('data.csv')")
    lines.append(f"print(f'Loaded {{len(df)}} rows x {{len(df.columns)}} columns')")
    lines.append("print('-' * 50)")
    lines.append("fixes_applied = []")
    lines.append("")

    issue_types = {i["type"] for i in issues}
    cols = df_info.get("columns", [])

    # ── Column name fix ───────────────────────────────────────────────────────
    if "column_names" in issue_types:
        lines.append("# ── Fix 1: Column names (remove spaces, lowercase) ──────")
        lines.append("df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace(r'[^a-z0-9_]', '', regex=True)")
        lines.append("print('✅ Fixed: Column names cleaned')")
        lines.append("fixes_applied.append('Column names standardised')")
        lines.append("")

    # ── Duplicates ────────────────────────────────────────────────────────────
    if "duplicates" in issue_types:
        lines.append("# ── Fix 2: Remove exact duplicate rows ──────────────────")
        lines.append("before = len(df)")
        lines.append("df = df.drop_duplicates()")
        lines.append("removed = before - len(df)")
        lines.append("print(f'✅ Fixed: Removed {removed} duplicate rows')")
        lines.append("fixes_applied.append(f'Removed {removed} duplicate rows')")
        lines.append("")

    if "near_duplicates" in issue_types:
        id_cols = [c for c in cols if any(k in c.lower() for k in ["id", "key", "uuid"])]
        non_id = [c for c in cols if c not in id_cols]
        if non_id:
            lines.append("# ── Fix 3: Remove near-duplicate rows (same data, different ID) ──")
            lines.append(f"non_id_cols = {non_id}")
            lines.append("before = len(df)")
            lines.append("df = df.drop_duplicates(subset=non_id_cols, keep='first')")
            lines.append("removed = before - len(df)")
            lines.append("print(f'✅ Fixed: Removed {removed} near-duplicate rows')")
            lines.append("fixes_applied.append(f'Removed {removed} near-duplicate rows')")
            lines.append("")

    # ── Per-column fixes ──────────────────────────────────────────────────────
    fix_num = 4
    for col, info in col_profiles.items():
        col_issues = info.get("issues", [])
        dtype = info.get("dtype", "")
        null_pct = info.get("null_pct", 0)

        safe_col = f'"{col}"'

        # Replace string NULLs first
        if dtype == "object":
            lines.append(f"# ── Fix {fix_num}: Replace string NULLs in '{col}' ──────────────")
            lines.append(f"df[{safe_col}] = df[{safe_col}].replace(['NULL','None','NA','NaN','nan',''], pd.NA)")
            fix_num += 1
            lines.append("")

        # Missing values
        null_issues = [i for i in col_issues if "missing" in i.lower() or "null" in i.lower() or "empty" in i.lower()]
        if null_issues and null_pct > 0:
            lines.append(f"# ── Fix {fix_num}: Handle missing values in '{col}' ({null_pct:.1f}% null) ──")
            if dtype in ["int64", "float64"] or "int" in dtype or "float" in dtype:
                lines.append(f"median_val = df[{safe_col}].median()")
                lines.append(f"df[{safe_col}] = df[{safe_col}].fillna(median_val)")
                lines.append(f"print(f'✅ Fixed: Filled {null_pct:.1f}% nulls in \"{col}\" with median ({{median_val:.2f}})')")
            else:
                lines.append(f"mode_val = df[{safe_col}].mode()")
                lines.append(f"fill_val = mode_val[0] if len(mode_val) > 0 else 'Unknown'")
                lines.append(f"df[{safe_col}] = df[{safe_col}].fillna(fill_val)")
                lines.append(f"print(f'✅ Fixed: Filled {null_pct:.1f}% nulls in \"{col}\" with mode ({{fill_val}})')")
            lines.append(f"fixes_applied.append('Filled missing values in {col}')")
            fix_num += 1
            lines.append("")

        # Inconsistent casing
        if any("casing" in i.lower() for i in col_issues):
            lines.append(f"# ── Fix {fix_num}: Standardise casing in '{col}' ──────────────────")
            lines.append(f"df[{safe_col}] = df[{safe_col}].str.strip().str.title()")
            lines.append(f"print('✅ Fixed: Standardised casing in \"{col}\"')")
            lines.append(f"fixes_applied.append('Standardised casing in {col}')")
            fix_num += 1
            lines.append("")

        # Whitespace
        if any("whitespace" in i.lower() for i in col_issues):
            lines.append(f"# ── Fix {fix_num}: Strip whitespace in '{col}' ──────────────────")
            lines.append(f"df[{safe_col}] = df[{safe_col}].str.strip()")
            lines.append(f"print('✅ Fixed: Stripped whitespace in \"{col}\"')")
            fix_num += 1
            lines.append("")

        # Wrong dtype (numeric stored as string)
        if any("numeric" in i.lower() for i in col_issues):
            lines.append(f"# ── Fix {fix_num}: Convert '{col}' from text to numeric ──────────")
            lines.append(f"df[{safe_col}] = pd.to_numeric(df[{safe_col}], errors='coerce')")
            lines.append(f"print('✅ Fixed: Converted \"{col}\" to numeric')")
            lines.append(f"fixes_applied.append('Converted {col} to numeric dtype')")
            fix_num += 1
            lines.append("")

        # Date format
        if any("date" in i.lower() for i in col_issues):
            lines.append(f"# ── Fix {fix_num}: Standardise date format in '{col}' ───────────")
            lines.append(f"df[{safe_col}] = pd.to_datetime(df[{safe_col}], errors='coerce', infer_datetime_format=True)")
            lines.append(f"df[{safe_col}] = df[{safe_col}].dt.strftime('%Y-%m-%d')")
            lines.append(f"print('✅ Fixed: Standardised dates in \"{col}\" to YYYY-MM-DD')")
            lines.append(f"fixes_applied.append('Standardised date format in {col}')")
            fix_num += 1
            lines.append("")

        # Outliers — cap to IQR bounds
        if any("outlier" in i.lower() for i in col_issues):
            lines.append(f"# ── Fix {fix_num}: Cap outliers in '{col}' using IQR ───────────")
            lines.append(f"Q1 = df[{safe_col}].quantile(0.25)")
            lines.append(f"Q3 = df[{safe_col}].quantile(0.75)")
            lines.append(f"IQR = Q3 - Q1")
            lines.append(f"lower = Q1 - 1.5 * IQR")
            lines.append(f"upper = Q3 + 1.5 * IQR")
            lines.append(f"before_count = ((df[{safe_col}] < lower) | (df[{safe_col}] > upper)).sum()")
            lines.append(f"df[{safe_col}] = df[{safe_col}].clip(lower=lower, upper=upper)")
            lines.append(f"print(f'✅ Fixed: Capped {{before_count}} outliers in \"{col}\" to [{{lower:.2f}}, {{upper:.2f}}]')")
            lines.append(f"fixes_applied.append('Capped outliers in {col}')")
            fix_num += 1
            lines.append("")

    # ── Summary ───────────────────────────────────────────────────────────────
    lines.append("# ── Summary & save ──────────────────────────────────────────")
    lines.append("print('=' * 50)")
    lines.append("print(f'Total fixes applied: {len(fixes_applied)}')")
    lines.append("for f in fixes_applied:")
    lines.append("    print(f'  • {f}')")
    lines.append("print(f'Final shape: {len(df)} rows x {len(df.columns)} columns')")
    lines.append("")
    lines.append("df.to_csv('data_cleaned.csv', index=False)")
    lines.append("print('\\n✅ Saved cleaned data to data_cleaned.csv')")

    return "\n".join(lines)
