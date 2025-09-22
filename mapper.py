import io
import math
import pandas as pd
import streamlit as st
from backend.columns import suggest_mapping, profile_key, save_mapping

st.set_page_config(page_title="SPINS Column Mapping Wizard", layout="wide")
st.title("🧭 SPINS Column Mapping Wizard (Multi-row headers)")

uploaded = st.file_uploader("Upload a SPINS file (.xlsb or .xlsx)", type=["xlsb","xlsx"])
if not uploaded:
    st.info("Upload a file to begin.")
    st.stop()

name = (uploaded.name or "").lower()
engine = "pyxlsb" if name.endswith(".xlsb") else None

# Open workbook
try:
    xls = pd.ExcelFile(uploaded, engine=engine)
except Exception as e:
    st.error(f"Could not open Excel file: {e}")
    st.stop()

sheet = st.selectbox("Sheet", xls.sheet_names, index=0)

# Load raw WITHOUT headers so we can choose header rows manually
try:
    raw = pd.read_excel(xls, sheet_name=sheet, engine=engine, header=None)
except Exception as e:
    st.error(f"Could not read sheet: {e}")
    st.stop()

st.caption("Preview (raw, first 30 rows) — use this to locate header rows.")
st.dataframe(raw.head(30), width="stretch")

st.markdown("### Pick header rows (multi-row allowed) and first data row")
max_row = min(200, len(raw) - 1)
start_hdr = st.number_input("Header start row (0-based)", min_value=0, max_value=max_row, value=0, step=1)
end_hdr   = st.number_input("Header end row (inclusive, 0-based)", min_value=start_hdr, max_value=max_row, value=start_hdr, step=1)
data_start = st.number_input("First data row (0-based, typically end_hdr+1)", min_value=end_hdr+1, max_value=max_row, value=min(end_hdr+1, max_row), step=1)

def norm_cell(x):
    if x is None or (isinstance(x, float) and math.isnan(x)): return ""
    s = str(x).strip()
    if not s: return ""
    if s.lower().startswith("unnamed"): return ""
    return s

# Build headers by concatenating the selected header rows for each column
header_block = raw.iloc[int(start_hdr):int(end_hdr)+1]
parts = header_block.fillna("").astype(str).applymap(norm_cell).values
# transpose to work per column
combined = []
for col_idx in range(header_block.shape[1]):
    tokens = [norm_cell(parts[r_idx][col_idx]) for r_idx in range(parts.shape[0])]
    tokens = [t for t in tokens if t]  # drop empties
    combined.append(" | ".join(tokens) if tokens else "")

# Create framed DataFrame with those headers; drop fully empty headers
df = raw.iloc[int(data_start):].copy()
df.columns = combined
keep_cols = []
for h in df.columns:
    hh = (h or "").strip()
    if not hh or hh.lower().startswith("unnamed"):
        continue
    keep_cols.append(h)
df = df.loc[:, keep_cols].reset_index(drop=True)

st.subheader("Detected headers after multi-row build")
st.write(list(df.columns))

suggested = suggest_mapping(list(df.columns))

st.subheader("Confirm mapping")
cols = st.columns(5)
options = ["(none)"] + list(df.columns)

def pick(label, key):
    default = suggested.get(key)
    idx = options.index(default) if default in options else 0
    return cols[["brand","chain","units","dollars","stores"].index(key)].selectbox(label, options, index=idx)

brand   = pick("Brand column",   "brand")
chain   = pick("Retailer (Chain) column", "chain")
units   = pick("Units column",   "units")
dollars = pick("Dollars column", "dollars")
stores  = pick("Stores column (doors count)", "stores")

final_map = {
    "brand":   None if brand=="(none)" else brand,
    "chain":   None if chain=="(none)" else chain,
    "units":   None if units=="(none)" else units,
    "dollars": None if dollars=="(none)" else dollars,
    "stores":  None if stores=="(none)" else stores,
}

st.subheader("Preview (first 10 rows using your mapping)")
preview = df.rename(columns={v:k for k,v in final_map.items() if v})
keep = [c for c in ["brand","chain","units","dollars","stores"] if c in preview.columns]
if keep:
    st.dataframe(preview[keep].head(10), width="stretch")
else:
    st.info("Select at least one mapping to see a preview.")

# Save a profile tied to the *resulting* headers so this layout auto-maps next time
profile_headers = list(df.columns)
key = profile_key(uploaded.name, sheet, profile_headers)

if st.button("💾 Save mapping for this layout"):
    save_mapping(key, {k:(v or "") for k,v in final_map.items()})
    st.success("Saved! Now go back to the main dashboard and re-upload the SAME layout.")
    st.caption("If SPINS changes layout later, re-run this wizard and save a new mapping.")
