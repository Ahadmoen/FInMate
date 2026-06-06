import json
import os
import random
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .symbols import COMPANIES, GENERAL_QUERIES, GLOBAL_KEYWORDS
from .symbols import SYMBOLS as _ALL_SYMBOLS

_limit = int(os.environ.get("SCRAPER_LIMIT", "0") or 0)
SYMBOLS = _ALL_SYMBOLS[:_limit] if _limit > 0 else _ALL_SYMBOLS

GOOGLE_NEWS_BASE = "https://news.google.com/rss/search"
HL, GL, CEID = "en-PK", "PK", "PK:en"
USER_AGENT = "Mozilla/5.0 (compatible; Scrapping_Fyp/1.0)"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_FILE = DATA_DIR / "news_data.json"

# Throttling — Google News RSS will 429 a tight loop after a few hundred
# calls. A small sleep + exponential backoff on 429 keeps a 738-symbol
# run survivable. Tunable via env for dev runs.
NEWS_THROTTLE_SEC = float(os.environ.get("NEWS_THROTTLE_SEC", "1.2"))
NEWS_MAX_RETRIES = 2  # 5s + 10s = 15s wasted per failed symbol (was 4 = 75s)

# Circuit breaker — if Google News is wedged (every symbol gets 503),
# burning through 738 × 15s of retries before timing out is wasted
# compute. Fail fast after N consecutive symbol failures so Cloud
# Scheduler can retry the job on its next slot when the upstream
# recovers, instead of the run getting killed mid-pipeline.
CONSECUTIVE_FAIL_ABORT = int(os.environ.get("NEWS_CONSECUTIVE_FAIL_ABORT", "10"))


def build_symbol_query(symbol: str) -> str:
    info = COMPANIES.get(symbol, {})
    terms = [info.get("name", symbol), symbol, *info.get("aliases", [])]
    unique = []
    for t in terms:
        if t and t not in unique:
            unique.append(t)
    return " OR ".join(f'"{t}"' if " " in t else t for t in unique)


def fetch_feed(query: str) -> ET.Element:
    """Throttled fetch — sleeps NEWS_THROTTLE_SEC between calls and retries
    with exponential backoff on 429. Without this, a 738-symbol run gets
    rate-limited after a few hundred symbols and the rest return empty."""
    url = f"{GOOGLE_NEWS_BASE}?q={quote_plus(query)}&hl={HL}&gl={GL}&ceid={CEID}"
    if NEWS_THROTTLE_SEC > 0:
        time.sleep(NEWS_THROTTLE_SEC + random.uniform(0, 0.3))
    last_exc: Exception | None = None
    for attempt in range(NEWS_MAX_RETRIES):
        try:
            response = requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
            # Both 429 (rate-limited) and 503 (Service Unavailable) are
            # Google's "back off" signals. Retry with exponential delay
            # rather than failing the symbol outright.
            if response.status_code in (429, 503):
                wait = 2 ** attempt * 5  # 5s, 10s, 20s, 40s
                print(f"  HTTP {response.status_code} — backing off {wait}s (attempt {attempt+1}/{NEWS_MAX_RETRIES})")
                time.sleep(wait)
                continue
            response.raise_for_status()
            return ET.fromstring(response.content)
        except Exception as exc:
            last_exc = exc
            if attempt < NEWS_MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
    raise last_exc if last_exc else RuntimeError("fetch_feed: exhausted retries")


def clean_html(html: str) -> str:
    return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)


def split_sentences(text: str) -> list:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def match_keywords(text: str, keywords: list) -> tuple:
    lower = text.lower()
    hits = sorted({kw for kw in keywords if kw.lower() in lower})
    sentences = split_sentences(text)
    context = [s for s in sentences if any(kw.lower() in s.lower() for kw in hits)]
    return hits, context


def parse_pubdate(raw: str) -> str:
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return raw


# Articles older than this are dropped at the parser. Keeping just
# today / yesterday matches the 30-day Supabase retention policy and
# avoids re-ingesting articles we already scored on previous runs.
RECENT_LOOKBACK_DAYS = int(os.environ.get("NEWS_RECENT_LOOKBACK_DAYS", "2"))


