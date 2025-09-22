import os, re, json, hashlib
from typing import Dict, List, Optional

# Where we persist mappings (relative to project root)
PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "column_profiles.json")

DEFAULT_PATTERNS = {
    "brand":   [r"^brand$", r"^brand\s*name$", r"\bbrand\b"],
    "chain":   [r"^ret(ailer)?$", r"^banner$", r"^chain$", r"row\s*labels", r"\bret.*label", r"\bbanner", r"\bchain"],
    "units":   [r"\bunits?\b", r"\bsum\s*of\s*units?\b", r"units.*4w", r"4w.*units"],
    "dollars": [r"\bdollars?\b", r"\bsales\b", r"^\$.*", r"\bsum\s*of\s*dollars?\b", r"dollars.*4w", r"4w.*dollars"],
    "stores":  [r"^stores?$", r"\bstores\s*selling\b", r"\bnum.*stores\b", r"door.*count", r"\bdoors?\b"],
    "acv":     [r"\bacv\b", r"\bacv\s*weighted\b", r"\b%?\s*acv\b", r"tdp.*acv", r"weighted\s*dist"],
}

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())

def _match_one(colnames: List[str], patterns: List[str]) -> Optional[str]:
    for pat in patterns:
        rx = re.compile(pat, re.IGNORECASE)
        for c in colnames:
            if rx.search(c):
                return c
    return None

def _sha1_name(name: str) -> str:
    return hashlib.sha1(name.encode("utf-8")).hexdigest()

def load_profiles() -> Dict:
    if os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}

def save_profiles(profiles: Dict) -> None:
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2)

def suggest_mapping(headers: List[str]) -> Dict[str, Optional[str]]:
    cols = [_norm(h) for h in headers]
    return {
        "brand":   _match_one(cols, DEFAULT_PATTERNS["brand"]),
        "chain":   _match_one(cols, DEFAULT_PATTERNS["chain"]),
        "units":   _match_one(cols, DEFAULT_PATTERNS["units"]),
        "dollars": _match_one(cols, DEFAULT_PATTERNS["dollars"]),
        "stores":  _match_one(cols, DEFAULT_PATTERNS["stores"]),
        "acv":     _match_one(cols, DEFAULT_PATTERNS["acv"]),
    }

def profile_key(file_name: str, sheet_name: str, headers: List[str]) -> str:
    base = os.path.splitext(os.path.basename(file_name))[0]
    sig = "|".join([_norm(h) for h in headers[:30]])  # header fingerprint
    raw = f"{base}::{sheet_name}::{sig}"
    return _sha1_name(raw)

def get_saved_mapping(key: str) -> Optional[Dict[str, str]]:
    prof = load_profiles()
    return prof.get(key)

def save_mapping(key: str, mapping: Dict[str, str]) -> None:
    prof = load_profiles()
    prof[key] = mapping
    save_profiles(prof)
