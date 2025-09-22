# backend/ingest.py — tolerant single-period ingest
import re
import math
from pathlib import Path
from typing import Optional, Tuple, List

import pandas as pd

DATA_DIR = Path("data")

# ----------------- helpers -----------------

def _pick_engine(path: Path) -> Optional[str]:
    return "pyxlsb" if str(path).lower().endswith(".xlsb") else None

def _norm_cell(x) -> str:
    if x is None: return ""
    if isinstance(x, float) and math.isnan(x): return ""
    s = str(x).strip()
    if s.lower().startswith("unnamed"): return ""
    return s

def _parse_date_from_name(name: str) -> Tuple[Optional[str], Optional[str]]:
    m = re.search(r"ending\s+(\d{2})-(\d{2})-(\d{2})", name.lower())
    if not m:
        return None, None
    mm, dd, yy = m.groups()
    yyyy = f"20{yy}"
    return f"{yyyy}-{mm}-{dd}", f"{yyyy}-{mm}-01"

def _find_header_block(raw: pd.DataFrame, max_scan: int = 200) -> Optional[Tuple[int,int,int]]:
    """
    Find the header block: scan for a row that contains 'Row Labels' (case-insensitive).
    Use that as the *end* of header; include up to 3 rows above to capture period labels.
    """
    upto = min(max_scan, len(raw))
    end_hdr = None
    for i in range(upto):
        row = raw.iloc[i].astype(str).str.strip().str.lower()
        if any("row labels" in c for c in row):
            end_hdr = i
            break
    if end_hdr is None:
        return None
    start_hdr = max(0, end_hdr - 3)
    data_start = end_hdr + 1
    return (start_hdr, end_hdr, data_start)

def _combine_headers(raw: pd.DataFrame, start_hdr: int, end_hdr: int) -> List[str]:
    blk = raw.iloc[start_hdr:end_hdr+1].copy()
    blk = blk.fillna("").astype(str)
    headers: List[str] = []
    for c in range(blk.shape[1]):
        tokens = [_norm_cell(v) for v in blk.iloc[:, c].tolist()]
        tokens = [t for t in tokens if t]
        headers.append(" | ".join(tokens) if tokens else "")
    return headers

def _guess_period_from_block(raw: pd.DataFrame, start_hdr: int, end_hdr: int) -> str:
    """
    Look for tokens like '4 WKS', '12 WKS', '24 WKS', '52 WKS', 'YTD' near the headers.
    Return '4','12','24','52','YTD' or 'unknown'.
    """
    text = " ".join(
        _norm_cell(x)
        for x in raw.iloc[max(0, start_hdr-5):end_hdr+1].fillna("").astype(str).values.ravel().tolist()
    ).upper()
    if "YTD" in text:
        return "YTD"
    for n in ("4", "12", "24", "52"):
        if re.search(rf"\b{n}\s*WKS?\b", text):
            return n
    return "unknown"

def _first_match(colnames: List[str], *needles: str) -> Optional[str]:
    """
    Return the first column whose name contains ALL needle fragments (case-insensitive).
    Each needle is matched as 'in string'.
    """
    needles = [n.lower() for n in needles]
    for c in colnames:
        lc = c.lower()
        if all(n in lc for n in needles):
            return c
    return None

def _find_columns(cols: List[str]) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Find chain, units, dollars, stores with forgiving patterns.
    """
    # Chain / retailer
    chain = (
        _first_match(cols, "row", "label") or
        _first_match(cols, "retailer") or
        _first_match(cols, "chain")
    )
    # Units
    units = (
        _first_match(cols, "units") or
        _first_match(cols, "unit")
    )
    # Dollars / Sales
    dollars = (
        _first_match(cols, "dollars") or
        _first_match(cols, "sales") or
        _first_match(cols, "$")
    )
    # Stores
    stores = (
        _first_match(cols, "stores", "selling") or
        _first_match(cols, "#", "stores") or
        _first_match(cols, "stores")
    )
    return chain, units, dollars, stores

# ----------------- main ingest -----------------

import re
from pathlib import Path
from typing import Optional, Tuple, List

import pandas as pd


# ---------------------------------
# tiny helpers
# ---------------------------------
def _pick_engine(p: Path) -> Optional[str]:
    return "pyxlsb" if str(p).lower().endswith(".xlsb") else None

def _parse_dates_from_name(name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parses '... Ending MM-DD-YY' from filename. Returns (report_date, report_month)
    as 'YYYY-MM-DD' and 'YYYY-MM-01'. If not found, (None, None).
    """
    m = re.search(r"ending\s+(\d{2})-(\d{2})-(\d{2})", name.lower())
    if not m:
        return None, None
    mm, dd, yy = m.groups()
    yyyy = f"20{yy}"
    return f"{yyyy}-{mm}-{dd}", f"{yyyy}-{mm}-01"

