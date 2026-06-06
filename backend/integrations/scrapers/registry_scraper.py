"""Monthly job: refresh symbols.py from the live PSX symbol listing.

Adds any newly listed equities to SYMBOLS/COMPANIES with auto-derived
metadata, and extends GLOBAL_KEYWORDS / GENERAL_QUERIES with sector terms
for sectors not yet represented. Existing curated entries are preserved.
"""
import re
from pathlib import Path

import pandas as pd
from psx import tickers as psx_tickers

from .symbols import COMPANIES, GENERAL_QUERIES, GLOBAL_KEYWORDS, SYMBOLS

SYMBOLS_FILE = Path(__file__).resolve().parent / "symbols.py"

# Hand-curated entries — preserved as-is on every refresh.
CURATED = {
    "SILK", "OGDC", "PPL", "LUCK", "ENGRO", "HBL", "UBL", "MCB", "NBP", "FFC",
    "HUBC", "PSO", "TRG", "SYS", "MEBL", "BAHL", "POL", "MARI", "DGKC", "NESTLE",
}

# Curated macro/general terms — rebuilt fresh on every run, then extended
# with one token-set per non-curated PSX sector.
CURATED_GLOBAL_KEYWORDS = [
    "psx", "kse-100", "kse100", "karachi stock", "pakistan stock exchange",
    "bourse", "dividend", "earnings", "profit", "loss", "revenue",
    "rupee", "inflation", "interest rate", "policy rate", "sbp", "monetary policy",
    "budget", "imf", "tax", "fiscal", "deficit", "current account",
    "gdp", "exports", "imports", "fdi",
]

CURATED_GENERAL_QUERIES = [
    ("Pakistan stock exchange", "Macro / PK Markets"),
    ("PSX KSE-100", "Macro / PK Markets"),
    ("Pakistan economy", "Macro / PK Economy"),
    ("State Bank of Pakistan", "Macro / PK Policy"),
    ("IMF Pakistan", "Macro / PK Policy"),
    ("Pakistan budget", "Macro / PK Fiscal"),
    ("crude oil price", "World / Commodities"),
    ("Fed interest rate", "World / Rates"),
    ("global markets", "World / Markets"),
    ("emerging markets", "World / Markets"),
]

SECTOR_STOPWORDS = {
    "and", "of", "the", "other", "miscellaneous",
    "inv", "cos", "co", "ltd", "etc",
}


def _tokens(text: str, stopwords: set) -> list:
    parts = re.split(r"[^a-z0-9]+", (text or "").lower())
    return [p for p in parts if p and p not in stopwords and len(p) > 2]


def _pick(row: dict, *keys: str) -> str:
    for k in keys:
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def fetch_listing() -> pd.DataFrame:
    df = psx_tickers()
    if "isETF" in df.columns:
        df = df[~df["isETF"].fillna(False).astype(bool)]
    if "isDebt" in df.columns:
        df = df[~df["isDebt"].fillna(False).astype(bool)]
    return df


def derive_entry(row: dict) -> dict:
    """Derive metadata for a non-curated symbol from the PSX listing row.

    Keywords are restricted to industry/sector terms — company-name tokens
    are intentionally NOT tokenized (matching on the full company name
    happens via the query string in news_scraper, not the keywords pool).
    """
    name = _pick(row, "name", "companyName", "fullName") or _pick(row, "symbol")
    industry = _pick(row, "sectorName", "sector", "industryName") or "Unknown"
    keywords = set(_tokens(industry, SECTOR_STOPWORDS))
    if name:
        keywords.add(name)
    return {"name": name, "aliases": [], "industry": industry, "keywords": sorted(keywords)}


