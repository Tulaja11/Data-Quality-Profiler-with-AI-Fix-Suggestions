import streamlit as st
import pandas as pd
import io as _io
import os
from src.profiler import profile_dataframe
from src.codegen import generate_fix_code

st.set_page_config(
    page_title="Data Quality Profiler",
    page_icon="📊",
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Inter:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #ffffff;
}

/* ── Header ── */
.app-header {
    padding: 2rem 0 1rem;
    border-bottom: 1px solid #f1f5f9;
    margin-bottom: 1.5rem;
}
.app-title {
    font-size: 1.9rem;
    font-weight: 600;
    color: #ffffff;
    letter-spacing: -0.4px;
    margin: 0;
}
.app-subtitle {
    font-size: 0.95rem;
    color: #f5f5dc;
    margin-top: 4px;
    font-weight: 400;
}

/* ── Metric cards ── */
.metric-row { display: flex; gap: 12px; margin-bottom: 1.5rem; }
.metric-box {
    flex: 1;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 1rem 1.1rem;
    text-align: center;
}
.metric-value {
    font-size: 1.65rem;
    font-weight: 600;
    color: #111827;
    line-height: 1.1;
}
.metric-value.red    { color: #dc2626; }
.metric-value.amber  { color: #d97706; }
.metric-value.green  { color: #16a34a; }
.metric-value.indigo { color: #4f46e5; }
.metric-key {
    font-size: 0.7rem;
    font-weight: 500;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-top: 4px;
}

/* ── Issue rows ── */
.issue-row {
    display: flex;
    gap: 12px;
    align-items: flex-start;
    padding: 0.85rem 1rem;
    border-radius: 6px;
    margin-bottom: 6px;
    border: 1px solid #e5e7eb;
    background: #fafafa;
}
.issue-dot {
    width: 8px; height: 8px; border-radius: 50%;
    margin-top: 5px; flex-shrink: 0;
}
.dot-critical { background: #dc2626; }
.dot-warning  { background: #d97706; }
.dot-info     { background: #6366f1; }
.issue-body {}
.issue-title-text { font-size: 0.88rem; font-weight: 500; color: #111827; }
.issue-detail-text { font-size: 0.82rem; color: #6b7280; margin-top: 2px; line-height: 1.5; }

/* ── Severity pill ── */
.pill {
    display: inline-block;
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 1px 7px;
    border-radius: 4px;
    margin-right: 6px;
    vertical-align: middle;
}
.pill-critical { background: #fee2e2; color: #991b1b; }
.pill-warning  { background: #fef3c7; color: #92400e; }
.pill-info     { background: #e0e7ff; color: #3730a3; }

/* ── Section label ── */
.section-label {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: #9ca3af;
    margin: 1.5rem 0 0.6rem;
}

/* ── Code block header ── */
.code-header {
    background: #f1f5f9;
    border: 1px solid #e2e8f0;
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    padding: 0.5rem 1rem;
    font-size: 0.78rem;
    font-weight: 500;
    color: #475569;
    font-family: 'JetBrains Mono', monospace;
}

/* ── Upload box ── */
.upload-box {
    border: 1.5px dashed #d1d5db;
    border-radius: 8px;
    padding: 2.5rem 2rem;
    text-align: center;
    background: #f9fafb;
    color: #6b7280;
    font-size: 0.9rem;
}
.upload-box b { color: #374151; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #f9fafb;
    border-right: 1px solid #e5e7eb;
}
section[data-testid="stSidebar"] .sidebar-title {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: #9ca3af;
    margin-bottom: 0.5rem;
}
section[data-testid="stSidebar"] .check-item {
    font-size: 0.85rem;
    color: #374151;
    padding: 3px 0;
}

/* ── Expander ── */
.streamlit-expanderHeader {
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    color: #374151 !important;
}

/* Hide streamlit branding */
#MainMenu, footer { visibility: hidden; }

/* Tab styling */
button[data-baseweb="tab"] {
    font-size: 0.83rem !important;
    font-weight: 500 !important;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
  <div class="app-title">📊 Data Quality Profiler</div>
  <div class="app-subtitle">Upload any CSV to detect data quality issues and get a ready-to-run Python fix script.</div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-title">Checks performed</div>', unsafe_allow_html=True)
    checks = [
        "Missing & null values",
        "Duplicate rows",
        "Near-duplicate rows",
        "Wrong data types",
        "Outliers (IQR method)",
        "Inconsistent casing",
        "Date format issues",
        "Whitespace in values",
        "Column name problems",
    ]
    for c in checks:
        st.markdown(f'<div class="check-item">· {c}</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="sidebar-title">Sample dataset</div>', unsafe_allow_html=True)
    if st.button("Load sample CSV", use_container_width=True):
        st.session_state["use_sample"] = True
        st.session_state["fix_code_generated"] = False
        st.rerun()

# ── File Upload ───────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "Upload CSV",
    type=["csv"],
    label_visibility="collapsed",
)

if st.session_state.get("use_sample") and not uploaded_file:
    sample_path = os.path.join(os.path.dirname(__file__), "sample_data.csv")
    uploaded_file = _io.StringIO(open(sample_path).read())
    uploaded_file.name = "sample_data.csv"

if uploaded_file is None:
    st.markdown("""
    <div class="upload-box">
        <b>Drop a CSV file above</b><br>
        or use the sample dataset from the sidebar
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── Load ─────────────────────────────────────────────────────────────────────
try:
    df = pd.read_csv(uploaded_file)
except Exception as e:
    st.error(f"Could not read file: {e}")
    st.stop()

fname = getattr(uploaded_file, "name", "file")
st.caption(f"Loaded **{fname}** — {df.shape[0]:,} rows × {df.shape[1]} columns")

# ── Profile ───────────────────────────────────────────────────────────────────
with st.spinner("Analysing..."):
    profile = profile_dataframe(df)

score       = profile["quality_score"]
score_color = "green" if score >= 80 else "amber" if score >= 60 else "red"
score_label = "Good" if score >= 80 else "Needs work" if score >= 60 else "Poor"
n_issues    = len(profile["issues"])
n_missing   = profile["total_missing"]
n_dupes     = profile["duplicate_rows"]

# ── Metrics ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5, c6 = st.columns(6)
def metric_card(col, value, label, color=""):
    with col:
        st.markdown(
            f'<div class="metric-box">'
            f'<div class="metric-value {color}">{value}</div>'
            f'<div class="metric-key">{label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

metric_card(c1, f"{score}/100", f"Quality · {score_label}", score_color)
metric_card(c2, f"{df.shape[0]:,}", "Rows", "indigo")
metric_card(c3, str(df.shape[1]), "Columns", "indigo")
metric_card(c4, str(n_missing), "Missing values", "red" if n_missing else "green")
metric_card(c5, str(n_dupes),   "Duplicate rows", "red" if n_dupes   else "green")
metric_card(c6, str(n_issues),  "Issues found",   "amber" if n_issues else "green")

# ── Score breakdown ───────────────────────────────────────────────────────────
# Shows WHY the score landed where it did, not just the number - each
# dimension is a rate (% of data unaffected), so it stays readable even on
# wide datasets instead of just stacking penalties.
dims = profile.get("dimension_scores", {})
if dims:
    st.markdown("<br>", unsafe_allow_html=True)
    d1, d2, d3, d4 = st.columns(4)
    dim_labels = {
        "completeness": "Completeness",
        "validity": "Validity",
        "uniqueness": "Uniqueness",
        "consistency": "Consistency",
    }
    for col, key in zip([d1, d2, d3, d4], dim_labels):
        with col:
            st.caption(dim_labels[key])
            st.progress(min(1.0, dims.get(key, 0) / 100))
            st.caption(f"{dims.get(key, 0):.0f}/100")

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["Issues", "Fix Script", "Column Details", "Data Preview"])

# ── Tab 1: Issues ─────────────────────────────────────────────────────────────
with tab1:
    issues = profile["issues"]
    if not issues:
        st.success("No issues found — your dataset looks clean.")
    else:
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        for issue in sorted(issues, key=lambda x: severity_order.get(x["severity"], 3)):
            sev = issue["severity"]
            st.markdown(
                f'<div class="issue-row">'
                f'<div class="issue-dot dot-{sev}"></div>'
                f'<div class="issue-body">'
                f'<div class="issue-title-text">'
                f'<span class="pill pill-{sev}">{sev}</span>'
                f'{issue["title"]}</div>'
                f'<div class="issue-detail-text">{issue["detail"]}</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

# ── Tab 2: Fix Script ─────────────────────────────────────────────────────────
with tab2:
    st.markdown("Generate a complete pandas script that fixes every issue detected above.")
    generate_btn = st.button("Generate fix script", type="primary")

    if generate_btn or st.session_state.get("fix_code_generated"):
        if not st.session_state.get("fix_code_generated"):
            with st.spinner("Building fix script..."):
                df_info = {"columns": list(df.columns), "shape": df.shape}
                code = generate_fix_code(df_info, profile["issues"], profile["column_profiles"])
                st.session_state["fix_code"] = code
                st.session_state["fix_code_generated"] = True

        code = st.session_state.get("fix_code", "")
        if code:
            st.markdown('<div class="code-header">fix_data.py</div>', unsafe_allow_html=True)
            st.code(code, language="python")

            col_a, col_b = st.columns([1, 5])
            with col_a:
                st.download_button(
                    "Download fix_data.py",
                    data=code,
                    file_name="fix_data.py",
                    mime="text/x-python",
                )
            with col_b:
                st.caption("Place `fix_data.py` in the same folder as your CSV, rename your file to `data.csv`, then run `python fix_data.py`")

            if st.button("↺ Regenerate"):
                st.session_state["fix_code_generated"] = False
                st.rerun()

# ── Tab 3: Column Details ─────────────────────────────────────────────────────
with tab3:
    for col_name, col_info in profile["column_profiles"].items():
        null_pct   = col_info.get("null_pct", 0)
        dtype      = col_info.get("dtype", "")
        col_issues = col_info.get("issues", [])
        flag       = "⚠" if col_issues else "✓"
        with st.expander(f"{flag}  {col_name}   —   {dtype}   |   {null_pct:.1f}% missing"):
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Missing",  f"{col_info.get('null_count',0)} ({null_pct:.1f}%)")
            m2.metric("Unique",   str(col_info.get("unique_count", "—")))
            m3.metric("Type",     dtype)
            m4.metric("Issues",   str(len(col_issues)))
            if col_info.get("sample_values"):
                vals = "  ·  ".join(str(v) for v in col_info["sample_values"][:6])
                st.caption(f"Sample values: {vals}")
            if col_info.get("stats"):
                st.json(col_info["stats"])
            for i in col_issues:
                st.markdown(f"- {i}")

# ── Tab 4: Data Preview ───────────────────────────────────────────────────────
with tab4:
    st.caption(f"Showing first 50 of {df.shape[0]:,} rows. Highlighted cells = missing or null values.")

    preview_df = df.head(50).copy()
    preview_df = preview_df.replace(["NULL", "None", "NA", "NaN", "nan", "none", "N/A", ""], pd.NA)

    NULL_STRINGS = {"null", "none", "na", "nan", "n/a", ""}

    def highlight_nulls(val):
        try:
            if val is None or val is pd.NA or pd.isna(val):
                return "background-color: #fee2e2; color: #991b1b;"
        except Exception:
            pass
        if str(val).strip().lower() in NULL_STRINGS:
            return "background-color: #fee2e2; color: #991b1b;"
        return ""

    try:
        styled = preview_df.style.applymap(highlight_nulls)
        st.dataframe(styled, use_container_width=True, height=480)
    except Exception:
        st.dataframe(preview_df, use_container_width=True, height=480)