def _find_header_row(raw: pd.DataFrame, max_scan: int = 200) -> Optional[int]:
    """
    Scan the first rows to locate the header row that includes 'Row Labels'.
    """
    for i in range(min(max_scan, len(raw))):
        row = raw.iloc[i].astype(str).str.strip().str.lower()
        if any("row labels" in c for c in row):
            return i
    return None

def _guess_period_from_meta(raw: pd.DataFrame, header_row: int) -> str:
    """
    Look above the header for text that looks like '4 Wks', '52 Wks', 'YTD', etc.
    Returns one of {'4W','52W','YTD','unknown'}
    """
    window = raw.iloc[max(0, header_row-12):header_row].astype(str).apply(lambda s: s.str.lower())
    flat = " | ".join([" | ".join(r.values.tolist()) for _, r in window.iterrows()])

    # very lenient regexes
    if re.search(r"\b4\s*w(ee)?ks?\b|\b4wk\b|\b4 wks\b", flat):
        return "4W"
    if re.search(r"\b52\s*w(ee)?ks?\b|\b52wk\b|\b52 wks\b", flat):
        return "52W"
    if re.search(r"\bytd\b|\byear to date\b", flat):
        return "YTD"
    return "unknown"

def _choose_col(cols: List[str], *patterns: str) -> Optional[str]:
    """
    Find a column whose name matches any of the given regex patterns (case-insensitive).
    Returns the first match, or None if not found.
    """
    low = {c.lower(): c for c in cols}
    for pat in patterns:
        rgx = re.compile(pat, re.I)
        for lc, orig in low.items():
            if rgx.search(lc):
                return orig
    return None


