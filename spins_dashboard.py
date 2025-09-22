# --- Minimal, cloud-safe Streamlit app (CSV only) ---

from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Neolea – SPINS (Selected Period, CSV only)", layout="wide")

CSV_PATH = Path("data/neolea_spins_singleperiod.csv")

# ---- Load data
if not CSV_PATH.exists():
    st.error(f"Data file not found: {CSV_PATH}. Commit it to the repo (data/...).")
    st.stop()

df = pd.read_csv(CSV_PATH)

# Clean types
for col in ["units", "dollars", "stores"]:
    if col in df:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# Only Neolea (defensive)
if "brand" in df:
    df = df[df["brand"].astype(str).str.upper() == "NEOLEA"].copy()

# Parse report_month if present
if "report_month" in df:
    df["report_month"] = pd.to_datetime(df["report_month"], errors="coerce")
    df = df.dropna(subset=["report_month"])

# ---- Sidebar filters
st.sidebar.header("Filters")

# month(s)
if "report_month" in df:
    months = sorted(df["report_month"].dt.strftime("%Y-%m-%d").unique().tolist())
    picked_months = st.sidebar.multiselect("Report month(s)", options=months, default=months)
    if picked_months:
        df = df[df["report_month"].dt.strftime("%Y-%m-%d").isin(picked_months)]
else:
    st.sidebar.info("This CSV has no 'report_month' column.")

# retailers (chains)
if "chain" in df:
    all_chains = sorted(df["chain"].astype(str).fillna("").unique().tolist())
    picked_chains = st.sidebar.multiselect("Retailers (chains)", options=all_chains, default=all_chains)
    if picked_chains:
        df = df[df["chain"].astype(str).isin(picked_chains)]
else:
    st.sidebar.warning("No 'chain' column in CSV.")

# ---- Metrics
st.title("Neolea – SPINS (Selected Period)")

u = float(df["units"].sum(skipna=True)) if "units" in df else 0.0
d = float(df["dollars"].sum(skipna=True)) if "dollars" in df else 0.0

# IMPORTANT: stores here are simple sum from CSV (selected period).
s = float(df["stores"].sum(skipna=True)) if "stores" in df else 0.0

# Velocity = units per store for the selected period
vel = (u / s) if s > 0 else float("nan")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Units (sum)", f"{int(round(u)):,.0f}")
c2.metric("Sales $ (sum)", f"${d:,.0f}")
c3.metric("Stores (sum)", f"{int(round(s)):,.0f}")
c4.metric("Velocity SPP", f"{vel:,.3f}" if pd.notna(vel) else "—")

st.markdown("---")

# ---- Table
show_cols = [c for c in ["chain", "units", "dollars", "stores"] if c in df.columns]
if show_cols:
    st.subheader("Retailer detail")
    st.dataframe(
        df[show_cols].sort_values("dollars", ascending=False) if "dollars" in show_cols else df[show_cols],
        use_container_width=True
    )
else:
    st.info("No expected columns found in CSV.")