def _is_recent(pub_iso: str) -> bool:
    """True if `pub_iso` (ISO-8601 string) is within RECENT_LOOKBACK_DAYS
    of now. Falls back to True if the date can't be parsed (better to
    keep an unparseable article than drop it silently)."""
    try:
        from datetime import datetime, timedelta
        dt = datetime.fromisoformat(pub_iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(days=RECENT_LOOKBACK_DAYS)
        return dt >= cutoff
    except Exception:
        return True


def parse_items(root: ET.Element) -> list:
    items = []
    dropped_old = 0
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = parse_pubdate(item.findtext("pubDate") or "")
        if not _is_recent(pub):
            dropped_old += 1
            continue
        desc = clean_html(item.findtext("description") or "")
        source_el = item.find("source")
        platform = (source_el.text or "").strip() if source_el is not None else ""
        if platform and title.endswith(f" - {platform}"):
            title = title[: -(len(platform) + 3)]
        items.append({"title": title, "link": link, "pub": pub, "desc": desc, "platform": platform})
    if dropped_old:
        print(f"  dropped {dropped_old} item(s) older than {RECENT_LOOKBACK_DAYS} day(s)")
    return items


# Pakistani / PSX context words used by `_article_matches_ticker` to
# disambiguate short ticker symbols. Two buckets:
#
#   PK_CONTEXT_SUBSTRINGS — unambiguous multi-char tokens, plain
#     substring match. "pakistan", "karachi", etc.
#   PK_CONTEXT_TOKENS — short acronyms that must hit at a word
#     boundary; otherwise plurals like "stars" match "rs " and
#     football articles pull through. Each entry is matched via
#     `\b{token}\b` so "PSX" matches "PSX" but not e.g. "PSXY".
PK_CONTEXT_SUBSTRINGS = frozenset({
    "pakistan", "pakistani", "kse-100", "kse100",
    "karachi", "lahore", "islamabad", "rawalpindi", "faisalabad",
    "rupee", "rupees",
    "state bank of pakistan", "ministry of finance",
    "monetary policy", "national bank of pakistan",
})

# Word-boundary tokens — short acronyms only.
PK_CONTEXT_TOKENS = frozenset({
    "psx", "kse", "pkr", "imf", "fbr", "sbp", "sst", "ssgc", "ogra",
})


def _has_pk_context(text_lower: str) -> bool:
    """True iff the article body contains a Pakistani-context marker.
    Substring check for unambiguous tokens; word-boundary check for
    short acronyms so 'rs ' / 'sst' don't collide with random words."""
    if any(s in text_lower for s in PK_CONTEXT_SUBSTRINGS):
        return True
    for tok in PK_CONTEXT_TOKENS:
        if re.search(rf"\b{re.escape(tok)}\b", text_lower):
            return True
    return False


_NAME_SUFFIX_RE = re.compile(r"\s+(limited|ltd\.?|co\.?|inc\.?|corp\.?)$", re.IGNORECASE)

# Generic / non-distinctive words that frequently appear in industry
# names but don't disambiguate. e.g. "Miscellaneous" or "Holding" in
# the body proves nothing about a specific ticker.
INDUSTRY_STOPWORDS = frozenset({
    "and", "the", "of", "co", "ltd", "limited", "company", "holding",
    "miscellaneous", "general", "other", "others", "group", "corp",
    "corporation", "industries", "industry", "sector",
})


def _industry_word_in_body(industry_str: str, body_lower: str) -> bool:
    """True iff any distinctive word from the ticker's industry string
    appears as a whole word in the article body.

    'PAPER, BOARD & PACKAGING' (PPP) splits into ['paper', 'board',
    'packaging']; an article must contain at least one to match the
    ticker via Tier 2. A constitutional-amendment article won't
    mention any of these — so PPP correctly rejects 'How 28th
    Amendment makes PPP kings of Pakistan's Global South'.

    Stop-words ('and', 'limited', 'group', 'sector') and short tokens
    (<4 chars) are skipped so they can't provide spurious matches.
    """
    for w in re.findall(r"[a-z]+", industry_str.lower()):
        if len(w) >= 4 and w not in INDUSTRY_STOPWORDS:
            if re.search(rf"\b{re.escape(w)}\b", body_lower):
                return True
    return False

# Industry-level keywords — articles that don't match a specific PSX
# ticker but DO talk about a whole sector get classified here. e.g.
# "Cement industry posts 12% growth" → Symbol=GENERAL, Market=Cement.
# Frontend can show these to all holders of tickers in that industry.
INDUSTRY_KEYWORDS = {
    "Cement":          ["cement industry", "cement sector", "clinker", "construction sector"],
    "Banking":         ["banking sector", "bank deposits", "bank lending", "kibor"],
    "Oil & Gas":       ["oil sector", "petroleum sector", "gas tariff", "lng", "opec"],
    "Power":           ["power sector", "electricity sector", "ipps", "circular debt", "power tariff", "k-electric tariff"],
    "Pharmaceuticals": ["pharma sector", "drap", "drug regulatory"],
    "Fertilizer":      ["fertilizer sector", "urea price", "dap price", "fertilizer subsidy"],
    "Textile":         ["textile sector", "textile exports", "cotton price", "yarn"],
    "Automobile":      ["auto sector", "car sales", "ev policy", "automobile policy"],
    "Chemicals":       ["chemical sector", "petrochemical"],
    "Food":            ["sugar price", "wheat price", "food sector", "ghee price"],
    "Insurance":       ["insurance sector", "secp announcement", "takaful"],
    "Steel":           ["steel sector", "iron ore", "scrap price"],
    "IT":              ["it sector", "tech sector", "fintech", "freelancers", "software exports", "p@sha", "psha"],
    "Agriculture":     ["agriculture sector", "agri sector", "farmer", "crop yield", "wheat production",
                        "rice exports", "kharif", "rabi", "agricultural policy"],
    # Politics is intentionally separate from Macro — political news
    # (elections, constitutional amendments, parliamentary debates)
    # affects market sentiment differently from macro-economic news
    # (petrol/dollar/IMF). Frontend can show/blend them differently.
    "Politics":        ["national assembly", "senate of pakistan", "constitutional amendment",
                        "supreme court of pakistan", "general elections", "by-election",
                        "election commission", "ecp announces", "no-confidence",
                        "prime minister announces", "cabinet decision", "ppp wins",
                        "pml-n", "pti", "imran khan", "shehbaz sharif"],
}

# Macro-level keywords — events that affect the whole market, not any
# one industry. petrol/diesel/dollar/budget/imf/inflation.
MACRO_KEYWORDS = frozenset({
    "petrol price", "diesel price", "fuel price hike", "ogra notification",
    "dollar rate", "rupee depreciation", "rupee appreciates", "rupee strengthens",
    "exchange rate", "open market rate", "interbank rate",
    "federal budget", "finance bill", "money bill",
    "imf program", "imf staff-level", "imf tranche", "world bank loan",
    "trade deficit", "current account deficit", "remittances",
    "inflation rate", "cpi", "monetary policy", "policy rate", "discount rate",
    "fbr collection", "fbr announcement", "sbp announces", "state bank announces",
    "kse-100 index", "psx index", "kse100", "psx closes", "psx opens",
})


# Sports / entertainment articles slip into Pakistani business feeds
# (Dawn, BR, ProPak all cover sport-business overlap). The article
# 'Fatima Sana Optimistic About Pakistan's Women's T20 World Cup
# Campaign' falsely matched FATIMA (Fatima Fertilizer) because:
#   - 'fatima' is in the body (Tier 2 bare-ticker hit)
#   - 'pakistan' is in the body (PK context disambiguator)
# Sports terms don't overlap with company-name semantics, so we
# discard the article BEFORE ticker matching. The keywords are chosen
# to be unambiguous — 'cricket', 'world cup', 't20 match', 'icc' have
# no business-news collision. Longer phrases like 'psl match' /
# 'psl season' avoid colliding with PSL (Pakistan Services Limited).
NON_BUSINESS_KEYWORDS = frozenset({
    # Cricket
    "cricket", "t20 world cup", "t20i", "odi series", "test match",
    "test series", "wicket", "batsman", "batter", "bowler", "icc",
    "world cup campaign", "world cup squad", "asia cup", "champions trophy",
    "psl match", "psl season", "psl 2025", "psl 2026", "ipl",
    "pakistan cricket board", "national t20",
    # Football / other sports
    "fifa", "football world cup", "uefa", "premier league",
    "olympics", "asian games", "commonwealth games",
    "kabaddi", "squash championship", "hockey world cup",
    # Entertainment / showbiz
    "bollywood", "lollywood", "hollywood", "box office",
    "film festival", "drama serial", "music video", "song release",
    "award show", "lux style awards",
    # People / lifestyle
    "actress ", "horoscope", "wedding ceremony",
})


def _is_non_business(title_lower: str, body_lower: str) -> bool:
    """True if article is sports/entertainment/lifestyle rather than
    business news. Pre-filter runs BEFORE ticker matching to suppress
    FATIMA / HABIB / ALI / KHAN false positives that arise when a
    Pakistani personal name happens to coincide with a PSX ticker."""
    for kw in NON_BUSINESS_KEYWORDS:
        if kw in title_lower or kw in body_lower:
            return True
    return False


# Mapping from noisy raw industry/market labels (PSX sector names,
# Google GENERAL_QUERIES bucket names) to the clean classifier set.
# Substring-matched in lowercase so 'COMMERCIAL BANKS' → Banking,
# 'OIL & GAS EXPLORATION' → Oil & Gas, 'World / Markets' → Macro, etc.
_RAW_INDUSTRY_MAP = [
    ("cement",         "Cement"),
    ("bank",           "Banking"),  # COMMERCIAL BANKS, INV. BANKS
    ("insurance",      "Insurance"),
    ("fertilizer",     "Fertilizer"),
    ("pharma",         "Pharmaceuticals"),
    ("oil",            "Oil & Gas"),
    ("gas",            "Oil & Gas"),
    ("petroleum",      "Oil & Gas"),
    ("power",          "Power"),
    ("electricity",    "Power"),
    ("electric",       "Power"),  # CABLE & ELECTRICAL GOODS
    ("textile",        "Textile"),
    ("automobile",     "Automobile"),
    ("auto",           "Automobile"),
    ("chemical",       "Chemicals"),
    ("food",           "Food"),
    ("steel",          "Steel"),
    ("engineering",    "Engineering"),
    ("paper",          "Paper"),
    ("packaging",      "Paper"),
    ("tech",           "IT"),
    ("technology",     "IT"),
    ("communication",  "IT"),
    ("agriculture",    "Agriculture"),
    ("agri",           "Agriculture"),
    ("politic",        "Politics"),
    ("macro",          "Macro"),
    ("world",          "Macro"),  # World / Markets → Macro
    ("commodities",    "Macro"),
    ("rates",          "Macro"),
    ("economy",        "Macro"),
    ("fiscal",         "Macro"),
    ("policy",         "Macro"),
]


def _normalize_industry(raw_market: str, title_lower: str = "", body_lower: str = "") -> str:
    """Produce a clean industry tag (Cement / Banking / IT / Politics
    / Macro / ...) regardless of what shape `raw_market` is in.

    Two-pass:
      1. Body-based classification via INDUSTRY_KEYWORDS / MACRO_KEYWORDS.
         More reliable when the article actually talks about the sector
         (e.g. an article in 'World / Markets' that's specifically about
         crude oil prices → Oil & Gas, not Macro).
      2. Fallback: substring-match the raw label against _RAW_INDUSTRY_MAP.
         Catches per-ticker rows (raw_market='PAPER, BOARD & PACKAGING'
         → Paper) and Google GENERAL_QUERIES (raw='Sector / CEMENT'
         → Cement).

    Returns '' if no classification fits — frontend can treat as 'Other'.
    """
    if body_lower or title_lower:
        result = _classify_unmatched_article(title_lower, body_lower)
        if result:
            return result[1]
    raw_lower = (raw_market or "").lower()
    for needle, clean in _RAW_INDUSTRY_MAP:
        if needle in raw_lower:
            return clean
    return ""


def _classify_unmatched_article(title_lower: str, body_lower: str) -> tuple[str, str] | None:
    """For articles that didn't match any PSX ticker, decide whether
    they're industry-level or macro-level news. Returns (Symbol, Market)
    or None if the article should be discarded.

    Industry classification beats macro — an article that talks about
    'cement industry' and 'budget' lands in Cement (more specific).
    """
    for industry, kws in INDUSTRY_KEYWORDS.items():
        for kw in kws:
            if kw in body_lower or kw in title_lower:
                return ("GENERAL", industry)
    for kw in MACRO_KEYWORDS:
        if kw in body_lower or kw in title_lower:
            return ("GENERAL", "Macro")
    return None


# PSX tickers whose lowercase form is a common English word. For these,
# the bare-ticker Tier 2 match is too noisy — "power" appears in any
# article about WAPDA / electricity / power outage; "cost" appears in
# any business article; "moon" appears in any space article. We
# disable Tier 2 entirely for these tickers and require the FULL
# multi-word company name in the title (Tier 1 only).
COMMON_WORD_TICKERS = frozenset({
    "POWER", "NEXT", "COST", "CASH", "MERIT", "PACE", "MOON", "SALT",
    "HUM", "FAST", "GAIN", "RUBY", "FRESH", "POPULAR",
    "TIGER", "LION", "KING", "ROYAL",
    "ASIA", "INDIA",
    "BANK", "GOLD", "COAL", "STEEL", "OIL",
    "DAY", "AGE", "MAY", "WAY",
    "ICE", "EYE", "ZAR", "ONE", "TWO",
})


def _article_matches_ticker(title_lower: str, body_lower: str, symbol: str) -> bool:
    """Decide whether an article should be assigned to a PSX ticker.

    BASELINE (required first): the article must contain at least one
    Pakistani-context marker (Pakistan/PSX/KSE/SBP/Rupee/...). Without
    this, a Saudi PIF article or an Indian "Dhanuka Agritech Limited"
    EPS article slips through Tier 1 (generic name substrings like
    "Systems Limited" or "Agritech Limited" exist in many countries'
    company names). Pre-2026-05-25 the matcher used PK context as a
    Tier-2 OR-fallback; now it's an AND-baseline applied first.

    Two tiers, evaluated only if baseline passes:
      1. HIGH confidence — the full multi-word company NAME (or a
         multi-word alias) appears IN THE TITLE. Article body is
         ignored for Tier 1 so an article titled 'Lucky Motors
         partners with GAC' whose body briefly mentions 'Lucky Cement'
         doesn't match LUCK — body mentions are typically about
         sibling/parent companies in the same group.

      2. MEDIUM confidence — the bare TICKER appears as a whole word
         anywhere (title or body) AND a SPECIFIC disambiguator is
         present: either (a) a distinctive industry word from
         COMPANIES[symbol].industry, or (b) a per-company keyword
         from COMPANIES[symbol].keywords.

    `title_lower` is the article title only (lowercased).
    `body_lower` is title + description combined (lowercased).
    """
    # BASELINE: Pakistani context required. Rejects Saudi/Indian/global
    # articles that happen to contain a generic-name substring (e.g.
    # 'Systems Limited' in Fujiyama Power Systems Limited).
    if not _has_pk_context(body_lower):
        return False

    info = COMPANIES.get(symbol, {})

    # Tier 1: name in TITLE only.
    # Strip trailing "Limited"/"Ltd" so news that says "Lucky Cement"
    # still matches the canonical "Lucky Cement Limited" entry.
    raw_name = (info.get("name") or "").lower()
    name = _NAME_SUFFIX_RE.sub("", raw_name).strip()
    if " " in name and name and name in title_lower:
        return True
    # Also try the raw name (with Limited suffix) — articles that DO
    # spell out the full corporate form should still match.
    if " " in raw_name and raw_name != name and raw_name in title_lower:
        return True
    for a in info.get("aliases") or []:
        a_lower = (a or "").lower()
        if " " in a_lower and a_lower in title_lower:
            return True

    # Tier 2: bare ticker + disambiguator (uses full body for recall).
    # Skip entirely for common-English-word tickers — too noisy.
    if symbol.upper() in COMMON_WORD_TICKERS:
        return False
    sym_lower = symbol.lower()
    if not re.search(rf"\b{re.escape(sym_lower)}\b", body_lower):
        return False
    # Distinctive industry-word check: 'PAPER, BOARD & PACKAGING' →
    # any of paper/board/packaging in body. Tighter than the previous
    # full-string match which never fired (no article spells out the
    # whole industry phrase verbatim).
    if _industry_word_in_body(info.get("industry") or "", body_lower):
        return True
    for kw in info.get("keywords") or []:
        kw_lower = (kw or "").lower()
        if kw_lower and kw_lower in body_lower:
            return True
    # Note: the _has_pk_context fallback was removed. Every Pakistani
    # news article mentions 'Pakistan' or PKR — using that as a Tier 2
    # disambiguator caused political articles to match PSX tickers
    # whose symbol coincided with abbreviations (PPP=political party
    # vs PPP=Pakistan Paper Products, etc.).
    return False


def fetch_external_rss(url: str, *, source_label: str) -> list:
    """Fetch a generic RSS/Atom feed (Dawn, BusinessRecorder, ProPakistani).
    No throttling needed since each fallback source is a different host
    and we only hit each one once per scraper run. Returns a list of
    {title, link, pub, desc, platform} items shaped like parse_items().
    Returns [] on any failure — the goal is best-effort fallback
    coverage, never a hard error."""
    # BusinessRecorder's edge returns 403 unless Accept advertises RSS;
    # other feeds don't care but the explicit header doesn't hurt.
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml,application/xml,text/xml,*/*",
    }
    try:
        response = requests.get(url, timeout=15, headers=headers)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        items = parse_items(root)
        for it in items:
            if not it.get("platform"):
                it["platform"] = source_label
        print(f"{source_label} fallback: {len(items)} items")
        return items
    except Exception as exc:
        print(f"{source_label} fallback: failed ({exc.__class__.__name__}: {exc})")
        return []


# Pakistani business news RSS feeds — used as fallback when Google News
# is wedged. Each returns general business/markets news that we match
# back to PSX tickers via the existing keyword-matching pipeline.
FALLBACK_FEEDS = [
    ("https://www.dawn.com/feeds/business", "Dawn"),
    ("https://www.brecorder.com/feeds/business", "BusinessRecorder"),
    ("https://propakistani.pk/category/business/feed/", "ProPakistani"),
]


def collect_fallback_articles() -> list:
    """Pull general Pakistani business news from non-Google sources.
    Three-pass classification per article:

      1. Tier 1/Tier 2 ticker match → assign to one or more tickers
         (one row per matched symbol — ENGRO + HBL article → 2 rows).
      2. If no ticker match → classify as INDUSTRY-level via
         INDUSTRY_KEYWORDS dict → row with Symbol=GENERAL, Market=Cement
         (or whichever sector). Frontend can show these to all holders
         of tickers in that industry.
      3. If no industry → check MACRO_KEYWORDS (petrol/dollar/IMF) →
         row with Symbol=GENERAL, Market=Macro.
      4. If nothing matches → discard (article isn't business-relevant)."""
    raw = []
    for url, label in FALLBACK_FEEDS:
        raw.extend(fetch_external_rss(url, source_label=label))
    if not raw:
        return []

    rows = []
    industry_hits = 0
    macro_hits = 0
    discarded = 0
    non_business = 0
    for item in raw:
        title_lower = (item.get("title") or "").lower()
        text = f"{item.get('title') or ''}. {item.get('desc') or ''}"
        body_lower = text.lower()
        # Pass 0: discard sports/entertainment BEFORE ticker matching.
        # Catches 'Fatima Sana T20 World Cup' falsely matching FATIMA
        # (Fatima Fertilizer) via Tier 2 bare-ticker + Pakistan context.
        if _is_non_business(title_lower, body_lower):
            non_business += 1
            continue
        # Pass 1: per-ticker match (Tier 1/Tier 2).
        matched = [s for s in SYMBOLS
                   if _article_matches_ticker(title_lower, body_lower, s)]
        if matched:
            for symbol in matched:
                info = COMPANIES.get(symbol, {})
                pool = sorted(set(GLOBAL_KEYWORDS + [symbol] + info.get("aliases", []) + info.get("keywords", [])))
                hits, context = match_keywords(text, pool)
                rows.append({
                    "Symbol": symbol,
                    "Date": item["pub"],
                    "Heading": item["title"],
                    "Link": item["link"],
                    "Keywords": hits,
                    "KeywordContext": context,
                    "Market": info.get("industry", ""),
                    "IndustryWise": _normalize_industry(info.get("industry", ""), title_lower, body_lower),
                    "Platform": item["platform"],
                    "Sentiment": None,
                })
            continue
        # Pass 2 + 3: industry-level or macro-level classification.
        classification = _classify_unmatched_article(title_lower, body_lower)
        if classification is None:
            discarded += 1
            continue
        sym, market = classification
        if market == "Macro":
            macro_hits += 1
        else:
            industry_hits += 1
        hits, context = match_keywords(text, GLOBAL_KEYWORDS)
        rows.append({
            "Symbol": sym,
            "Date": item["pub"],
            "Heading": item["title"],
            "Link": item["link"],
            "Keywords": hits,
            "KeywordContext": context,
            "Market": market,
            # For industry/macro classified rows the market label IS already
            # the clean industry name (Cement / Politics / Macro / ...),
            # so it's a 1:1 pass-through.
            "IndustryWise": market,
            "Platform": item["platform"],
            "Sentiment": None,
        })
    ticker_rows = len(rows) - industry_hits - macro_hits
    print(
        f"FALLBACK: {len(rows)} rows from {len(raw)} articles "
        f"(ticker:{ticker_rows} industry:{industry_hits} macro:{macro_hits} "
        f"non-business:{non_business} discarded:{discarded})"
    )
    return rows


class UpstreamWedgedError(RuntimeError):
    """Raised when the upstream news source is consistently failing —
    signals the main loop to abort early instead of retrying the
    remaining ~700 symbols against an obviously dead endpoint."""


def collect_symbol(symbol: str, *, fail_state: dict | None = None) -> list:
    info = COMPANIES.get(symbol, {})
    industry = info.get("industry", "")
    pool = sorted(set(GLOBAL_KEYWORDS + [symbol] + info.get("aliases", []) + info.get("keywords", [])))
    query = build_symbol_query(symbol)

    try:
        root = fetch_feed(query)
    except Exception as exc:
        print(f"{symbol}: fetch failed: {exc}")
        if fail_state is not None:
            fail_state["consecutive"] = fail_state.get("consecutive", 0) + 1
            if fail_state["consecutive"] >= CONSECUTIVE_FAIL_ABORT:
                raise UpstreamWedgedError(
                    f"{fail_state['consecutive']} consecutive fetch failures — "
                    f"upstream (Google News) appears wedged. Aborting run early."
                )
        return []
    if fail_state is not None:
        fail_state["consecutive"] = 0

    rows = []
    dropped = 0
    for item in parse_items(root):
        title_lower = (item.get("title") or "").lower()
        body_lower = f"{item.get('title') or ''}. {item.get('desc') or ''}".lower()
        # Post-filter Google News results through the Tier 1/Tier 2
        # match. Google returns articles matching the OR query
        # (name OR symbol OR aliases), which means short tickers like
        # "SPL" pull back "Saudi Premier League" articles. The matcher
        # rejects bare-ticker hits unless industry / PK context is also
        # present, so unrelated international news gets dropped.
        # Tier 1 only inspects the title to avoid matching articles
        # that just mention a sibling company in the body.
        if not _article_matches_ticker(title_lower, body_lower, symbol):
            dropped += 1
            continue
        text = f"{item['title']}. {item['desc']}"
        hits, context = match_keywords(text, pool)
        rows.append({
            "Symbol": symbol,
            "Date": item["pub"],
            "Heading": item["title"],
            "Link": item["link"],
            "Keywords": hits,
            "KeywordContext": context,
            "Market": industry,
            "IndustryWise": _normalize_industry(industry, title_lower, body_lower),
            "Platform": item["platform"],
            "Sentiment": None,
        })
    if dropped:
        print(f"{symbol}: {len(rows)} items  (dropped {dropped} non-PSX matches)")
    else:
        print(f"{symbol}: {len(rows)} items")
    return rows


def collect_general() -> list:
    rows = []
    for query, market in GENERAL_QUERIES:
        try:
            root = fetch_feed(query)
        except Exception as exc:
            print(f"GENERAL [{query}]: fetch failed: {exc}")
            continue
        for item in parse_items(root):
            text = f"{item['title']}. {item['desc']}"
            title_lower = (item.get("title") or "").lower()
            body_lower = text.lower()
            hits, context = match_keywords(text, GLOBAL_KEYWORDS)
            rows.append({
                "Symbol": "GENERAL",
                "Date": item["pub"],
                "Heading": item["title"],
                "Link": item["link"],
                "Keywords": hits,
                "KeywordContext": context,
                "Market": market,
                "IndustryWise": _normalize_industry(market, title_lower, body_lower),
                "Platform": item["platform"],
                "Sentiment": None,
            })
    print(f"GENERAL: {len(rows)} items")
    return rows


def load_existing(path: Path) -> list:
    if not path.exists():
        return []
    return json.loads(path.read_text())


def merge(existing: list, new: list) -> list:
    combined = existing + new
    seen = {}
    for row in combined:
        key = (row.get("Symbol"), row.get("Link") or row.get("Heading"))
        if key[1]:
            seen[key] = row
    # Prune anything older than RECENT_LOOKBACK_DAYS so news_data.json
    # doesn't grow unbounded across runs. Without this, sentiment
    # ends up rescoring tens of thousands of stale articles every day.
    rows = [r for r in seen.values() if _is_recent(r.get("Date", ""))]
    return sorted(rows, key=lambda r: r.get("Date", ""), reverse=True)


def write_json(path: Path, rows: list) -> None:
    pd.DataFrame(rows).to_json(path, orient="records", indent=2, force_ascii=False)


def main() -> None:
    import sys
    import time as _time
    from datetime import datetime as _dt
    from ml_services import mlflow_utils
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    new_rows = []
    fail_state: dict = {"consecutive": 0}
    aborted_early = False
    started = _time.time()

    with mlflow_utils.run("data_quality_v2", run_name=f"news_scraper_{int(started)}",
                          tags={"scraper": "news", "kind": "scraper_health"}):
        try:
            for symbol in SYMBOLS:
                new_rows.extend(collect_symbol(symbol, fail_state=fail_state))
            new_rows.extend(collect_general())
        except UpstreamWedgedError as exc:
            print(f"\nABORTING Google News loop: {exc}")
            aborted_early = True

        # ALWAYS run the fallback pass (Dawn / BusinessRecorder / ProPakistani).
        # They're cheap (3 HTTP calls total) and rescue the run when Google News
        # is wedged. When Google works, fallback adds extra coverage rather than
        # duplicating — keyword-matching dedups in downstream merge().
        try:
            new_rows.extend(collect_fallback_articles())
        except Exception as exc:
            print(f"fallback pass failed (non-fatal): {exc.__class__.__name__}: {exc}")

        # Per-symbol coverage + freshness stats, logged regardless of outcome.
        symbols_with_rows = {r["Symbol"] for r in new_rows if r.get("Symbol")}
        pub_dates = [r.get("Date") for r in new_rows if r.get("Date")]
        latest_pub = max(pub_dates) if pub_dates else None
        oldest_pub = min(pub_dates) if pub_dates else None

        mlflow_utils.log_params({
            "scraper": "news",
            "symbols_attempted": len(SYMBOLS),
            "max_retries": NEWS_MAX_RETRIES,
            "throttle_sec": NEWS_THROTTLE_SEC,
            "abort_threshold": CONSECUTIVE_FAIL_ABORT,
        })
        mlflow_utils.log_metrics({
            "items_fetched": len(new_rows),
            "symbols_with_news": len(symbols_with_rows),
            "symbols_without_news": max(0, len(SYMBOLS) - len(symbols_with_rows)),
            "coverage_pct": (len(symbols_with_rows) / max(1, len(SYMBOLS))) * 100,
            "duration_sec": _time.time() - started,
            "aborted_early": 1.0 if aborted_early else 0.0,
        })
        # latest_pub / oldest_pub are dates, not numbers — store as tags.
        if latest_pub:
            mlflow_utils.log_metrics({"latest_pub_epoch": float(_dt.fromisoformat(latest_pub.replace("Z", "+00:00")).timestamp())}) if False else None

    if not new_rows:
        # Exit non-zero so Cloud Run Job marks this run FAILED — without
        # that, the scheduler thinks the run succeeded and the downstream
        # ML stage runs on stale news. Better to fail loudly + retry.
        print("no items fetched — exiting with status 2 so Cloud Scheduler retries")
        sys.exit(2)

    merged = merge(load_existing(OUTPUT_FILE), new_rows)
    write_json(OUTPUT_FILE, merged)
    print(f"\nsaved {len(merged)} items -> {OUTPUT_FILE}")
    if aborted_early:
        # Google News loop circuit-broke but Dawn/BR/ProPak fallback
        # rescued at least some articles. Exit 0 so the downstream
        # sentiment + upload + ML stages run on the partial data —
        # better to keep the chain alive with less news than to fail
        # the whole pipeline. The console log + MLflow data_quality
        # run already record the partial-fetch state.
        print(f"[partial] Google News wedged; carrying on with {len(merged)} items from fallback sources")


if __name__ == "__main__":
    main()