# ---------------------------------
# main: single workbook -> tidy rows
# ---------------------------------
def ingest_single_period(file_path: Path) -> pd.DataFrame:
    """
    Read ONE workbook that contains the retailer-level table for a *single selected period*,
    and return tidy columns: chain, units, dollars, stores, brand, report_date, report_month, period.
    """
    engine = _pick_engine(file_path)
    xls = pd.ExcelFile(file_path, engine=engine)

    # Most likely sheets first
    preferred = [
        "Ret_Brand_Pivot",
        "Ret_Brand_All_B_Pivot",
        "Ret_BrandCategory_Pivot",
        "Ret_BrandCategory_All_B_Pivot",
        "Retailer",
    ]
    candidate_sheets = [s for s in preferred if s in xls.sheet_names]
    # fallback: anything that hints retailer pivots
    if not candidate_sheets:
        candidate_sheets = [s for s in xls.sheet_names if ("ret" in s.lower() or "brand" in s.lower()) and "pivot" in s.lower()]
    if not candidate_sheets:
        candidate_sheets = xls.sheet_names[:]  # last resort

    out_rows = []
    for sh in candidate_sheets:
        raw = pd.read_excel(xls, sheet_name=sh, engine=engine, header=None)
        header_row = _find_header_row(raw)
        if header_row is None:
            continue

        # Build headers from the header row only (robust, avoids multi-row noise)
        headers = raw.iloc[header_row].astype(str).str.strip()
        data = raw.iloc[header_row+1:].copy()
        data.columns = headers

        # Drop totally empty/unnamed columns
        keep_cols = []
        for c in data.columns:
            cs = str(c).strip()
            if cs and not cs.lower().startswith("unnamed"):
                keep_cols.append(c)
        data = data.loc[:, keep_cols].reset_index(drop=True)

        cols = list(map(str, data.columns))

        # Map the necessary columns
        chain_col = _choose_col(
            cols,
            r"^row labels$",
            r"\b(retailer|chain)\b"
        )
        units_col = _choose_col(cols, r"\b(sum of )?units\b")
        dollars_col = _choose_col(cols, r"\b(sum of )?dollars?\b|\brevenue\b|\bnet sales\b")
        # Prefer the EXACT SPINS calc column for store count (your Column X remark)
        stores_col = _choose_col(
            cols,
            r"\bsum of # of stores selling calc\b",  # exact SPINS label we saw
            r"\b# of stores\b",
            r"\bstores\b",
            r"\bdoors\b",
        )

        if not chain_col or not units_col or not dollars_col or not stores_col:
            # Not a usable sheet
            continue

        # Clean/filter the table
        df = data[[chain_col, units_col, dollars_col, stores_col]].copy()
        df = df.rename(columns={
# --- map columns robustly
chain_col   = _pick_col(df.columns, r"\brow labels\b", r"\bretailer\b", r"\bchain\b")
units_col   = _pick_col(df.columns, r"\bsum of units\b", r"\bunits\b")
dollars_col = _pick_col(df.columns, r"\bsum of dollars\b", r"\bdollars\b")

# Prefer the true doors column (column X in your Excel)
doors_col   = _pick_col(
    df.columns,
    r"^#?\s*of\s*stores\s*selling$",
    r"^#?\s*stores\s*selling$",
    r"\baverage\b.*stores.*selling",
    r"\bavg\b.*stores.*selling",
)

# Store-weeks (optional; some layouts have this “calc”)
storeweeks_col = _pick_col(
    df.columns,
    r"\bsum of # of stores selling calc\b",
    r"\bstores\s*weeks\b",
    r"\bstore[-\s]*weeks\b",
    r"\bdoors\s*weeks\b",
)

need = [chain_col, units_col, dollars_col]
if not all(need):
    # not usable – let upstream caller skip this file
    return pd.DataFrame()

df2 = df[[c for c in need if c]].copy()
df2.rename(columns={
    chain_col: "chain",
    units_col: "units",
    dollars_col: "dollars",
}, inplace=True)

# Attach doors and store_weeks if present
if doors_col and doors_col in df.columns:
    df2["doors"] = pd.to_numeric(df[doors_col], errors="coerce")
else:
    df2["doors"] = pd.NA

if storeweeks_col and storeweeks_col in df.columns:
    df2["store_weeks"] = pd.to_numeric(df[storeweeks_col], errors="coerce")
else:
    df2["store_weeks"] = pd.NA        })

        # Numeric coercion
        for c in ["units", "dollars", "stores"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        # Keep only rows that look like retailers (remove grand totals/empty)
        df["chain"] = df["chain"].astype(str).str.strip()
        df = df[df["chain"].str.len() > 0]
        # Common rollups we typically exclude from retailer lists; you can still keep if you want them
        # (Dashboard can still filter these out.)
        # df = df[~df["chain"].str.contains(r"^total us", case=False, na=False)]

        # Add static fields
        df["brand"] = "NEOLEA"
        report_date, report_month = _parse_dates_from_name(file_path.name)
        df["report_date"] = report_date
        df["report_month"] = report_month

        # Period tag from the meta text above the header
        period = _guess_period_from_meta(raw, header_row)
        df["period"] = period

        out_rows.append(df)

        # Stop at first usable sheet (these workbooks usually duplicate the same table in a few sheets)
        break

    if not out_rows:
        return pd.DataFrame(columns=["chain","units","dollars","stores","brand","report_date","report_month","period"])

    return pd.concat(out_rows, ignore_index=True)


# ---------------------------------
# multi-file helper
# ---------------------------------
def ingest_all_singleperiod(files: List[Path]) -> pd.DataFrame:
    """
    Iterate a list of .xlsb/.xlsx files, ingest each, add a source_file column, and concat.
    """
    frames = []
    for p in files:
        try:
            df = ingest_single_period(p)
            if not df.empty:
                df["source_file"] = p.name
                frames.append(df)
            else:
                print(f"Skipped {p.name}: no usable period table found")
        except Exception as e:
            print(f"Error on {p.name}: {e}")
    if not frames:
        return pd.DataFrame(columns=["chain","units","dollars","stores","brand","report_date","report_month","period","source_file"])
    return pd.concat(frames, ignore_index=True)
def ingest_many(paths: List[Path]) -> pd.DataFrame:
    frames = []
    for p in paths:
        try:
            df = ingest_single_period(p)
        except Exception as e:
            print(f"Error reading {p.name}: {e}")
            df = pd.DataFrame()
        if len(df):
            frames.append(df)
        else:
            print(f"Skipped {p.name}: no usable table found")
    if frames:
        return pd.concat(frames, ignore_index=True)
    return pd.DataFrame()

if __name__ == "__main__":
    # Example CLI run:
    #   python -m backend.ingest
    files = sorted(DATA_DIR.glob("*.xlsb")) + sorted(DATA_DIR.glob("*.xlsx"))
    if not files:
        print("No Excel files in ./data")
    else:
        all_df = ingest_many(files)
        print(f"Ingested rows: {len(all_df)}")
        if len(all_df):
            out_csv = DATA_DIR / "neolea_spins_singleperiod.csv"
            all_df.to_csv(out_csv, index=False)
            print(f"Saved: {out_csv}")
            print(all_df.head(10).to_string(index=False))
