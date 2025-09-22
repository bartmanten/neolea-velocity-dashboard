# spins_dashboard.py — single-period, Neolea-only, clean sidebar
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Neolea – SPINS (Single Period)", layout="wide")

CSV_PATH = Path("data/neolea_spins_singleperiod.csv")

# ---- Load
if not CSV_PATH.exists():
    st.error(f"Data file not found: {CSV_PATH}. Run:  python -m backend.ingest")
    st.stop()

df = pd.read_csv(CSV_PATH, dtype={"report_month": str})

# Clean types
for c in ("units","dollars","stores"):
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

# Force brand to uppercase, keep Neolea only
df["brand"] = df.get("brand","").astype(str)
df = df[df["brand"].str.upper() == "NEOLEA"].copy()

# Parse dates if present
if "report_month" in df.columns:
    df["report_month"] = pd.to_datetime(df["report_month"], errors="coerce")

# Clean chain & drop junk
df["chain"] = df.get("chain","").astype(str).str.strip()
df = df[df["chain"].ne("")]

# Sidebar — month and retailer pickers
st.sidebar.header("Filters")

# Month selector (by file’s report_month if available; else show file date text)
if "report_month" in df.columns and df["report_month"].notna().any():
    months = sorted(df["report_month"].dropna().unique().tolist())
    picked_months = st.sidebar.multiselect(
        "Report month(s)", options=months, default=months
    )
    df = df[df["report_month"].isin(picked_months)]
else:
    # fallback: keep all
    picked_months = []
    st.sidebar.info("No month metadata found; showing all.")

# Retailers list — strictly from chain names
retailers = sorted(df["chain"].dropna().astype(str).unique().tolist())
picked_retailers = st.sidebar.multiselect(
    "Retailers (chains)", options=retailers, default=retailers
)

if not picked_retailers:
    st.info("Select at least one retailer.")
    st.stop()

df = df[df["chain"].isin(picked_retailers)].copy()

# Main
st.title("Neolea – SPINS (Selected Period)")
st.caption("This view reflects one selected period per file export (SPINS). Velocity shown is **per store per selected period (SPP)**.")

# KPI row
total_units = df["units"].sum(skipna=True) if "units" in df else 0
total_dollars = df["dollars"].sum(skipna=True) if "dollars" in df else 0.0
total_stores = df["stores"].sum(skipna=True) if "stores" in df else 0.0

# Velocity SPP (per store per period). Guard divide-by-zero.
velocity_spp = None
den = total_stores if total_stores and total_stores > 0 else None
if den:
    velocity_spp = total_units / den

c1, c2, c3, c4 = st.columns(4)
c1.metric("Units (sum)", f"{int(round(total_units)):,}")
c2.metric("Sales $ (sum)", f"${total_dollars:,.0f}")
c3.metric("Stores (sum)", f"{int(round(total_stores)):,}")
c4.metric("Velocity SPP", f"{velocity_spp:.3f}" if velocity_spp is not None else "—")

st.markdown("---")

# By retailer table
show = df[["chain","units","dollars","stores"]].copy()
show = show.groupby("chain", as_index=False).agg(
    units=("units","sum"),
    dollars=("dollars","sum"),
    stores=("stores","sum"),
)
# velocity per store per period by chain (not weighted)
show["velocity_spp"] = show.apply(
    lambda r: (r["units"] / r["stores"]) if pd.notna(r["units"]) and pd.notna(r["stores"]) and r["stores"] > 0 else None,
    axis=1
)

st.subheader("Retailer detail")
st.dataframe(show.sort_values("dollars", ascending=False), height=420)

# Optional download
st.download_button(
    "Download current view (CSV)",
    data=show.to_csv(index=False),
    file_name="neolea_singleperiod_retailers.csv",
    mime="text/csv",
)
