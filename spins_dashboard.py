# spins_dashboard.py — Verification-first dashboard (single-period, brand=NEOLEA)

from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Neolea – SPINS Verifier", layout="wide")

CSV_PATH = Path("data/neolea_spins_singleperiod.csv")

# ---------- Load ----------
if not CSV_PATH.exists():
    st.error(f"Data file not found: {CSV_PATH}\nBuild it locally with:\n  python - <<'PY'\nfrom pathlib import Path\nimport pandas as pd\nfrom backend.ingest import ingest_single_period\nfiles = sorted(Path('data').glob('*.xlsb'))\nparts = []\nfor f in files:\n    d = ingest_single_period(f)\n    d['source_file'] = f.name\n    parts.append(d)\nif parts:\n    out = pd.concat(parts, ignore_index=True)\n    out.to_csv('data/neolea_spins_singleperiod.csv', index=False)\n    print('Wrote data/neolea_spins_singleperiod.csv rows:', len(out))\nelse:\n    print('No .xlsb files found under ./data')\nPY")
    st.stop()

df = pd.read_csv(CSV_PATH, dtype={"report_month": "string"}, low_memory=False)

# Normalize columns that should exist
expected = ["chain","units","dollars","stores","brand","report_date","report_month","period"]
for c in expected:
    if c not in df.columns:
        df[c] = pd.NA

# Types / cleaning
df["chain"] = df["chain"].astype(str).str.strip()
df["brand"] = df["brand"].astype(str).str.strip()
df["period"] = df["period"].astype(str).str.strip()
if "report_month" in df:
    df["report_month"] = pd.to_datetime(df["report_month"], errors="coerce")

# Filter to Neolea only
df = df[df["brand"].str.upper() == "NEOLEA"].copy()

# ---------- UI: pick ONE period then retailers ----------
st.sidebar.header("Filters")
periods = [p for p in sorted(df["period"].dropna().unique().tolist()) if p and p != "nan"]
if not periods:
    st.error("No period labels found in CSV. The ingest didn’t detect ‘4w’, ‘52w’ or ‘ytd’.")
    st.stop()

picked_period = st.sidebar.selectbox("Period", periods, index=0)

dfp = df[df["period"] == picked_period].copy()
if len(dfp) == 0:
    st.warning(f"No rows for period: {picked_period}")
    st.stop()

retailers = sorted(dfp["chain"].dropna().unique().tolist())
picked_retailers = st.sidebar.multiselect(
    "Retailers",
    options=retailers,
    default=retailers,
    key="retailers_ms",
)

if not picked_retailers:
    st.info("Pick at least one retailer.")
    st.stop()

dfv = dfp[dfp["chain"].isin(picked_retailers)].copy()

# ---------- KPIs ----------
# Stores here are **per retailer** doors for the selected period. Summing across retailers
# gives total doors across selected retailers (not store-weeks).
total_units = pd.to_numeric(dfv["units"], errors="coerce").sum(skipna=True)
total_dollars = pd.to_numeric(dfv["dollars"], errors="coerce").sum(skipna=True)
# Two ways to show "stores": sum across retailers, and median per retailer (sanity check)
stores_series = pd.to_numeric(dfv["stores"], errors="coerce")
stores_sum = stores_series.sum(skipna=True)
stores_median = stores_series.median(skipna=True)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Units (sum)", f"{int(round(total_units)):,}")
col2.metric("Sales $ (sum)", f"${total_dollars:,.0f}")
col3.metric("Stores (sum of retailers)", f"{int(round(stores_sum)):,}")
col4.metric("Stores per Retailer (median)", f"{stores_median:,.0f}" if pd.notna(stores_median) else "—")

st.caption(
    "Note: ‘Stores (sum of retailers)’ is the simple sum of each retailer’s **doors** in the selected period. "
    "Doors should not be multiplied by weeks. If this sum looks too high, the CSV may contain store-weeks instead of doors."
)

# ---------- Table ----------
show_cols = ["chain","units","dollars","stores","period","report_date","report_month"]
show_cols = [c for c in show_cols if c in dfv.columns]
st.dataframe(dfv[show_cols].sort_values("chain"), use_container_width=True)

# ---------- Debug / Verification ----------
with st.expander("🔎 Debug / Verify what the app is reading", expanded=False):
    st.write("**CSV path:**", str(CSV_PATH))
    st.write("**Columns present:**", list(df.columns))
    st.write("**Dtypes:**")
    st.write(df.dtypes.astype(str).to_dict())

    st.write("**Unique periods in CSV:**", sorted([p for p in df["period"].dropna().unique().tolist() if p and p != "nan"]))
    st.write("**Unique chains (this period):**", retailers)

    st.write("**First 15 rows for this period (Neolea only):**")
    st.dataframe(dfp.head(15), use_container_width=True)

    # Fresh Market sanity check
    fm = dfp[dfp["chain"].str.contains("FRESH MARKET", case=False, na=False)].copy()
    if len(fm):
        st.subheader("The Fresh Market rows (selected period)")
        st.dataframe(fm[show_cols], use_container_width=True)
        fm_stores = pd.to_numeric(fm["stores"], errors="coerce")
        st.write("Fresh Market stores values:", fm_stores.tolist())
        # warn if clearly store-weeks
        if fm_stores.max() and fm_stores.max() > 300:
            st.error(
                "⚠️ The Fresh Market `stores` value is > 300. That looks like **store-weeks**, not doors. "
                "We need to adjust the ingest to use the **‘# of Stores Selling’** column from the Retailer tab (Column X)."
            )
    else:
        st.write("No Fresh Market row found for this period in the CSV.")

st.success("Loaded CSV and filtered to Neolea. Pick a period and retailers in the sidebar.")