def diff_and_merge(listing: pd.DataFrame) -> tuple:
    existing_symbols = list(SYMBOLS)
    existing_set = set(existing_symbols)
    # Start from curated entries only — non-curated entries get re-derived
    # from PSX on every run so fixes to derive_entry propagate.
    companies = {sym: dict(COMPANIES[sym]) for sym in CURATED if sym in COMPANIES}
    new_symbols = []
    new_sectors = set()
    refreshed = 0

    for _, row in listing.iterrows():
        sym = _pick(row.to_dict(), "symbol", "Symbol", "ticker")
        if not sym:
            continue
        if sym in CURATED:
            continue  # preserved as-is
        entry = derive_entry(row.to_dict())
        companies[sym] = entry
        if sym not in existing_set:
            new_symbols.append(sym)
            existing_set.add(sym)
        else:
            refreshed += 1
        if entry["industry"] and entry["industry"] != "Unknown":
            new_sectors.add(entry["industry"])

    # Preserve any current non-curated symbol not in the PSX listing (delisted etc.)
    for sym in existing_symbols:
        if sym not in companies and sym in COMPANIES:
            companies[sym] = dict(COMPANIES[sym])

    all_symbols = list(CURATED & set(existing_symbols))  # preserve curated order below
    all_symbols = [s for s in existing_symbols if s in CURATED]
    all_symbols += [s for s in existing_symbols if s not in CURATED]
    all_symbols += new_symbols

    curated_industries = {COMPANIES[s].get("industry", "") for s in CURATED if s in COMPANIES}
    actually_new_sectors = sorted(new_sectors - curated_industries)
    print(f"  refreshed {refreshed} existing non-curated entries")

    # Rebuild from curated baseline so previous-run pollution gets cleaned out.
    global_keywords = list(CURATED_GLOBAL_KEYWORDS)
    for sector in actually_new_sectors:
        for token in _tokens(sector, SECTOR_STOPWORDS):
            if token not in global_keywords:
                global_keywords.append(token)

    general_queries = list(CURATED_GENERAL_QUERIES)
    existing_queries = {q for q, _ in general_queries}
    query_additions = []
    for sector in actually_new_sectors:
        q = f"Pakistan {sector}"
        if q not in existing_queries:
            query_additions.append((q, f"Sector / {sector}"))
    general_queries = general_queries + query_additions

    return all_symbols, companies, global_keywords, general_queries, new_symbols, actually_new_sectors


def render_symbols_py(symbols: list, companies: dict, global_keywords: list, general_queries: list) -> str:
    lines = ["SYMBOLS = ["]
    for s in symbols:
        lines.append(f"    {s!r},")
    lines.append("]")
    lines.append("")
    lines.append("COMPANIES = {")
    for sym in symbols:
        info = companies.get(sym, {})
        lines.append(f"    {sym!r}: {{")
        lines.append(f"        \"name\": {info.get('name', '')!r},")
        lines.append(f"        \"aliases\": {info.get('aliases', [])!r},")
        lines.append(f"        \"industry\": {info.get('industry', '')!r},")
        lines.append(f"        \"keywords\": {info.get('keywords', [])!r},")
        lines.append("    },")
    lines.append("}")
    lines.append("")
    lines.append("GLOBAL_KEYWORDS = [")
    for kw in global_keywords:
        lines.append(f"    {kw!r},")
    lines.append("]")
    lines.append("")
    lines.append("GENERAL_QUERIES = [")
    for q, m in general_queries:
        lines.append(f"    ({q!r}, {m!r}),")
    lines.append("]")
    return "\n".join(lines) + "\n"


def main() -> None:
    import time as _time
    from ml_services import mlflow_utils
    started = _time.time()
    print("fetching PSX listing...")
    listing = fetch_listing()
    print(f"  {len(listing)} equities listed")

    symbols, companies, global_keywords, general_queries, new_syms, new_sectors = diff_and_merge(listing)

    with mlflow_utils.run("data_quality_v2", run_name=f"registry_scraper_{int(started)}",
                          tags={"scraper": "registry", "kind": "scraper_health"}):
        SYMBOLS_FILE.write_text(render_symbols_py(symbols, companies, global_keywords, general_queries))
        print(f"  added {len(new_syms)} new symbols: {', '.join(new_syms) if new_syms else '(none)'}")
        print(f"  sectors covered: {len(new_sectors)} non-curated")
        print(f"  rewrote {SYMBOLS_FILE}")

        mlflow_utils.log_params({
            "scraper": "registry",
            "new_symbols_added": ", ".join(new_syms) if new_syms else "(none)",
            "new_sectors": ", ".join(new_sectors) if new_sectors else "(none)",
        })
        mlflow_utils.log_metrics({
            "psx_total_listed": len(listing),
            "symbols_in_registry": len(symbols),
            "new_symbols_count": len(new_syms),
            "new_sectors_count": len(new_sectors),
            "duration_sec": _time.time() - started,
        })


if __name__ == "__main__":
    main()
