#!/usr/bin/env python3
#
# Copyright 2026 Riccardo Nevoso
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
MedSearch — Flask backend + native desktop window.
Author: Riccardo Nevoso

Searches several medical/scientific literature sources in parallel and serves a
native desktop UI (via pywebview). Results and AI text stream live via
Server-Sent Events (SSE).
"""

import sys, os, json, re, time, threading, urllib.parse, urllib.request
import urllib.error, xml.etree.ElementTree as ET
import concurrent.futures, hashlib, hmac, secrets, subprocess
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape as escape_xml
from flask import Flask, render_template, request, Response, jsonify, stream_with_context

import secrets_store

# ── resolve paths so app.py works as a script AND as a frozen build ──────────
# Two freezing tools put bundled data files (templates/, VERSION) in different
# places:
#   • PyInstaller → a temp dir exposed as sys._MEIPASS
#   • py2app      → <Bundle>.app/Contents/Resources (sys.executable is in
#                   Contents/MacOS, so Resources is ../Resources)
# When run from source they sit next to this file. RESOURCE_DIR points at
# whichever actually holds the assets.
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    # PyInstaller
    RESOURCE_DIR = Path(sys._MEIPASS)
    APP_DIR_PATH = Path(sys.executable).parent.resolve()
elif getattr(sys, "frozen", False):
    # py2app: resources live in Contents/Resources, beside Contents/MacOS
    _exe_dir = Path(sys.executable).resolve().parent          # Contents/MacOS
    _res = _exe_dir.parent / "Resources"                       # Contents/Resources
    RESOURCE_DIR = _res if (_res / "templates").exists() else _exe_dir
    APP_DIR_PATH = _exe_dir
else:
    RESOURCE_DIR = Path(__file__).parent.resolve()
    APP_DIR_PATH = RESOURCE_DIR

BASE_DIR = RESOURCE_DIR
sys.path.insert(0, str(BASE_DIR))

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"),
            static_folder=str(BASE_DIR / "static"))

# ── Request token ────────────────────────────────────────────────────────────
# The server listens on 127.0.0.1, which every web page open in the user's
# ordinary browser can also reach. Without a check, any site could POST to
# /update/apply or spend the user's Anthropic credits through /synthesis. A
# random per-launch token is rendered into our own page (other origins can't
# read it) and must accompany every request except the page itself. The token
# is also written to ~/.medsearch/server_token (0600), so that a second launch
# can find this copy and hand it its request instead of starting another.
APP_TOKEN = secrets.token_urlsafe(24)

# The installed launcher (MedSearch.app), when MedSearch was started through it:
# macOS names it in __CFBundleIdentifier. Used to restart, or to open at login,
# THROUGH the launcher, so MedSearch keeps its own name and icon. Launchers
# built before the rename carry the old identifier and are still ours.
_LAUNCHER_IDS = ("com.halbarad.medsearch", "com.riccardonevoso.medsearch")

def _launcher_bundle_id():
    bid = os.environ.get("__CFBundleIdentifier", "")
    return bid if bid.startswith(_LAUNCHER_IDS) else ""
_OPEN_PATHS = ("/", "/ping")

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG  (shared with medsearch.py logic)
# ══════════════════════════════════════════════════════════════════════════════

CONFIG_DIR  = Path.home() / ".medsearch"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "anthropic_api_key": "",
    "pubmed_api_key":    "",
    "scopus_api_key":    "",
    "scopus_insttoken":  "",
    "wos_api_key":       "",
    "unpaywall_email":   "",
    # User preference: whether AI features are active (independent of key).
    # Lets users who don't want AI turn it off even with a key present.
    "ai_enabled":        True,
    # Optional institutional proxy (EZProxy / OpenAthens). Paywalled-but-
    # subscribed papers can be opened through the user's library login.
    # institution_proxies: list of {"label","url"}; active_proxy: index into it.
    # institution_proxy (legacy single string) is migrated into the list on load.
    "institution_proxy": "",
    "institution_proxies": [],
    "active_proxy":     0,
    # Selected national guideline body (country code, e.g. "it"). Used by the
    # "National guidelines" button to open the right authority's search.
    "guideline_country": "",
    # Default source for the menu bar's quick search. One of the source keys
    # ("pubmed", "guidelines", "scopus", ...) or "all". Set from that menu.
    "default_source": "pubmed",
    # A monthly ceiling in USD for what the AI features may spend. 0 = no
    # ceiling. The hard limit belongs in the Anthropic console; this one is
    # here so the spending is visible and stops before it surprises anyone.
    "ai_monthly_cap": 0.0,
    # Mirror priority order. sci-hub.se was DNS-blocked in Jan 2026, so the
    # currently-active mirrors come first. We pass the full list to the UI so
    # users can fall through to a backup if a mirror is unreachable.
    "scihub_mirrors":    ["https://sci-hub.ru", "https://sci-hub.st", "https://sci-hub.ee"],
}

# Legacy mirror configurations we silently migrate to the current defaults
# (old saved configs would otherwise keep pointing at the dead sci-hub.se).
_LEGACY_BROKEN_MIRRORS = [
    ["https://sci-hub.se", "https://sci-hub.st", "https://sci-hub.ru"],
]

# The settings that are secrets. They live in the macOS Keychain when it is
# available (secrets_store.py); the config file then holds everything else.
# unpaywall_email is deliberately not one: it is an address, shown in full in
# Settings, and it is what identifies the caller to Unpaywall.
SECRET_KEYS = ("anthropic_api_key", "pubmed_api_key", "scopus_api_key",
               "scopus_insttoken", "wos_api_key")


def _config_for_disk(cfg, stored):
    """What gets written to config.json. A secret is blanked ONLY once the
    Keychain has confirmed it holds it: a Keychain that is present but refuses
    (a locked or missing login keychain) must not cost the user their key."""
    return {k: ("" if k in stored else v) for k, v in cfg.items()}


def load_config():
    cfg = dict(DEFAULTS)
    migrated = False
    if CONFIG_FILE.exists():
        try:
            saved = json.loads(CONFIG_FILE.read_text())
            cfg.update(saved)
            # Migrate any config that still has the dead-mirror-first order
            if cfg.get("scihub_mirrors") in _LEGACY_BROKEN_MIRRORS:
                cfg["scihub_mirrors"] = list(DEFAULTS["scihub_mirrors"])
                migrated = True
            # Migrate a legacy single institution_proxy into the new list form.
            # If it matches UniTN's known proxy, tag it with that id so it lands
            # in the predefined UniTN slot instead of appearing as a custom dup.
            legacy_proxy = (cfg.get("institution_proxy") or "").strip()
            if legacy_proxy and not cfg.get("institution_proxies"):
                if "biblio.unitn.it" in legacy_proxy:
                    cfg["institution_proxies"] = [{"id": "unitn", "label": "UniTN", "url": legacy_proxy}]
                else:
                    cfg["institution_proxies"] = [{"label": "My institution", "url": legacy_proxy}]
                cfg["active_proxy"] = 0
                migrated = True
        except Exception: pass
    # Keys come from the Keychain; a key still sitting in the file is one
    # saved by an older version, so it moves across and is wiped from the file.
    in_keychain = set()
    if secrets_store.available():
        for k in SECRET_KEYS:
            from_file = (cfg.get(k) or "").strip()
            # THE FILE WINS WHEN IT HAS A VALUE. Storing to the Keychain always
            # blanks the file, so a secret still in the file was written by a
            # version that wasn't using the Keychain, or by one that couldn't —
            # either way it is the newer of the two, and preferring the Keychain
            # here silently threw away a key the user had just entered.
            if from_file:
                if secrets_store.set(k, from_file):
                    in_keychain.add(k)
                    migrated = True
                continue
            stored = secrets_store.get(k)
            if stored:
                cfg[k] = stored
                in_keychain.add(k)
    for k, e in {"anthropic_api_key":"ANTHROPIC_API_KEY","pubmed_api_key":"NCBI_API_KEY",
                 "scopus_api_key":"SCOPUS_API_KEY","wos_api_key":"WOS_API_KEY",
                 "unpaywall_email":"UNPAYWALL_EMAIL"}.items():
        v = os.environ.get(e,"")
        if v: cfg[k] = v
    if migrated:
        # persist the fix so it doesn't keep migrating each launch
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(json.dumps(_config_for_disk(cfg, in_keychain), indent=2))
        except Exception: pass
    return cfg

def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    stored = set()
    if secrets_store.available():
        for k in SECRET_KEYS:
            if secrets_store.set(k, (cfg.get(k) or "").strip()):
                stored.add(k)
    CONFIG_FILE.write_text(json.dumps(_config_for_disk(cfg, stored), indent=2))
    # The file no longer holds keys, but it still holds where this person
    # works and what they searched for: keep it to this account.
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except Exception:
        pass

CONFIG = load_config()

TIMEOUT = 15
MAX_RESULTS_DEFAULT = 10

# ── National clinical-guideline bodies ─────────────────────────────────────
# Per-country official guideline sources. We open these in the built-in browser
# (no scraping — their sites are JS-driven and/or anti-bot protected). Where the
# site accepts a query parameter we pre-fill it with {q}; otherwise we open the
# search/landing page for the user to type into. PubMed's "Guidelines" source
# already covers anything indexed there; these catch the national PDFs that
# aren't, and give clinicians the authoritative local source directly.
NATIONAL_GUIDELINE_BODIES = {
    "it": {
        "name": "SNLG — Sistema Nazionale Linee Guida",
        "country": "Italy",
        # Dedicated SNLG portal (the old /-/snlg path on iss.it is now dead). The
        # concluded-guidelines section lists downloadable PDFs; search is on-site
        # (JS-driven), so we open the portal rather than a pre-filled query.
        "url": "https://snlg.iss.it",
        "prefill": False,
    },
    "uk": {
        "name": "NICE — National Institute for Health and Care Excellence",
        "country": "United Kingdom",
        "url": "https://www.nice.org.uk/search?q={q}",
        "prefill": True,
    },
    "us": {
        "name": "ECRI Guidelines Trust",
        "country": "United States",
        # The US National Guideline Clearinghouse closed in 2018; ECRI is the
        # de-facto successor (free account required to view full guidelines).
        "url": "https://guidelines.ecri.org/",
        "prefill": False,
    },
    "de": {
        "name": "AWMF — Leitlinienregister",
        "country": "Germany",
        "url": "https://register.awmf.org/de/suche?searchterm={q}",
        "prefill": True,
    },
    "fr": {
        "name": "HAS — Haute Autorité de Santé",
        "country": "France",
        "url": "https://www.has-sante.fr/jcms/fc_2875171/fr/recherche?text={q}",
        "prefill": True,
    },
}


# ── Auto-update configuration ──────────────────────────────────────────────
# APP_DIR_PATH is set above (frozen-aware). VERSION ships as a bundled resource,
# so read it from RESOURCE_DIR; fall back to the app dir for source checkouts.
VERSION_FILE    = RESOURCE_DIR / "VERSION"
# Raw GitHub URL for the VERSION file on the main branch
GITHUB_RAW_VERSION = "https://raw.githubusercontent.com/H4lBarAd11/MedSearch-by-RN/main/VERSION"

def get_local_version():
    try:
        return VERSION_FILE.read_text().strip()
    except Exception:
        return "Beta 0"

def _version_tuple(v):
    """
    Parse a version string into a comparable tuple, where a real release
    always sorts ABOVE any beta.

    - 'Beta 6'  → (0, 6)      (betas are pre-1.0 releases)
    - '1.0'     → (1, 0)
    - '1.2.3'   → (1, 2, 3)

    This guarantees 1.0 > Beta N for every N, so users on a beta correctly
    receive the 1.0 update (and never get prompted to 'downgrade' to a beta).
    """
    s = str(v).strip()
    nums = re.findall(r"\d+", s)
    if not nums:
        return (0,)
    # Anything labelled "beta" is a pre-release: prefix a 0 major component.
    if re.search(r"beta", s, re.IGNORECASE):
        return (0,) + tuple(int(n) for n in nums)
    return tuple(int(n) for n in nums)

LOCAL_VERSION = get_local_version()

JOURNAL_QUARTILES = {
    "nature":"Q1","science":"Q1","cell":"Q1","the lancet":"Q1","lancet":"Q1",
    "new england journal of medicine":"Q1","nejm":"Q1","jama":"Q1",
    "jama network open":"Q1","bmj":"Q1","british medical journal":"Q1",
    "annals of internal medicine":"Q1","nature medicine":"Q1",
    "nature biotechnology":"Q1","nature genetics":"Q1","nature communications":"Q1",
    "plos medicine":"Q1","plos biology":"Q1","journal of clinical oncology":"Q1",
    "circulation":"Q1","european heart journal":"Q1","gut":"Q1","hepatology":"Q1",
    "journal of allergy and clinical immunology":"Q1",
    "american journal of respiratory and critical care medicine":"Q1",
    "diabetes care":"Q1","diabetologia":"Q1","annals of oncology":"Q1",
    "journal of infectious diseases":"Q1","clinical infectious diseases":"Q1",
    "brain":"Q1","annals of neurology":"Q1","journal of neuroscience":"Q1",
    "neurosurgery":"Q1","journal of neurosurgery":"Q1","acta neurochirurgica":"Q1",
    "world neurosurgery":"Q2","neurosurgical focus":"Q2",
    "plos one":"Q2","plos genetics":"Q2","scientific reports":"Q2",
    "bmc medicine":"Q2","bmc bioinformatics":"Q2","journal of internal medicine":"Q2",
    "european journal of clinical investigation":"Q2",
    "clinical microbiology and infection":"Q2",
}

def get_quartile(j):
    return JOURNAL_QUARTILES.get((j or "").lower().strip())

# ══════════════════════════════════════════════════════════════════════════════
#  HTTP HELPERS
# ══════════════════════════════════════════════════════════════════════════════

class _RateLimiter:
    """Spaces calls to one service evenly across threads."""
    def __init__(self):
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self, per_second):
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._next)
            self._next = slot + 1.0 / per_second
        if slot > now:
            time.sleep(slot - now)

# Sources now run in parallel, and Cochrane, Guidelines, PubMed and the PMC
# lookups all hit NCBI. NCBI allows 3 requests/s without a key and 10 with one,
# and answers 429 beyond that, so every NCBI call shares one limiter.
_NCBI_LIMITER = _RateLimiter()

def _throttle(url):
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if host.endswith("ncbi.nlm.nih.gov"):
        _NCBI_LIMITER.wait(9 if CONFIG.get("pubmed_api_key") else 2.8)

def _contact_email():
    """The user's own address for polite-pool APIs (NCBI, Crossref), or None."""
    return (CONFIG.get("unpaywall_email") or "").strip() or None

def http_get(url, headers=None, timeout=TIMEOUT, error_body=False):
    """error_body=True also returns what the server said alongside an HTTP error.
    Opt-in, because most callers read a body as "it worked"; the ones that ask
    for it check the status first and use the body to say WHY it was refused."""
    req = urllib.request.Request(url, headers=headers or {
        "User-Agent": "MedSearch/1.0 (academic literature search)"})
    for attempt in (1, 2):
        _throttle(url)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace"), r.status
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 1:
                time.sleep(1.0)
                continue
            if error_body:
                try: return e.read().decode("utf-8", errors="replace"), e.code
                except Exception: pass
            return None, e.code
        except Exception:
            return None, 0
    return None, 0

def fetch_json(url, headers=None, timeout=TIMEOUT, error_body=False):
    body, status = http_get(url, headers, timeout=timeout, error_body=error_body)
    if body:
        try: return json.loads(body), status
        except Exception: pass
    return None, status

# ══════════════════════════════════════════════════════════════════════════════
#  DEDUPLICATION
# ══════════════════════════════════════════════════════════════════════════════

def _dedup_keys(doi, title):
    # DOIs are case-insensitive, and sources disagree on case (PubMed keeps the
    # publisher's capitals, Crossref lowercases), so compare them lowercased.
    keys = []
    if doi:
        keys.append("doi:" + doi.strip().lower())
    norm = re.sub(r"[^a-z0-9]", "", (title or "").lower())
    if norm:
        keys.append("title:" + norm)
    return keys

def is_duplicate(seen, doi, title):
    return any(k in seen for k in _dedup_keys(doi, title))

def register(seen, doi, title):
    seen.update(_dedup_keys(doi, title))

# ══════════════════════════════════════════════════════════════════════════════
#  ACCESS RESOLUTION
# ══════════════════════════════════════════════════════════════════════════════

def _best_oa_url(locations):
    """
    Given a list of Unpaywall oa_location dicts, pick the URL most likely to
    actually fetch as a PDF. Publisher copies (Elsevier, Wiley, Springer...)
    frequently 403 a server-side fetch even when the article is open-access,
    whereas PubMed Central and other repositories serve PDFs reliably. So we
    rank: PMC/repository PDF > any direct PDF > repository landing > any URL.
    """
    if not locations:
        return None
    # Hosts that tend to block automated PDF fetches (deprioritize these)
    blocky = ("sciencedirect", "elsevier", "wiley", "springer", "tandfonline",
              "sagepub", "nature.com", "oup.com", "academic.oup", "cell.com",
              "jamanetwork", "nejm.org", "thelancet")
    # Hosts that serve PDFs reliably (prioritize these)
    friendly = ("ncbi.nlm.nih.gov", "europepmc", "pmc", "arxiv", "biorxiv",
                "medrxiv", "ssrn", "researchgate-not", "osf.io", "zenodo",
                "doaj", "plos", "frontiersin", "mdpi", "hindawi", "biomedcentral",
                ".edu", "repository", "repec")

    def host_of(u):
        try: return (urllib.parse.urlparse(u).hostname or "").lower()
        except Exception: return ""

    def score(loc):
        pdf = loc.get("url_for_pdf")
        url = loc.get("url")
        target = pdf or url
        if not target:
            return (-999, None)
        h = host_of(target)
        s = 0
        if pdf: s += 10                                  # direct PDF beats landing
        if any(f in h for f in friendly): s += 20        # reliable host
        if any(b in h for b in blocky):   s -= 15        # likely to 403
        if loc.get("host_type") == "repository": s += 5  # repos > publishers
        if loc.get("version") == "publishedVersion": s += 1
        return (s, target)

    ranked = sorted((score(l) for l in locations), key=lambda t: t[0], reverse=True)
    for s, target in ranked:
        if target:
            return target
    return None

def check_oa(doi):
    """
    Find a free full-text URL for a DOI. Tries Unpaywall first (preferring an OA
    copy that will actually fetch — PMC/repository over publisher, which often
    403s); falls back to OpenAlex when Unpaywall can't answer. Returns URL or None.
    """
    if not doi:
        return None
    # ── Unpaywall ──────────────────────────────────────────────────────────
    email = (CONFIG.get("unpaywall_email") or "").strip()
    unpaywall_answered = False
    if email:
        data, status = fetch_json(
            f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?email={urllib.parse.quote(email)}")
        if data is not None and status == 200:
            unpaywall_answered = True
            if data.get("is_oa"):
                # Consider ALL oa locations, not just best_oa_location, so we can
                # pick a repository/PMC copy that fetches without a 403.
                locs = data.get("oa_locations") or []
                if not locs and data.get("best_oa_location"):
                    locs = [data["best_oa_location"]]
                u = _best_oa_url(locs)
                if u:
                    return u
    # ── OpenAlex fallback ──────────────────────────────────────────────────
    if not unpaywall_answered:
        data2, _ = fetch_json(f"https://api.openalex.org/works/doi:{urllib.parse.quote(doi)}")
        if data2:
            oa = data2.get("open_access") or {}
            if oa.get("oa_url"):
                return oa["oa_url"]
            best = data2.get("best_oa_location") or {}
            if best.get("pdf_url"):
                return best["pdf_url"]
            if best.get("landing_page_url"):
                return best["landing_page_url"]
            for loc in (data2.get("locations") or []):
                if loc.get("is_oa") and loc.get("pdf_url"):
                    return loc["pdf_url"]
    return None

def _pmc_pdf_url(pmcid):
    """Build the direct PMC PDF URL from a PMC id (with or without the 'PMC' prefix)."""
    if not pmcid:
        return None
    p = str(pmcid).strip()
    if not p:
        return None
    if not p.upper().startswith("PMC"):
        p = "PMC" + p
    return f"https://pmc.ncbi.nlm.nih.gov/articles/{p}/pdf/"

def pmcids_for_dois(dois):
    """
    Resolve DOIs to PubMed Central ids with ONE call to NCBI's ID Converter
    (it takes up to 200 ids at once). PMC membership means a free full text
    exists even when the publisher's copy is paywalled. Returns {doi_lower:
    pmcid}; DOIs not in PMC are absent. Fails soft to {}.
    """
    dois = [d for d in dict.fromkeys(d.strip() for d in dois if d)][:200]
    if not dois:
        return {}
    url = ("https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
           f"?ids={urllib.parse.quote(','.join(dois))}&format=json&tool=medsearch")
    if _contact_email():
        url += f"&email={urllib.parse.quote(_contact_email())}"
    # Short timeout: optional enrichment must never hold up the search.
    data, status = fetch_json(url, timeout=8)
    out = {}
    if data and status == 200:
        for rec in data.get("records") or []:
            if rec.get("pmcid") and rec.get("doi"):
                out[rec["doi"].lower()] = rec["pmcid"]
    return out

# Crossref records retraction notices (including the Retraction Watch database)
# as works that "update" the original DOI. Expressions of concern are flagged
# separately: they are a warning, not a retraction.
_RETRACTING_UPDATES = {"retraction", "withdrawal", "removal"}

def retraction_status(doi):
    """Return "retracted", "concern" or None for a DOI, via Crossref. Fails soft."""
    if not doi:
        return None
    url = (f"https://api.crossref.org/works?filter=updates:{urllib.parse.quote(doi)}"
           "&rows=20")
    if _contact_email():
        url += f"&mailto={urllib.parse.quote(_contact_email())}"
    data, status = fetch_json(url, timeout=6)
    if not data or status != 200:
        return None
    flag = None
    target = doi.lower()
    for item in (data.get("message") or {}).get("items") or []:
        for upd in item.get("update-to") or []:
            if (upd.get("DOI") or "").lower() != target:
                continue
            kind = (upd.get("type") or "").lower().replace("-", "_")
            if kind in _RETRACTING_UPDATES:
                return "retracted"
            if kind == "expression_of_concern":
                flag = "concern"
    return flag

# ── Per-DOI enrichment cache (survives restarts) ─────────────────────────────
# Open-access location, PMC id and retraction status are looked up per DOI on
# every search; caching them makes repeated and "load more" searches fast.
# Entries expire after a few days so newly-freed or newly-retracted papers show.
DOI_CACHE_FILE = CONFIG_DIR / "doi_cache.json"
_DOI_CACHE_TTL = 3 * 24 * 3600
_DOI_CACHE_MAX = 5000
_DOI_CACHE_LOCK = threading.Lock()

def _load_doi_cache():
    try:
        data = json.loads(DOI_CACHE_FILE.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

_DOI_CACHE = _load_doi_cache()

def _doi_cache_get(doi):
    with _DOI_CACHE_LOCK:
        e = _DOI_CACHE.get(doi.lower())
    if e and time.time() - e.get("t", 0) < _DOI_CACHE_TTL:
        return e
    return None

def _doi_cache_put(doi, kind, link, retraction):
    with _DOI_CACHE_LOCK:
        _DOI_CACHE[doi.lower()] = {"t": time.time(), "kind": kind,
                                   "link": link, "retraction": retraction}

def save_doi_cache():
    with _DOI_CACHE_LOCK:
        items = sorted(_DOI_CACHE.items(), key=lambda kv: kv[1].get("t", 0))
        keep = dict(items[-_DOI_CACHE_MAX:])
        _DOI_CACHE.clear()
        _DOI_CACHE.update(keep)
        text = json.dumps(keep)
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        DOI_CACHE_FILE.write_text(text)
    except Exception:
        pass

# One shared pool for the per-article lookups. Source threads submit here and
# wait; the lookups themselves never submit, so the pool cannot deadlock.
_ENRICH_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=12)

def enrich_access(articles):
    """
    Fill access_kind / access_link / retraction on each article, in parallel.
    Articles that already carry access_kind (e.g. PubMed ones with a PMC id)
    keep it but still get the retraction check. Order of preference for the
    link: Unpaywall/OpenAlex open copy → PubMed Central → the DOI itself.
    """
    todo = []
    for a in articles:
        doi = a.get("doi")
        if not doi:
            if a.get("access_kind") is None:
                a["access_kind"], a["access_link"] = "none", None
            continue
        cached = _doi_cache_get(doi)
        if cached:
            if a.get("access_kind") is None:
                a["access_kind"], a["access_link"] = cached["kind"], cached["link"]
            a["retraction"] = a.get("retraction") or cached.get("retraction")
        else:
            todo.append(a)
    if not todo:
        return articles

    need_oa = [a for a in todo if a.get("access_kind") is None]
    oa_f  = {_ENRICH_POOL.submit(check_oa, a["doi"]): a for a in need_oa}
    # PubMed records already say "Retracted Publication" themselves, and a
    # Crossref call costs ~2 s, so Crossref is asked only about papers from
    # sources that carry no retraction data (Scopus, Web of Science).
    ret_f = {_ENRICH_POOL.submit(retraction_status, a["doi"]): a for a in todo
             if not a.get("pmid")}
    for fut, a in oa_f.items():
        try: oa = fut.result()
        except Exception: oa = None
        if oa:
            a["access_kind"], a["access_link"] = "open", oa
    missing = [a for a in need_oa if a.get("access_kind") is None]
    pmc = pmcids_for_dois([a["doi"] for a in missing]) if missing else {}
    for a in missing:
        pmcid = pmc.get(a["doi"].lower())
        if pmcid:
            a["access_kind"], a["access_link"] = "open", _pmc_pdf_url(pmcid)
        else:
            a["access_kind"], a["access_link"] = "doi", f"https://doi.org/{a['doi']}"
    for fut, a in ret_f.items():
        try: flag = fut.result()
        except Exception: flag = None
        a["retraction"] = a.get("retraction") or flag
    for a in todo:
        _doi_cache_put(a["doi"], a["access_kind"], a["access_link"], a.get("retraction"))
    return articles

def scihub_links(doi):
    """Return [primary_url, ...alternates] for a DOI, or [] if no DOI."""
    if not doi: return []
    mirrors = CONFIG.get("scihub_mirrors") or DEFAULTS["scihub_mirrors"]
    return [f"{m}/{doi}" for m in mirrors]

# ══════════════════════════════════════════════════════════════════════════════
#  AI
# ══════════════════════════════════════════════════════════════════════════════

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
# The long-form work (synthesis, Explain, the assistant) uses Sonnet; the
# per-article one-liners and the suggested questions are short, high-volume
# jobs, so they use Haiku. A 7-source search makes ~70 one-liner calls.
MODEL_MAIN = "claude-sonnet-5"
MODEL_FAST = "claude-haiku-4-5"
# Sonnet 5 thinks by default. These are short reading tasks where the extra
# latency and output spend buy nothing, so it is switched off for them.
_NO_THINKING = {"thinking": {"type": "disabled"}}

# ── What the AI spends ──────────────────────────────────────────────────────
# Every Anthropic reply states how many tokens it used; these are the published
# per-million-token prices for the two models above (USD, June 2026: Sonnet 5
# $2/$10, Haiku 4.5 $1/$5). The assistant caches its context, and cached tokens
# are not billed at the input rate: writing a cache entry costs 1.25x the input
# rate, reading one 0.1x. A model we don't price is still counted, with its
# tokens recorded and no cost added — a number that is wrong is worse than one
# that is missing.
_PRICES = {                      # model -> (input $/1M, output $/1M)
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}
_CACHE_WRITE_RATE, _CACHE_READ_RATE = 1.25, 0.10
USAGE_FILE = CONFIG_DIR / "usage.json"
_USAGE_LOCK = threading.Lock()


def _this_month():
    return datetime.now().strftime("%Y-%m")


def _empty_usage():
    return {"month": _this_month(), "cost": 0.0, "input_tokens": 0,
            "output_tokens": 0, "calls": {}, "unpriced_calls": 0}


def load_usage():
    """This month's spend. A new month starts from zero; last month's total is
    not kept — this exists to answer "what is this costing me", not to be an
    accounting record."""
    try:
        data = json.loads(USAGE_FILE.read_text())
        if isinstance(data, dict) and data.get("month") == _this_month():
            return {**_empty_usage(), **data}
    except Exception:
        pass
    return _empty_usage()


def record_usage(model, feature, input_tokens, output_tokens,
                 cache_write_tokens=0, cache_read_tokens=0):
    """Add one call to this month's total. Never raises: a failure to write the
    tally must not break the feature the user asked for."""
    try:
        with _USAGE_LOCK:
            u = load_usage()
            price = _PRICES.get(model)
            if price:
                u["cost"] += (
                    (input_tokens / 1e6) * price[0]
                    + (cache_write_tokens / 1e6) * price[0] * _CACHE_WRITE_RATE
                    + (cache_read_tokens / 1e6) * price[0] * _CACHE_READ_RATE
                    + (output_tokens / 1e6) * price[1])
            else:
                u["unpriced_calls"] += 1
            u["input_tokens"] += int(input_tokens or 0) + int(cache_write_tokens or 0) + int(cache_read_tokens or 0)
            u["output_tokens"] += int(output_tokens or 0)
            u["calls"][feature] = u["calls"].get(feature, 0) + 1
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            USAGE_FILE.write_text(json.dumps(u, indent=2))
            return u
    except Exception:
        return None


def ai_cap():
    """The monthly ceiling in USD, or 0.0 for no ceiling."""
    try:
        return max(0.0, float(CONFIG.get("ai_monthly_cap") or 0))
    except Exception:
        return 0.0


def ai_over_cap():
    cap = ai_cap()
    return bool(cap) and load_usage()["cost"] >= cap


def _over_cap_message():
    return (f"This month's AI spending has reached the ${ai_cap():.2f} limit you set. "
            "Raise it in Settings, or leave it and MedSearch keeps searching without AI.")


def _anthropic_key():
    return (CONFIG.get("anthropic_api_key") or "").strip()

def ai_active():
    """AI runs only when a key exists AND the user hasn't switched AI off."""
    return bool(_anthropic_key()) and CONFIG.get("ai_enabled", True)

def _sse(obj):
    return "data: " + json.dumps(obj) + "\n\n"

def _anthropic_open(payload, timeout):
    req = urllib.request.Request(ANTHROPIC_URL, data=json.dumps(payload).encode(),
        headers={"x-api-key": _anthropic_key(), "anthropic-version": "2023-06-01",
                 "content-type": "application/json"}, method="POST")
    return urllib.request.urlopen(req, timeout=timeout)

def _api_error_text(e):
    """A plain-language message for an HTTPError from the Anthropic API."""
    try: detail = e.read().decode(errors="replace")
    except Exception: detail = ""
    msg = f"Anthropic API error {e.code}. "
    if e.code == 401:
        msg += "Your API key is invalid or expired. Re-enter it in Settings (check for typos or extra spaces)."
    elif e.code == 429:
        msg += "Rate limit reached or credits exhausted. Check your Anthropic account balance."
    elif e.code in (500, 502, 503, 529):
        msg += "The service is busy right now. Try again in a minute."
    else:
        try: msg += json.loads(detail)["error"]["message"][:200]
        except Exception: msg += detail[:200]
    return msg

def claude_text(payload, timeout=30, feature="other"):
    """One non-streaming call; returns the reply text. Raises RuntimeError."""
    if not _anthropic_key():
        raise RuntimeError("No Anthropic API key set.")
    if ai_over_cap():
        raise RuntimeError(_over_cap_message())
    try:
        with _anthropic_open(payload, timeout) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(_api_error_text(e))
    except Exception as e:
        raise RuntimeError(f"Anthropic request failed: {e}")
    usage = data.get("usage") or {}
    record_usage(payload.get("model"), feature,
                 usage.get("input_tokens", 0), usage.get("output_tokens", 0),
                 usage.get("cache_creation_input_tokens", 0),
                 usage.get("cache_read_input_tokens", 0))
    if data.get("stop_reason") == "refusal":
        raise RuntimeError("The model declined this request.")
    return "".join(b.get("text", "") for b in data.get("content", [])
                   if b.get("type") == "text").strip()

def claude_stream(payload, timeout=120, feature="other"):
    """
    Stream one call as our own SSE events: {"type":"chunk"} per text delta,
    {"type":"error"} on failure, and always a final {"type":"done"}.
    """
    if not _anthropic_key():
        yield _sse({"type": "error", "text": "No API key set. Add your Anthropic key in Settings."})
        yield _sse({"type": "done"})
        return
    if not CONFIG.get("ai_enabled", True):
        yield _sse({"type": "error", "text": "AI features are turned off. Turn them on with AI on/off in the bottom bar."})
        yield _sse({"type": "done"})
        return
    if ai_over_cap():
        yield _sse({"type": "error", "text": _over_cap_message()})
        yield _sse({"type": "done"})
        return
    payload = dict(payload, stream=True)
    # The tokens are reported in two places: the input count when the message
    # starts, the output count as it ends.
    used_in = used_out = used_cache_write = used_cache_read = 0
    try:
        with _anthropic_open(payload, timeout) as r:
            for raw in r:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                try: ev = json.loads(line[5:].strip())
                except Exception: continue
                kind = ev.get("type")
                if kind == "message_start":
                    u0 = ((ev.get("message") or {}).get("usage") or {})
                    used_in = u0.get("input_tokens", 0)
                    used_cache_write = u0.get("cache_creation_input_tokens", 0)
                    used_cache_read = u0.get("cache_read_input_tokens", 0)
                elif kind == "message_delta":
                    used_out = (ev.get("usage") or {}).get("output_tokens", used_out)
                if kind == "content_block_delta":
                    delta = ev.get("delta") or {}
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        yield _sse({"type": "chunk", "text": delta["text"]})
                elif kind == "message_delta":
                    if (ev.get("delta") or {}).get("stop_reason") == "refusal":
                        yield _sse({"type": "error", "text": "The model declined this request."})
                elif kind == "error":
                    msg = (ev.get("error") or {}).get("message") or "The AI service reported an error."
                    yield _sse({"type": "error", "text": msg})
                    break
    except urllib.error.HTTPError as e:
        yield _sse({"type": "error", "text": _api_error_text(e)})
    except Exception as e:
        yield _sse({"type": "error", "text": f"Request failed: {e}"})
    if used_in or used_out or used_cache_read or used_cache_write:
        record_usage(payload.get("model"), feature, used_in, used_out,
                     used_cache_write, used_cache_read)
    yield _sse({"type": "done"})

def ai_oneliner(title, abstract):
    if not ai_active() or not abstract:
        return None
    prompt = (f"Title: {title}\n\nAbstract: {abstract}\n\n"
              "In exactly one sentence (≤25 words), state the key finding. No preamble.")
    try:
        return claude_text({"model": MODEL_FAST, "max_tokens": 80,
                            "messages": [{"role": "user", "content": prompt}]},
                           feature="summaries") or None
    except Exception:
        # one-liners fail silently (don't spam errors per article); synthesis surfaces them
        return None

def ai_synthesis_stream(query, articles):
    """Generator that yields SSE chunks for the synthesis."""
    if not articles:
        yield _sse({"type": "error", "text": "No articles."})
        yield _sse({"type": "done"})
        return
    parts = []
    for i, a in enumerate(articles, 1):
        ol = f" → {a['oneliner']}" if a.get("oneliner") else ""
        flag = " [RETRACTED]" if a.get("retraction") == "retracted" else ""
        parts.append(f"[{i}] {a['title']}{flag} ({a['year']}, {a['source']})\n"
                     f"    Authors: {a.get('authors','Unknown')}{ol}\n"
                     f"    Abstract: {(a.get('abstract') or '')[:400]}")
    prompt = (f'Literature search query: "{query}"\n\n'
              f"{len(articles)} articles:\n\n" + "\n\n".join(parts) + "\n\n"
              "Write a comprehensive academic synthesis (3–5 paragraphs). Cover: state of evidence, "
              "key findings, consensus, controversies/gaps, clinical implications. "
              "Reference articles by [number]. Do not rely on any article marked [RETRACTED]; "
              "if one is relevant, say that it was retracted.")
    yield from claude_stream({"model": MODEL_MAIN, "max_tokens": 2000, **_NO_THINKING,
                              "messages": [{"role": "user", "content": prompt}]},
                             timeout=120, feature="syntheses")

def ai_explain_stream(article):
    note = ("\nNOTE: this paper has been RETRACTED. Say so first, and treat its findings accordingly.\n"
            if article.get("retraction") == "retracted" else "")
    prompt = (f"Title: {article['title']}\nAuthors: {article.get('authors','Unknown')}\n"
              f"Year: {article.get('year','n.d.')}\nAbstract: {article.get('abstract') or 'No abstract.'}\n"
              f"{note}\n"
              "Explain this paper for a medical professional. Cover:\n"
              "1. Research question and why it matters\n2. Methodology\n"
              "3. Main findings\n4. Limitations and biases\n5. Clinical implications")
    yield from claude_stream({"model": MODEL_MAIN, "max_tokens": 1500, **_NO_THINKING,
                              "messages": [{"role": "user", "content": prompt}]},
                             timeout=120, feature="explanations")

# ══════════════════════════════════════════════════════════════════════════════
#  AI ASSISTANT  (content-aware clinical chat, grounded in current results)
# ══════════════════════════════════════════════════════════════════════════════

def _articles_context(articles, limit=80, abstract_chars=200):
    """Build a compact text digest of the current results for grounding.

    Every loaded result is listed (up to `limit`) so the assistant can answer
    "which of these…" about the whole list, not just the first page. Each
    line is title + one-liner; the abstract excerpt is only a fallback when no
    one-liner exists. The block is prompt-cached, so later turns in the same
    conversation read it at a fraction of the cost.
    """
    if not articles:
        return "(No search results are currently loaded.)"
    parts = []
    for i, a in enumerate(articles[:limit], 1):
        line = f"[{i}] {a.get('title','')} ({a.get('year','n.d.')}, {a.get('journal','')})"
        if a.get("pub_types"):
            line += f" — {', '.join(a['pub_types'])}"
        if a.get("retraction") == "retracted":
            line += " — RETRACTED"
        if a.get("oneliner"):
            line += f"\n    → {a['oneliner']}"
        elif abstract_chars > 0 and a.get("abstract"):
            line += f"\n    Abstract: {(a.get('abstract') or '')[:abstract_chars]}"
        parts.append(line)
    extra = f"\n\n(+{len(articles)-limit} more results not shown)" if len(articles) > limit else ""
    return "\n\n".join(parts) + extra

ASSISTANT_SYSTEM = (
    "You are a clinical research assistant inside MedSearch, a medical literature "
    "search tool used by physicians and researchers. You help interpret evidence, "
    "answer clinical and scientific questions, and suggest directions for further "
    "inquiry.\n\n"
    "When the user's current search results are provided, ground your answers in "
    "them and cite specific papers by their bracket number, e.g. [3]. If you need "
    "the full abstract of a specific paper to answer well, tell the user to click "
    "'Explain' on that card. If the results don't contain the answer, say so "
    "plainly and answer from general medical knowledge, making clear you're doing so.\n\n"
    "Be accurate, concise, and appropriately cautious. Default to 2-4 short "
    "paragraphs; expand only if asked. Note important uncertainties or "
    "contraindications. You are an aid to clinical reasoning, not a substitute for "
    "professional judgment; do not give individualized treatment directives for "
    "specific patients."
)

def assistant_chat_stream(messages, query, articles):
    """Stream a chat completion grounded in current results. `messages` is the
    running conversation [{role, content}, ...] from the client.

    The article context sits in its own cached system block, so subsequent
    turns in the same conversation pay ~10x less for it.
    """
    context = _articles_context(articles)
    system_blocks = [
        {"type": "text", "text": ASSISTANT_SYSTEM},
        {"type": "text",
         "text": f"=== CURRENT SEARCH ===\nQuery: {query or '(none)'}\nResults currently loaded:\n{context}",
         "cache_control": {"type": "ephemeral"}},
    ]
    yield from claude_stream({"model": MODEL_MAIN, "max_tokens": 1024, **_NO_THINKING,
                              "system": system_blocks, "messages": messages},
                             timeout=120, feature="questions")

def assistant_suggestions(query, articles):
    """Generate 3-4 short follow-up questions based on the current search."""
    if not ai_active() or not query:
        return []
    context = _articles_context(articles, limit=8, abstract_chars=0)
    prompt = (
        f'A clinician searched for: "{query}"\n\n'
        f"These results are loaded:\n{context}\n\n"
        "Suggest exactly 4 concise follow-up questions the clinician might want to "
        "ask about this evidence (comparisons, mechanisms, dosing, contraindications, "
        "gaps, guidelines, etc.). Each question ≤12 words, specific to this topic. "
        "Respond ONLY with a JSON array of 4 strings, nothing else."
    )
    try:
        text = claude_text({"model": MODEL_FAST, "max_tokens": 250,
                            "messages": [{"role": "user", "content": prompt}]},
                           feature="suggestions")
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        arr = json.loads(text)
        if isinstance(arr, list):
            return [str(q).strip() for q in arr if str(q).strip()][:4]
    except Exception:
        pass
    return []

# ══════════════════════════════════════════════════════════════════════════════
#  MESH
# ══════════════════════════════════════════════════════════════════════════════

def get_mesh(query):
    suggestions = []
    # ESpell only answers in XML (a retmode=json request still gets XML back),
    # so it is parsed as XML. Only offered when it actually changes the query.
    body, _ = http_get(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/espell.fcgi"
                       f"?db=pubmed&term={urllib.parse.quote(query)}", timeout=8)
    if body:
        try:
            corrected = (ET.fromstring(body).findtext("CorrectedQuery") or "").strip()
            if corrected and corrected.lower() != query.lower():
                suggestions.append({"type": "spelling", "text": corrected})
        except Exception:
            pass
    mesh_data, _ = fetch_json(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
                               f"?db=mesh&term={urllib.parse.quote(query)}&retmax=5&retmode=json")
    ids = ((mesh_data or {}).get("esearchresult") or {}).get("idlist") or []
    if ids:
        # efetch on db=mesh only returns plain text, so the headings are read
        # from esummary's JSON instead (first entry of ds_meshterms).
        summ, _ = fetch_json(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                             f"?db=mesh&id={','.join(ids[:5])}&retmode=json")
        res = (summ or {}).get("result") or {}
        for uid in res.get("uids") or []:
            terms = (res.get(uid) or {}).get("ds_meshterms") or []
            if terms:
                suggestions.append({"type": "mesh", "text": terms[0]})
    return suggestions

# ══════════════════════════════════════════════════════════════════════════════
#  CITATION GRAPH  (OpenCitations COCI API + Crossref title resolution)
# ══════════════════════════════════════════════════════════════════════════════

def _crossref_meta(doi):
    """Resolve a DOI to {title, year, authors} via Crossref. Returns None on failure."""
    if not doi: return None
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi)}"
    ua = "MedSearch/1.0" + (f" (mailto:{_contact_email()})" if _contact_email() else "")
    data, status = fetch_json(url, headers={"User-Agent": ua})
    if not data or status != 200:
        return None
    msg = data.get("message", {})
    title_list = msg.get("title", [])
    title = title_list[0] if title_list else "(title unavailable)"
    # Year
    year = ""
    for key in ("published-print","published-online","issued","created"):
        parts = msg.get(key, {}).get("date-parts", [[]])
        if parts and parts[0]:
            year = str(parts[0][0]); break
    # Authors (first 2)
    authors = []
    for a in msg.get("author", [])[:2]:
        fam = a.get("family",""); given = a.get("given","")
        if fam:
            authors.append(f"{fam}{' '+given[0]+'.' if given else ''}")
    n = len(msg.get("author", []))
    author_str = "; ".join(authors) + (" et al." if n > 2 else "")
    journal = (msg.get("container-title") or [""])[0]
    return {"doi": doi, "title": title, "year": year,
            "authors": author_str, "journal": journal}

def _resolve_dois(dois, limit=12):
    """Resolve up to `limit` DOIs to metadata, in parallel for speed."""
    dois = [d for d in dois if d][:limit]
    out = []
    if not dois: return out
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(_crossref_meta, d): d for d in dois}
        for fut in concurrent.futures.as_completed(futures):
            try:
                meta = fut.result()
                if meta: out.append(meta)
            except Exception:
                pass
    return out

def _doi_from_ids(field):
    """OpenCitations v2 lists every id of a work in one string
    ("omid:br/06… doi:10.1/x pmid:123"); return the DOI part, or ""."""
    for tok in (field or "").split():
        if tok.startswith("doi:"):
            return tok[4:]
    return ""

def get_citation_graph(doi, cap=12):
    """
    Returns {references:[...], citations:[...], counts:{...}} for a DOI.
    references = works this paper cites; citations = works citing this paper.
    Titles resolved via Crossref (capped for speed).
    """
    # The v1 COCI API now only redirects; v2 is the live index.
    base = "https://api.opencitations.net/index/v2"
    result = {"references": [], "citations": [],
              "ref_total": 0, "cit_total": 0, "doi": doi}
    if not doi:
        return result
    headers = {"User-Agent": "MedSearch/1.0"}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        ref_f = ex.submit(fetch_json, f"{base}/references/doi:{urllib.parse.quote(doi)}", headers, 20)
        cit_f = ex.submit(fetch_json, f"{base}/citations/doi:{urllib.parse.quote(doi)}", headers, 20)
        ref_data, _ = ref_f.result()
        cit_data, _ = cit_f.result()

    ref_dois, cit_dois = [], []
    if isinstance(ref_data, list):
        result["ref_total"] = len(ref_data)
        ref_dois = [d for d in (_doi_from_ids(r.get("cited")) for r in ref_data) if d]
    if isinstance(cit_data, list):
        result["cit_total"] = len(cit_data)
        cit_dois = [d for d in (_doi_from_ids(r.get("citing")) for r in cit_data) if d]

    result["references"] = _resolve_dois(ref_dois, limit=cap)
    result["citations"]  = _resolve_dois(cit_dois, limit=cap)
    return result

# ══════════════════════════════════════════════════════════════════════════════
#  SEARCH FUNCTIONS  (return list of article dicts, no printing)
# ══════════════════════════════════════════════════════════════════════════════

def within_range(year_str, y_from, y_to):
    if not y_from and not y_to: return True
    try:
        y = int(str(year_str)[:4])
        if y_from and y < y_from: return False
        if y_to   and y > y_to:   return False
        return True
    except Exception: return True

def _pubmed_year(art_el):
    """Extract a 4-digit year from PubDate, handling <Year> and <MedlineDate>."""
    pd = art_el.find(".//Journal/JournalIssue/PubDate")
    if pd is None:
        return "n.d."
    y = pd.find("Year")
    if y is not None and y.text:
        return y.text
    md = pd.find("MedlineDate")   # e.g. "2020 Jan-Feb" or "1998-1999"
    if md is not None and md.text:
        m = re.search(r"\d{4}", md.text)
        if m: return m.group(0)
    return "n.d."

# Detect whether the user typed a "power query" (operators / field tags / quotes)
_PM_OPERATOR_RE = re.compile(r'\b(AND|OR|NOT)\b')          # Boolean operators (uppercase)
_PM_FIELDTAG_RE = re.compile(r'\[[a-zA-Z/ ]+\]')           # field tags like [tiab], [mesh], [au]
def is_power_query(q):
    """True if the query uses Boolean operators, field tags, or quoted phrases."""
    if _PM_OPERATOR_RE.search(q): return True
    if _PM_FIELDTAG_RE.search(q): return True
    if '"' in q: return True
    return False

def build_pubmed_term(query, strict=True):
    """
    Power query (operators/tags/quotes) → pass through verbatim, always.
        The user has taken explicit control; the strict flag is ignored.
    Strict (default) → AND the words together, each tagged [tiab] (title/abstract),
        so results are papers actually ABOUT the terms — not tangential MeSH-tree
        matches. e.g. 'glioblastoma temozolomide resistance'
                   → glioblastoma[tiab] AND temozolomide[tiab] AND resistance[tiab]
    Broad (opt-in) → bare terms; PubMed's Automatic Term Mapping expands to MeSH +
        synonyms (the pubmed.gov default). Wider recall, more drift.
    """
    q = query.strip()
    if is_power_query(q):
        return q
    if not strict:
        return q   # broad: let ATM expand freely
    # Strict: split into words, tag each [tiab], AND them.
    # Keep short multi-word as-is if only one token.
    words = [w for w in re.split(r'\s+', q) if w]
    if len(words) <= 1:
        return f"{q}[tiab]" if q else q
    return " AND ".join(f"{w}[tiab]" for w in words)

# PubMed publication types worth showing on a card, strongest evidence first.
# Everything else PubMed lists ("Journal Article", "Research Support, …") is
# noise for a clinician scanning results.
_PUB_TYPE_BADGES = [
    ("Meta-Analysis",                 "Meta-analysis"),
    ("Systematic Review",             "Systematic review"),
    ("Practice Guideline",            "Guideline"),
    ("Guideline",                     "Guideline"),
    ("Randomized Controlled Trial",   "RCT"),
    ("Clinical Trial, Phase IV",      "Clinical trial"),
    ("Clinical Trial, Phase III",     "Clinical trial"),
    ("Clinical Trial, Phase II",      "Clinical trial"),
    ("Clinical Trial, Phase I",       "Clinical trial"),
    ("Controlled Clinical Trial",     "Clinical trial"),
    ("Clinical Trial",                "Clinical trial"),
    ("Observational Study",           "Observational"),
    ("Review",                        "Review"),
    ("Case Reports",                  "Case report"),
    ("Preprint",                      "Preprint"),
]

def _pub_type_badges(raw_types):
    raw = set(raw_types)
    out = []
    for name, badge in _PUB_TYPE_BADGES:
        if name in raw and badge not in out:
            out.append(badge)
    return out

def _article(**fields):
    """One result, with every key the UI and the exporters rely on."""
    a = {"title": "No title", "authors": "", "author_list": [], "year": "n.d.",
         "journal": "", "quartile": None, "doi": None, "pmid": None,
         "abstract": "", "source": "", "access_kind": None, "access_link": None,
         "scihub": None, "oneliner": None, "pub_types": [], "retraction": None}
    a.update(fields)
    if a["doi"] and not a["scihub"]:
        a["scihub"] = scihub_links(a["doi"])
    if a["journal"] and a["quartile"] is None:
        a["quartile"] = get_quartile(a["journal"])
    return a

def _short_authors(names, n=3):
    return "; ".join(names[:n]) + (" et al." if len(names) > n else "")

def search_pubmed(query, max_r, y_from, y_to, strict=True, extra_filter=None,
                  source_label="PubMed", sort="relevance", offset=0):
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    kp   = f"&api_key={CONFIG['pubmed_api_key']}" if CONFIG.get("pubmed_api_key") else ""
    dp   = (f"&mindate={y_from or 1900}/01/01&maxdate={y_to or 2099}/12/31&datetype=pdat"
            if y_from or y_to else "")
    term = build_pubmed_term(query, strict=strict)
    if extra_filter:
        term = f"({term}) AND {extra_filter}"
    # sort=relevance → PubMed "Best Match"; sort=date → most recent first
    sort_param = "date" if sort == "date" else "relevance"
    data, _ = fetch_json(f"{base}/esearch.fcgi?db=pubmed&term={urllib.parse.quote(term)}"
                         f"&retstart={offset}&retmax={max_r}&sort={sort_param}&retmode=json{kp}{dp}")
    if not data:
        raise RuntimeError(f"{source_label} didn't respond. Check your connection and try again.")
    ids   = data.get("esearchresult", {}).get("idlist", [])
    total = int(data.get("esearchresult", {}).get("count", 0))
    if not ids:
        return [], total

    body, _ = http_get(f"{base}/efetch.fcgi?db=pubmed&id={','.join(ids)}&retmode=xml{kp}")
    if not body:
        raise RuntimeError(f"{source_label} returned no records. Try again in a moment.")
    try:
        root = ET.fromstring(body)
    except Exception:
        raise RuntimeError(f"{source_label} sent a response that couldn't be read.")

    # Preserve the relevance order returned by esearch
    by_pmid = {}
    for art in root.findall(".//PubmedArticle"):
        pmid_el = art.find(".//MedlineCitation/PMID")
        if pmid_el is not None and pmid_el.text:
            by_pmid[pmid_el.text] = art

    results = []
    for pmid in ids:
        art = by_pmid.get(pmid)
        med = art.find(".//MedlineCitation") if art is not None else None
        art_el = med.find("Article") if med is not None else None
        if art_el is None:
            continue

        title_el = art_el.find("ArticleTitle")
        title = ("".join(title_el.itertext()).strip() if title_el is not None else "") or "No title"
        journal = art_el.findtext(".//Journal/Title") or ""
        year = _pubmed_year(art_el)
        if not within_range(year, y_from, y_to):
            continue

        names = []
        for au in art_el.findall(".//AuthorList/Author"):
            last, fore = au.findtext("LastName"), au.findtext("ForeName")
            if last:
                names.append(f"{last}, {fore}" if fore else last)
            elif au.findtext("CollectiveName"):
                names.append(au.findtext("CollectiveName"))
        short = []
        for au in art_el.findall(".//AuthorList/Author")[:3]:
            last, fore = au.findtext("LastName"), au.findtext("ForeName")
            if last:
                short.append(f"{last}, {fore[0]}." if fore else last)
        authors = "; ".join(short) + (" et al." if len(names) > 3 else "")

        doi   = next((a.text for a in art.findall(".//PubmedData/ArticleIdList/ArticleId")
                      if a.get("IdType") == "doi"), None)
        pmcid = next((a.text for a in art.findall(".//PubmedData/ArticleIdList/ArticleId")
                      if a.get("IdType") == "pmc"), None)

        # Abstract may have multiple labelled sections — join them all
        chunks = []
        for ap in art_el.findall(".//Abstract/AbstractText"):
            label, txt = ap.get("Label"), "".join(ap.itertext())
            chunks.append(f"{label}: {txt}" if label else txt)

        raw_types = [pt.text or "" for pt in art_el.findall(".//PublicationTypeList/PublicationType")]
        retraction = "retracted" if "Retracted Publication" in raw_types else None
        if not retraction and any(c.get("RefType") == "ExpressionOfConcernIn"
                                  for c in med.findall(".//CommentsCorrectionsList/CommentsCorrections")):
            retraction = "concern"

        a = _article(title=title, authors=authors, author_list=names, year=year,
                     journal=journal, doi=doi, pmid=pmid,
                     abstract=" ".join(chunks).strip(), source=source_label,
                     pub_types=_pub_type_badges(raw_types), retraction=retraction)
        # A PMC id in the record means the full text is free in PubMed Central:
        # link its PDF directly, with no extra lookup.
        if pmcid:
            a["access_kind"], a["access_link"] = "open", _pmc_pdf_url(pmcid)
        results.append(a)
    return enrich_access(results), total

def search_cochrane(query, max_r, y_from, y_to, strict=True, sort="relevance", offset=0):
    """
    Cochrane systematic reviews are indexed in PubMed under the journal
    'Cochrane Database of Systematic Reviews'. We search PubMed restricted to
    that journal, giving real inline results instead of a dead external link.
    """
    # [ta] = journal title abbreviation field; covers the current journal name.
    return search_pubmed(query, max_r, y_from, y_to, strict=strict,
                         extra_filter='"Cochrane Database Syst Rev"[ta]',
                         source_label="Cochrane", sort=sort, offset=offset)

def search_guidelines(query, max_r, y_from, y_to, strict=True, sort="relevance", offset=0):
    # Clinical practice guidelines: PubMed restricted to guideline publication
    # types. Captures national/society guidelines from many countries.
    return search_pubmed(query, max_r, y_from, y_to, strict=strict,
                         extra_filter='(Guideline[ptyp] OR "Practice Guideline"[ptyp])',
                         source_label="Guidelines", sort=sort, offset=offset)

def search_arxiv(query, max_r, y_from, y_to, sort="relevance", offset=0):
    # sortBy=relevance ↔ submittedDate (most recent first)
    sort_by = "submittedDate" if sort == "date" else "relevance"
    body, _ = http_get(f"https://export.arxiv.org/api/query?search_query=all:"
                       f"{urllib.parse.quote(query)}&start={offset}&max_results={max_r}"
                       f"&sortBy={sort_by}&sortOrder=descending", timeout=20)
    if not body:
        raise RuntimeError("arXiv didn't respond. Try again in a moment.")
    ns = {"a": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(body)
    except Exception:
        raise RuntimeError("arXiv sent a response that couldn't be read.")
    results = []
    for e in root.findall("a:entry", ns):
        # One malformed entry must not cost the whole source.
        try:
            year  = (e.findtext("a:published", "", ns) or "")[:4] or "n.d."
            if not within_range(year, y_from, y_to):
                continue
            title = " ".join((e.findtext("a:title", "", ns) or "").split()) or "No title"
            names = [n for n in (a.findtext("a:name", "", ns).strip()
                                 for a in e.findall("a:author", ns)) if n]
            arxiv_id = (e.findtext("a:id", "", ns) or "").strip()
            results.append(_article(
                title=title, authors=_short_authors(names), author_list=names,
                year=year, journal="arXiv",
                abstract=(e.findtext("a:summary", "", ns) or "").strip(),
                source="arXiv", access_kind="open" if arxiv_id else "none",
                access_link=arxiv_id.replace("/abs/", "/pdf/") or None,
                pub_types=["Preprint"]))
        except Exception:
            continue
    return results, 0

def search_clinicaltrials(query, max_r, y_from, y_to, sort="relevance", offset=0):
    # ClinicalTrials v2: default ordering is relevance; LastUpdatePostDate:desc
    # gives most-recently-updated first.
    sort_p = "&sort=LastUpdatePostDate%3Adesc" if sort == "date" else ""
    # The v2 API paginates by opaque token, not numeric offset, so for "load
    # more" we over-fetch (offset+max_r, max 1000) and skip the first `offset`.
    data, status = fetch_json(f"https://clinicaltrials.gov/api/v2/studies"
                              f"?query.term={urllib.parse.quote(query)}"
                              f"&pageSize={min(max_r + offset, 1000)}&format=json{sort_p}")
    if not data:
        raise RuntimeError(f"ClinicalTrials.gov didn't respond (HTTP {status or 'no answer'}).")
    results = []
    for study in (data.get("studies") or [])[offset:]:
        proto  = study.get("protocolSection", {})
        id_mod = proto.get("identificationModule", {})
        sm     = proto.get("statusModule", {})
        phases = proto.get("designModule", {}).get("phases", ["N/A"])
        phase  = ", ".join(phases) if isinstance(phases, list) else str(phases)
        nct    = id_mod.get("nctId", "N/A")
        start  = sm.get("startDateStruct", {}).get("date", "")
        year   = start[:4] if start else "n.d."
        if not within_range(year, y_from, y_to):
            continue
        results.append(_article(
            title=id_mod.get("briefTitle", "No title"), authors="ClinicalTrials.gov",
            year=year, journal=f"Phase: {phase} | Status: {sm.get('overallStatus', 'Unknown')}",
            nct_id=nct, abstract=proto.get("descriptionModule", {}).get("briefSummary", ""),
            source="ClinicalTrials", access_kind="open",
            access_link=f"https://clinicaltrials.gov/study/{nct}",
            pub_types=["Registered trial"]))
    return results, 0

# NOTE: medRxiv/bioRxiv were removed — their official API has no keyword-search
# endpoint (only date-range or DOI fetch), and the PMC-based workaround simply
# duplicated PubMed results via dedup. arXiv stays (it has a real search API).

def search_scopus(query, max_r, y_from, y_to, sort="relevance", offset=0):
    key = (CONFIG.get("scopus_api_key","") or "").strip()
    if not key:
        raise RuntimeError("No Scopus API key set.")
    dr = (f" AND PUBYEAR > {(y_from or 1900)-1} AND PUBYEAR < {(y_to or 2099)+1}"
          if y_from or y_to else "")
    # Scopus authenticates by API key PLUS institutional IP range. From off-campus
    # an institutional token (X-ELS-Insttoken) is also required — send it if set.
    headers = {"X-ELS-APIKey": key, "Accept": "application/json"}
    insttoken = (CONFIG.get("scopus_insttoken","") or "").strip()
    if insttoken:
        headers["X-ELS-Insttoken"] = insttoken
    # sort=relevancy ↔ -coverDate (minus prefix = descending → newest first)
    sort_p = "&sort=-coverDate" if sort == "date" else "&sort=relevancy"
    url = (f"https://api.elsevier.com/content/search/scopus"
           f"?query={urllib.parse.quote(query+dr)}&start={offset}&count={max_r}{sort_p}")
    data, status = fetch_json(url, headers=headers, error_body=True)
    if status != 200:
        # Surface a clear, actionable error instead of failing silently
        if status == 401:
            # A 401 has two unrelated causes and Elsevier says which: a key it does
            # not know (APIKEY_INVALID), or a good key used from outside the
            # subscriber's network. Sending someone to the VPN over a mistyped key
            # costs them an afternoon.
            err = (data or {}).get("error-response") or {}
            if err.get("error-code") == "APIKEY_INVALID":
                raise RuntimeError("Scopus does not recognise this API key (401). A Scopus key is "
                                   "32 characters — copy it again from dev.elsevier.com and "
                                   "re-enter it in Settings.")
            raise RuntimeError("Scopus rejected the request (401). The key is valid but not "
                               "authorised from here — Scopus needs you on the campus IP range, "
                               "or an institutional token (set in Settings).")
        if status == 403:
            raise RuntimeError("Scopus access forbidden (403). Your key may lack entitlement "
                               "for the Search API, or your subscription doesn't cover it.")
        if status == 429:
            raise RuntimeError("Scopus quota exceeded (429). The weekly request limit for this "
                               "key is depleted; it resets ~1 week after first use.")
        if status == 400:
            raise RuntimeError("Scopus rejected the query (400) — likely a query-syntax issue.")
        raise RuntimeError(f"Scopus returned HTTP {status or 'no answer'}.")
    results = []
    for e in (data or {}).get("search-results", {}).get("entry", []):
        # An error can also come back inside a 200 body ("Result set was empty")
        if "error" in e:
            if "empty" in str(e.get("error")).lower():
                break
            raise RuntimeError(f"Scopus: {e.get('error')}")
        creator = e.get("dc:creator", "")
        results.append(_article(
            title=e.get("dc:title", "No title"), authors=creator,
            author_list=[creator] if creator else [],
            year=e.get("prism:coverDate", "")[:4] or "n.d.",
            journal=e.get("prism:publicationName", ""), doi=e.get("prism:doi"),
            cited_by=e.get("citedby-count"), abstract=e.get("dc:description", ""),
            source="Scopus"))
    return enrich_access(results), 0

def search_wos(query, max_r, y_from, y_to, sort="relevance", offset=0):
    key = (CONFIG.get("wos_api_key","") or "").strip()
    if not key:
        raise RuntimeError("No Web of Science API key set.")
    # WoS Starter sortField must be "TAG DIRECTION": RS+D = relevance, PY+D =
    # publication year descending. A bare "RS" is refused with HTTP 400.
    sort_p = "&sortField=PY%2BD" if sort == "date" else "&sortField=RS%2BD"
    # WoS paginates by 1-indexed page of size `limit`. Offsets are always a
    # multiple of max_r, so this lands exactly on the next page.
    wos_page = (offset // max_r) + 1 if max_r else 1
    # Every WoS query needs a field tag ("TS=…"); plain words are refused with
    # HTTP 400 (MISS_TAGEQ). Search topic (title, abstract, keywords) unless
    # the user already wrote WoS syntax.
    q = query if re.search(r"\b[A-Z]{2,3}\s*=", query) else f"TS=({query})"
    data, status = fetch_json(
        f"https://api.clarivate.com/apis/wos-starter/v1/documents"
        f"?db=WOS&q={urllib.parse.quote(q)}&limit={max_r}&page={wos_page}{sort_p}",
        headers={"X-ApiKey": key})
    if status != 200:
        if status in (401, 403):
            raise RuntimeError(f"Web of Science rejected the request ({status}). The API key may "
                               "be wrong/expired, not entitled to the WoS Starter API, or its "
                               "subscription may still be awaiting approval on "
                               "developer.clarivate.com.")
        if status == 429:
            raise RuntimeError("Web of Science quota exceeded (429). Try again later.")
        raise RuntimeError(f"Web of Science returned HTTP {status or 'no answer'}.")
    results = []
    for h in (data or {}).get("hits", []):
        src  = h.get("source", {})
        year = str(src.get("publishYear") or "n.d.")
        if not within_range(year, y_from, y_to):
            continue
        names = [a.get("displayName", "") for a in h.get("names", {}).get("authors", [])
                 if a.get("displayName")]
        # WoS Starter returns identifiers as one dict ({"doi": …, "pmid": …}).
        # Older responses gave a list of {"type", "value"}; accept both.
        ids = h.get("identifiers") or {}
        if isinstance(ids, list):
            ids = {i.get("type"): i.get("value") for i in ids if isinstance(i, dict)}
        cites = h.get("citations") or []
        cited = next((c.get("count") for c in cites
                      if isinstance(c, dict) and c.get("db") == "WOS"), None)
        results.append(_article(
            title=h.get("title", "No title"), authors=_short_authors(names),
            author_list=names, year=year, journal=src.get("sourceTitle", ""),
            doi=ids.get("doi"), pmid=ids.get("pmid"), cited_by=cited,
            abstract=h.get("abstract") or "", source="Web of Science"))
    return enrich_access(results), 0

# Every source, in dedup-priority order: when two sources return the same
# paper, the earlier one keeps it. Cochrane and Guidelines come before plain
# PubMed so systematic reviews and guidelines are labelled as such.
SOURCES = [
    # key,             label,                 runner,                takes strict
    ("cochrane",       "Cochrane",            search_cochrane,       True),
    ("guidelines",     "Guidelines",          search_guidelines,     True),
    ("pubmed",         "PubMed",              search_pubmed,         True),
    ("scopus",         "Scopus",              search_scopus,         False),
    ("wos",            "Web of Science",      search_wos,            False),
    ("clinicaltrials", "ClinicalTrials.gov",  search_clinicaltrials, False),
    ("arxiv",          "arXiv",               search_arxiv,          False),
]
_KEY_REQUIRED = {"scopus": ("scopus_api_key", "Scopus"),
                 "wos":    ("wos_api_key", "Web of Science")}

# ══════════════════════════════════════════════════════════════════════════════
#  EXPORT
# ══════════════════════════════════════════════════════════════════════════════

def _author_names(a):
    """Full author list for export: the source's complete list when we have
    it, else the display string split back into names (minus "et al.")."""
    if a.get("author_list"):
        return list(a["author_list"])
    raw = (a.get("authors") or "").replace(" et al.", "")
    if raw == "ClinicalTrials.gov":
        return []
    return [n.strip() for n in raw.split(";") if n.strip()]

_BIB_SPECIAL = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "&": r"\&",
                "%": r"\%", "#": r"\#", "_": r"\_", "$": r"\$",
                "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}

def _bib(text):
    """Escape a value for a BibTeX field. Unbalanced braces in a title used to
    break the whole .bib file; LaTeX specials break the document that cites it."""
    return "".join(_BIB_SPECIAL.get(ch, ch) for ch in str(text or ""))

def _bib_key(a, i, used):
    first = (_author_names(a) or ["anon"])[0]
    surname = first.split(",")[0].split()[-1] if first.strip() else "anon"
    base = re.sub(r"[^A-Za-z0-9]", "", surname) or "anon"
    base += re.sub(r"\D", "", str(a.get("year", "")))[:4]
    key, n = base, 1
    while key in used:
        n += 1
        key = f"{base}{chr(ord('a') + n - 2)}" if n <= 27 else f"{base}_{i}"
    used.add(key)
    return key

def do_export(articles, query, fmt, synthesis=""):
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^\w]+", "_", query)[:40]
    base = Path.home() / "medsearch_exports"
    base.mkdir(parents=True, exist_ok=True)
    paths = []
    if fmt in ("md", "all"):
        p = base / f"medsearch_{safe}_{ts}.md"
        lines = [f"# MedSearch Results\n\n**Query:** {query}  \n"
                 f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  \n"
                 f"**Articles:** {len(articles)}\n\n---\n"]
        for i, a in enumerate(articles, 1):
            lines.append(f"## {i}. {a['title']}\n")
            if a.get("retraction") == "retracted":
                lines.append("**⚠ RETRACTED**  \n")
            lines.append(f"**Source:** {a['source']} | **Year:** {a['year']}  \n")
            if a.get("pub_types"):
                lines.append(f"**Type:** {', '.join(a['pub_types'])}  \n")
            lines.append(f"**Authors:** {'; '.join(_author_names(a))}  \n")
            if a.get("doi"): lines.append(f"**DOI:** https://doi.org/{a['doi']}  \n")
            if a.get("pmid"): lines.append(f"**PMID:** {a['pmid']}  \n")
            if a.get("oneliner"): lines.append(f"**Summary:** _{a['oneliner']}_  \n")
            lines.append(f"\n{a.get('abstract','')}\n\n---\n")
        if synthesis: lines.append(f"\n## AI Synthesis\n\n{synthesis}\n")
        p.write_text("".join(lines), encoding="utf-8"); paths.append(str(p))
    if fmt in ("bib", "all"):
        p = base / f"medsearch_{safe}_{ts}.bib"
        entries, used = [], set()
        for i, a in enumerate(articles, 1):
            fields = [("title", "{" + _bib(a["title"]) + "}"),
                      # BibTeX separates authors with " and "; "; " made one garbled name
                      ("author", " and ".join(_bib(n) for n in _author_names(a))),
                      ("year", _bib(re.sub(r"\D", "", str(a.get("year", "")))[:4])),
                      ("journal", _bib(a.get("journal", "")))]
            if a.get("doi"):  fields.append(("doi", _bib(a["doi"])))
            if a.get("pmid"): fields.append(("pmid", _bib(a["pmid"])))
            if a.get("abstract"): fields.append(("abstract", _bib(a["abstract"])))
            if a.get("retraction") == "retracted": fields.append(("note", "RETRACTED"))
            body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields if v)
            entries.append(f"@article{{{_bib_key(a, i, used)},\n{body}\n}}")
        p.write_text("\n\n".join(entries) + "\n", encoding="utf-8"); paths.append(str(p))
    if fmt in ("ris", "all"):
        p = base / f"medsearch_{safe}_{ts}.ris"
        lines = []
        for a in articles:
            lines += ["TY  - JOUR", f"TI  - {a['title']}"]
            # RIS takes one AU line per author
            lines += [f"AU  - {n}" for n in _author_names(a)]
            lines += [f"PY  - {re.sub(r'[^0-9]', '', str(a.get('year', '')))[:4]}",
                      f"T2  - {a.get('journal','')}"]
            if a.get("doi"):      lines.append(f"DO  - {a['doi']}")
            if a.get("pmid"):     lines.append(f"AN  - {a['pmid']}")
            if a.get("access_link"): lines.append(f"UR  - {a['access_link']}")
            if a.get("abstract"): lines.append(f"AB  - {' '.join(a['abstract'].split())}")
            if a.get("retraction") == "retracted": lines.append("N1  - RETRACTED")
            lines += ["ER  - ", ""]
        p.write_text("\n".join(lines), encoding="utf-8"); paths.append(str(p))
    return paths

# ══════════════════════════════════════════════════════════════════════════════
#  ZOTERO EXPORT  (via the local connector on port 23119)
# ══════════════════════════════════════════════════════════════════════════════

ZOTERO_CONNECTOR = "http://127.0.0.1:23119"

def _parse_creators(authors_str):
    """
    Turn our 'Lastname, F.; Lastname2, G.; ...' author string into Zotero's
    creators array: [{creatorType, firstName, lastName}, ...].
    Handles the ' et al.' suffix and single-field names gracefully.
    """
    creators = []
    if not authors_str:
        return creators
    cleaned = authors_str.replace(" et al.", "").strip()
    for chunk in cleaned.split(";"):
        name = chunk.strip()
        if not name:
            continue
        if "," in name:
            last, first = name.split(",", 1)
            creators.append({"creatorType":"author",
                             "firstName":first.strip(),
                             "lastName":last.strip()})
        else:
            # No comma — store as a single-field name (Zotero supports this)
            creators.append({"creatorType":"author", "name":name})
    return creators

def article_to_zotero_item(a):
    """Map one of our article dicts to a Zotero journalArticle item."""
    item = {
        "itemType":         "journalArticle",
        "title":            a.get("title",""),
        "creators":         _parse_creators("; ".join(_author_names(a))),
        "publicationTitle": a.get("journal",""),
        "date":             str(a.get("year","")),
        "abstractNote":     a.get("abstract","") or "",
        "tags":             [{"tag": "MedSearch"}],
    }
    if a.get("doi"):
        item["DOI"] = a["doi"]
        item["url"] = f"https://doi.org/{a['doi']}"
    elif a.get("pmid"):
        item["url"] = f"https://pubmed.ncbi.nlm.nih.gov/{a['pmid']}/"
    if a.get("pmid"):
        # store PMID in the Extra field, a common convention
        item["extra"] = f"PMID: {a['pmid']}"
    return item

def zotero_ping():
    """Return True if the Zotero desktop app's connector is reachable."""
    try:
        req = urllib.request.Request(f"{ZOTERO_CONNECTOR}/connector/ping",
                                     headers={"User-Agent":"MedSearch"})
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False

def zotero_save(articles):
    """
    POST items to the local Zotero connector's /connector/saveItems endpoint.
    Returns (ok, message). Zotero must be open with the connector available.
    """
    items = [article_to_zotero_item(a) for a in articles]
    payload = json.dumps({
        "items": items,
        "uri":   "https://medsearch.local",
        "sessionID": f"medsearch-{int(time.time())}",
    }).encode()
    req = urllib.request.Request(
        f"{ZOTERO_CONNECTOR}/connector/saveItems",
        data=payload,
        headers={"Content-Type":"application/json",
                 "User-Agent":"MedSearch",
                 "X-Zotero-Connector-API-Version":"3"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30):
            return True, f"{len(items)} item(s) sent to Zotero."
    except urllib.error.HTTPError as e:
        body = ""
        try: body = e.read().decode()[:200]
        except Exception: pass
        return False, f"Zotero returned error {e.code}. {body}"
    except Exception as e:
        return False, f"Could not reach Zotero: {e}"


# ══════════════════════════════════════════════════════════════════════════════
#  SESSION STORE  (in-memory, per-process)
# ══════════════════════════════════════════════════════════════════════════════

HISTORY_FILE = CONFIG_DIR / "history.json"
_HISTORY_MAX = 50

def _load_history():
    try:
        items = json.loads(HISTORY_FILE.read_text())
        return [str(q) for q in items if str(q).strip()][-_HISTORY_MAX:]
    except Exception:
        return []

def _save_history():
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(SESSION["history"][-_HISTORY_MAX:], indent=2))
    except Exception:
        pass

# Recent searches persist across launches; results stay per-process.
# offsets: per-source start of the NEXT "load more" batch.
SESSION = {"articles": [], "query": "", "history": _load_history(),
           "last_synthesis": "", "offsets": {}}

# ══════════════════════════════════════════════════════════════════════════════
#  FLASK ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.before_request
def _guard():
    # Only answer requests addressed to the loopback name we serve on. A DNS-
    # rebinding page arrives with its own hostname and is refused here.
    host = (request.host or "").rsplit(":", 1)[0]
    if host not in ("127.0.0.1", "localhost"):
        return "Forbidden", 403
    if request.path in _OPEN_PATHS or request.path.startswith("/static/"):
        return None
    token = request.headers.get("X-MedSearch-Token") or request.args.get("t") or ""
    if not hmac.compare_digest(token, APP_TOKEN):
        return jsonify({"ok": False, "error": "forbidden",
                        "message": "This request didn't come from the MedSearch window."}), 403
    return None

@app.after_request
def _no_framing(resp):
    resp.headers["X-Frame-Options"] = "DENY"
    return resp

def _json_body():
    """The request's JSON object, or {} for a missing or malformed body."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}

def _int_or_none(v):
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None

def _asset_version():
    """A short hash of the page's own CSS/JS, appended to their URLs. The
    embedded browser caches static files, and after an update it must never
    pair the new HTML with yesterday's script."""
    h = hashlib.sha256()
    for rel in ("static/css/app.css", "static/js/boot.js", "static/js/app.js"):
        try:
            h.update((RESOURCE_DIR / rel).read_bytes())
        except OSError:
            pass
    return h.hexdigest()[:10]

ASSET_V = _asset_version()

@app.route("/")
def index():
    has_key = bool(_anthropic_key())
    ai_pref = CONFIG.get("ai_enabled", True)
    # Optional deep-link from a launch with --query: /?q=...&src=...
    auto_query  = (request.args.get("q") or "").strip()
    auto_source = (request.args.get("src") or CONFIG.get("default_source","pubmed") or "pubmed").strip()
    return render_template("index.html",
                           token=APP_TOKEN,
                           asset_v=ASSET_V,
                           ai_on=(has_key and ai_pref),   # active only if key AND enabled
                           has_ai_key=has_key,             # whether a key exists at all
                           history=SESSION["history"][-10:],
                           saved=load_saved(),
                           show_onboarding=not CONFIG.get("onboarding_seen", False),
                           app_version=get_local_version(),
                           has_scopus=bool((CONFIG.get("scopus_api_key","") or "").strip()),
                           has_wos=bool((CONFIG.get("wos_api_key","") or "").strip()),
                           institution_proxies=CONFIG.get("institution_proxies", []),
                           active_proxy=CONFIG.get("active_proxy", 0),
                           auto_query=auto_query,
                           auto_source=auto_source)

@app.route("/ping")
def ping():
    """Lets a second launch recognise that MedSearch is already running."""
    return jsonify({"app": "medsearch", "version": get_local_version()})

# The native window, once created, so a second launch can bring it forward.
_MAIN_WINDOW = None
# The menu bar item (statusbar.py), on macOS once the window exists.
_STATUSBAR = None

@app.route("/focus", methods=["POST"])
def focus_window():
    w = _MAIN_WINDOW
    if _STATUSBAR is not None:
        # The window may be hidden in the menu bar, with no Dock icon: showing it
        # through the menu bar item brings both back (and un-minimises it).
        from PyObjCTools import AppHelper
        AppHelper.callAfter(_STATUSBAR.show)
        # AppKit work happens on the main thread, so the answer can only say
        # whether there is a window to show, which is what the caller needs:
        # false means "no native window here, open the browser instead".
        return jsonify({"ok": w is not None})
    if w is not None:
        try:
            w.restore()
            w.show()
            # Toggling on_top is pywebview's portable way to raise a window.
            w.on_top = True
            w.on_top = False
        except Exception:
            pass
    return jsonify({"ok": w is not None})

@app.route("/usage")
def usage_report():
    """What the AI has cost this month, for the Settings panel."""
    u = load_usage()
    return jsonify({"month": u["month"], "cost": round(u["cost"], 4),
                    "calls": u["calls"], "unpriced_calls": u.get("unpriced_calls", 0),
                    "cap": ai_cap(), "over_cap": ai_over_cap()})


@app.route("/ai/toggle", methods=["POST"])
def ai_toggle():
    """Turn AI features on/off (user preference, persisted)."""
    data = _json_body()
    CONFIG["ai_enabled"] = bool(data.get("enabled", True))
    save_config(CONFIG)
    return jsonify({"ok": True, "ai_enabled": CONFIG["ai_enabled"]})

@app.route("/proxy/active", methods=["POST"])
def set_active_proxy():
    """
    Set which institution is active (persisted). The index refers to the
    frontend's merged list (predefined UniTN/ASUIT/FBK first, then customs),
    which buildInstitutions() reconstructs deterministically, so we just store
    the integer. -1 means "no library / don't proxy".
    """
    data = _json_body()
    try:
        CONFIG["active_proxy"] = int(data.get("index", 0))
    except Exception:
        CONFIG["active_proxy"] = 0
    save_config(CONFIG)
    return jsonify({"ok": True, "active_proxy": CONFIG["active_proxy"]})

@app.route("/guidelines/bodies")
def guideline_bodies():
    """List the available national guideline bodies (for the country picker)."""
    out = [{"code": code, "name": b["name"], "country": b["country"],
            "prefill": b["prefill"]}
           for code, b in NATIONAL_GUIDELINE_BODIES.items()]
    # stable, country-name order
    out.sort(key=lambda x: x["country"])
    return jsonify({"bodies": out, "selected": CONFIG.get("guideline_country", "")})

@app.route("/guidelines/link", methods=["POST"])
def guideline_link():
    """
    Build the URL to open for a national guideline body. If the body supports a
    query parameter, the current search query is pre-filled; otherwise we return
    the portal/search URL for the user to type into. Also persists the chosen
    country so it's remembered.
    """
    data = _json_body()
    code = (data.get("country") or "").strip().lower()
    query = (data.get("query") or "").strip()
    body = NATIONAL_GUIDELINE_BODIES.get(code)
    if not body:
        return jsonify({"ok": False, "message": "Unknown country."}), 200
    # Remember the selection
    CONFIG["guideline_country"] = code
    save_config(CONFIG)
    url = body["url"]
    prefilled = False
    if body["prefill"] and "{q}" in url:
        if query:
            url = url.replace("{q}", urllib.parse.quote(query))
            prefilled = True
        else:
            # no query to fill — strip to the bare search page
            url = url.split("?")[0]
    return jsonify({"ok": True, "url": url, "name": body["name"],
                    "country": body["country"], "prefilled": prefilled})

@app.route("/onboarding/dismiss", methods=["POST"])
def onboarding_dismiss():
    CONFIG["onboarding_seen"] = True
    save_config(CONFIG)
    return jsonify({"ok": True})

# ── Second launch → running window search handoff ─────────────────────────
# A second launch (e.g. `app.py --query …`) can't reach into the running
# window directly (separate process). It POSTs the search here; the window
# polls /pending_search and runs anything queued, so the search happens INSIDE
# the existing window. The menu bar item is in-process and doesn't need this.
_PENDING_SEARCH = {"query": None, "source": None, "ts": 0}

@app.route("/queue_search", methods=["POST"])
def queue_search():
    """Menu-bar app posts a search request to be picked up by the native window."""
    data = _json_body()
    query = (data.get("query") or "").strip()
    source = (data.get("source") or CONFIG.get("default_source", "pubmed")).strip()
    if not query:
        return jsonify({"ok": False, "message": "Empty query."}), 200
    _PENDING_SEARCH["query"] = query
    _PENDING_SEARCH["source"] = source
    _PENDING_SEARCH["ts"] = time.time()
    return jsonify({"ok": True})

@app.route("/pending_search")
def pending_search():
    """Native window polls this; returns and clears any queued search."""
    q = _PENDING_SEARCH["query"]
    if not q:
        return jsonify({"pending": False})
    src = _PENDING_SEARCH["source"]
    # Clear it so it runs once.
    _PENDING_SEARCH["query"] = None
    _PENDING_SEARCH["source"] = None
    return jsonify({"pending": True, "query": q, "source": src})

# ── Auto-update routes ─────────────────────────────────────────────────────

CHANGELOG_FILE = "CHANGELOG.md"
GITHUB_RAW_CHANGELOG = GITHUB_RAW_VERSION.rsplit("/", 1)[0] + "/" + CHANGELOG_FILE


def changelog_entry(text, version):
    """The lines under `## <version>` in a CHANGELOG, as a list. Empty when the
    file has no entry for it — a version with nothing written about it must not
    invent anything."""
    out, inside = [], False
    for line in (text or "").splitlines():
        if line.startswith("## "):          # a heading ends the previous entry
            inside = line[3:].strip() == str(version).strip()
            continue
        if inside and line.strip().startswith("- "):
            out.append(line.strip()[2:].strip())
    return out[:8]


@app.route("/update/check")
def update_check():
    """Compare local VERSION with the one on GitHub. No git needed for the check."""
    local = get_local_version()
    body, status = http_get(GITHUB_RAW_VERSION, timeout=8)
    if not body:
        return jsonify({"ok": False, "reason": "offline",
                        "local": local})
    remote = body.strip()
    update_available = _version_tuple(remote) > _version_tuple(local)
    # What the new version changes, read from the same place it is published.
    changes = []
    if update_available:
        notes, _ = http_get(GITHUB_RAW_CHANGELOG, timeout=8)
        changes = changelog_entry(notes, remote)
    # Is this a git checkout? (update can only be applied if so)
    is_git = (APP_DIR_PATH / ".git").exists()
    return jsonify({
        "ok": True,
        "local": local,
        "remote": remote,
        "update_available": update_available,
        "can_apply": is_git,
        "changes": changes,
    })

def _requirements_digest():
    try:
        return hashlib.sha256((APP_DIR_PATH / "requirements.txt").read_bytes()).hexdigest()
    except Exception:
        return ""

@app.route("/update/apply", methods=["POST"])
def update_apply():
    """
    Update to the latest version from GitHub.
    Uses fetch + hard reset to the remote branch so local file changes
    (e.g. a flipped executable bit, or an accidental edit) can't block the
    update. User config and data live in ~/.medsearch/, outside the repo,
    so they're never touched. If requirements.txt changed, the new
    dependencies are installed into the running interpreter's environment
    before the app offers to restart — otherwise an update that adds a
    dependency would leave an app that no longer starts.
    """
    if not (APP_DIR_PATH / ".git").exists():
        return jsonify({"ok": False,
                        "message": "This copy isn't a git checkout, so it can't auto-update. "
                                   "Please re-clone from GitHub."}), 200
    git = ["git", "-C", str(APP_DIR_PATH)]
    version_before = get_local_version()
    reqs_before = _requirements_digest()
    try:
        # 1. Fetch the latest commits from origin
        fetch = subprocess.run(git + ["fetch", "origin"],
                               capture_output=True, text=True, timeout=60)
        if fetch.returncode != 0:
            return jsonify({"ok": False,
                            "message": "Couldn't reach GitHub to fetch the update.",
                            "error": (fetch.stderr or "").strip()[-400:]}), 200

        # 2. Determine the current branch (usually 'main')
        branch_res = subprocess.run(git + ["rev-parse", "--abbrev-ref", "HEAD"],
                                    capture_output=True, text=True, timeout=15)
        branch = branch_res.stdout.strip()
        if not branch or branch == "HEAD":      # detached checkout
            branch = "main"

        # 3. Hard reset to origin/<branch> — guarantees we match the remote
        reset = subprocess.run(git + ["reset", "--hard", f"origin/{branch}"],
                               capture_output=True, text=True, timeout=60)
        if reset.returncode != 0:
            return jsonify({"ok": False,
                            "message": "Update failed while applying changes.",
                            "error": (reset.stderr or reset.stdout).strip()[-400:]}), 200

        # 4. New or changed dependencies → install them now, into this venv
        if _requirements_digest() != reqs_before:
            pip = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
                                  "-r", str(APP_DIR_PATH / "requirements.txt")],
                                 capture_output=True, text=True, timeout=600)
            if pip.returncode != 0:
                return jsonify({"ok": False,
                                "message": "The update was downloaded, but installing its new "
                                           "components failed. MedSearch may not start until this "
                                           "is fixed — run \"Create Desktop App.command\" again.",
                                "error": (pip.stderr or pip.stdout).strip()[-400:]}), 200

        # 5. Verify the version actually changed (catch silent no-ops)
        version_after = get_local_version()
        if _version_tuple(version_after) <= _version_tuple(version_before):
            return jsonify({"ok": True, "new_version": version_after, "unchanged": True,
                            "message": f"Already up to date (version {version_after})."})
        return jsonify({"ok": True, "new_version": version_after, "unchanged": False,
                        "can_restart": not getattr(sys, "frozen", False)})
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "message": "Update timed out."}), 200
    except FileNotFoundError:
        return jsonify({"ok": False,
                        "message": "git is not installed, so auto-update isn't available."}), 200
    except Exception as e:
        return jsonify({"ok": False, "message": f"Update error: {e}"}), 200

def _relaunch_and_exit():
    """Start a fresh copy of MedSearch once this process has gone, then exit.

    Launched from the Desktop wrapper, the app is re-opened through
    LaunchServices (`open -b`) so it comes back as MedSearch, with its icon and
    no Terminal. A small detached shell waits for this PID to disappear first,
    so the new copy gets port 5050 instead of finding this one still alive.
    """
    time.sleep(0.4)          # let the HTTP response reach the window
    pid = os.getpid()
    bundle_id = _launcher_bundle_id()
    app_py = str(APP_DIR_PATH / "app.py")
    try:
        if os.name == "posix":
            import shlex
            if sys.platform == "darwin" and bundle_id:
                relaunch = f"open -b {shlex.quote(bundle_id)}"
            else:
                relaunch = (f"cd {shlex.quote(str(APP_DIR_PATH))} && "
                            f"exec {shlex.quote(sys.executable)} {shlex.quote(app_py)} --relaunch")
            script = f"while kill -0 {pid} 2>/dev/null; do sleep 0.2; done; {relaunch}"
            subprocess.Popen(["/bin/sh", "-c", script], cwd=str(APP_DIR_PATH),
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        else:
            flags = getattr(subprocess, "DETACHED_PROCESS", 0) | \
                    getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            subprocess.Popen([sys.executable, app_py, "--relaunch"], cwd=str(APP_DIR_PATH),
                             creationflags=flags, close_fds=True)
    finally:
        os._exit(0)

@app.route("/app/restart", methods=["POST"])
def app_restart():
    if getattr(sys, "frozen", False):
        return jsonify({"ok": False, "message": "Please quit and reopen MedSearch."})
    threading.Thread(target=_relaunch_and_exit, daemon=True).start()
    return jsonify({"ok": True})

# Sources that must be released before any later source, so the Cochrane /
# Guidelines / PubMed labels win the dedup exactly as they did when the
# sources ran one after another.
_PRIORITY_SOURCES = {"cochrane", "guidelines", "pubmed"}

@app.route("/search_stream", methods=["POST"])
def search_stream():
    """Streaming search — every source runs at once; results stream via SSE."""
    data    = _json_body()
    query   = (data.get("query") or "").strip()
    wanted  = data.get("sources") or []
    try:
        max_r = max(1, min(int(data.get("max_results") or MAX_RESULTS_DEFAULT), 100))
    except (TypeError, ValueError):
        max_r = MAX_RESULTS_DEFAULT
    y_from  = _int_or_none(data.get("year_from"))
    y_to    = _int_or_none(data.get("year_to"))
    strict  = data.get("strict", True) is not False
    sort    = data.get("sort") if data.get("sort") in ("relevance", "date") else "relevance"
    load_more = bool(data.get("load_more"))

    def one_event(obj):
        return Response(_sse(obj), mimetype="text/event-stream")
    if not query:
        return one_event({"type": "error", "text": "Empty query"})
    if load_more and query != SESSION.get("query"):
        return one_event({"type": "error",
                          "text": "The search changed since these results loaded. Run it again first."})

    selected = [src for src in SOURCES if src[0] in wanted or "all" in wanted]

    # Fresh search resets the session; "load more" keeps existing results and
    # asks each source for its OWN next batch. (The window used to send the
    # total shown across all sources as every source's offset, so with three
    # sources the second batch skipped results 11–30 of each.)
    if not load_more:
        SESSION["articles"] = []
        SESSION["query"]    = query
        SESSION["last_synthesis"] = ""
        SESSION["offsets"]  = {}
        if query in SESSION["history"]:
            SESSION["history"].remove(query)
        SESSION["history"].append(query)
        _save_history()
    starts = {}
    for key, *_ in selected:
        starts[key] = SESSION["offsets"].get(key, 0) if load_more else 0
        SESSION["offsets"][key] = starts[key] + max_r

    def run_source(key, fn, takes_strict):
        kwargs = dict(sort=sort, offset=starts[key])
        if takes_strict:
            kwargs["strict"] = strict
        return fn(query, max_r, y_from, y_to, **kwargs)

    def generate():
        seen = set()
        if load_more:
            all_results = list(SESSION["articles"])
            for a in all_results:
                register(seen, a.get("doi"), a.get("title"))
        else:
            all_results = []
        ai_on = ai_active()

        # Initial padding comment defeats buffering in some webviews.
        yield ":" + (" " * 2048) + "\n\n"

        src_pool = concurrent.futures.ThreadPoolExecutor(max_workers=len(selected) + 1)
        ai_pool  = concurrent.futures.ThreadPoolExecutor(max_workers=8)
        pending  = {}          # future → ("mesh",) | ("src", key) | ("ol", idx)
        finished = {}          # key → (results, total, error_text)
        released = set()
        try:
            total_sources = len(selected)
            for i, (key, label, fn, takes_strict) in enumerate(selected, 1):
                yield _sse({"type": "source_start", "source": label,
                            "index": i, "total": total_sources})
                if key in _KEY_REQUIRED and not (CONFIG.get(_KEY_REQUIRED[key][0]) or "").strip():
                    finished[key] = ([], 0, f"Add a {_KEY_REQUIRED[key][1]} API key in Settings "
                                            "to search this source.")
                else:
                    pending[src_pool.submit(run_source, key, fn, takes_strict)] = ("src", key)

            # MeSH hints only on a fresh search that includes a PubMed source
            if not load_more and any(k in _PRIORITY_SOURCES for k, *_ in selected):
                pending[src_pool.submit(get_mesh, query)] = ("mesh",)

            def release_ready():
                for key, label, _fn, _s in selected:
                    if key in released:
                        continue
                    if key not in finished:
                        if key in _PRIORITY_SOURCES:
                            return          # later sources wait for this one
                        continue
                    released.add(key)
                    res, total, err = finished[key]
                    if err:
                        yield _sse({"type": "source_error", "source": label, "text": err})
                    fresh = []
                    for a in res:
                        if is_duplicate(seen, a.get("doi"), a.get("title")):
                            continue
                        register(seen, a.get("doi"), a.get("title"))
                        a["_idx"] = len(all_results)
                        all_results.append(a)
                        fresh.append(a)
                        yield _sse({"type": "article", "source": label, "article": a})
                    SESSION["articles"] = all_results
                    yield _sse({"type": "source_done", "source": label, "count": len(fresh),
                                "total_pubmed": total if key == "pubmed" else 0,
                                "running_count": len(all_results),
                                "done_sources": len(released), "total_sources": total_sources})
                    if ai_on:
                        for a in fresh:
                            if a.get("abstract") and not a.get("oneliner"):
                                fut = ai_pool.submit(ai_oneliner, a.get("title", ""), a["abstract"])
                                pending[fut] = ("ol", a["_idx"])

            yield from release_ready()
            while pending:
                done, _ = concurrent.futures.wait(
                    list(pending), timeout=10, return_when=concurrent.futures.FIRST_COMPLETED)
                if not done:
                    yield ":keep-alive\n\n"
                    continue
                for fut in done:
                    tag = pending.pop(fut)
                    if tag[0] == "mesh":
                        try: mesh = fut.result()
                        except Exception: mesh = []
                        yield _sse({"type": "mesh", "mesh": mesh})
                    elif tag[0] == "src":
                        try:
                            res, total = fut.result()
                            finished[tag[1]] = (res, total, None)
                        except Exception as e:
                            finished[tag[1]] = ([], 0, str(e) or "This source failed.")
                        yield from release_ready()
                    else:
                        try: ol = fut.result()
                        except Exception: ol = None
                        if ol and tag[1] < len(all_results):
                            all_results[tag[1]]["oneliner"] = ol
                            yield _sse({"type": "oneliner", "idx": tag[1], "text": ol})

            yield _sse({"type": "done", "count": len(all_results)})
        finally:
            # Also reached when the window stops the search mid-stream.
            src_pool.shutdown(wait=False, cancel_futures=True)
            ai_pool.shutdown(wait=False, cancel_futures=True)
            save_doi_cache()

    resp = Response(stream_with_context(generate()), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache, no-transform"
    resp.headers["X-Accel-Buffering"] = "no"
    resp.headers["Content-Encoding"] = "none"   # prevent gzip buffering
    return resp

def _sse_response(gen):
    return Response(stream_with_context(gen), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.route("/synthesis")
def synthesis():
    query    = SESSION.get("query","")
    articles = SESSION.get("articles",[])
    def generate():
        text = ""
        for chunk in ai_synthesis_stream(query, articles):
            try:
                ev = json.loads(chunk[6:])
                if ev.get("type") == "chunk":
                    text += ev["text"]
            except Exception:
                pass
            yield chunk
        SESSION["last_synthesis"] = text
    return _sse_response(generate())

@app.route("/explain/<int:idx>")
def explain(idx):
    articles = SESSION.get("articles",[])
    if idx < 0 or idx >= len(articles):
        return _sse_response(iter([_sse({"type": "error", "text": "Invalid index"}),
                                   _sse({"type": "done"})]))
    return _sse_response(ai_explain_stream(articles[idx]))

@app.route("/citations/<int:idx>")
def citations(idx):
    articles = SESSION.get("articles",[])
    if idx < 0 or idx >= len(articles):
        return jsonify({"error":"Invalid index"}), 400
    art = articles[idx]
    doi = art.get("doi")
    if not doi:
        return jsonify({"error":"no_doi",
                        "message":"This article has no DOI, so its citation graph can't be retrieved.",
                        "title": art.get("title","")}), 200
    graph = get_citation_graph(doi)
    graph["source_title"] = art.get("title","")
    graph["source_year"]  = art.get("year","")
    return jsonify(graph)

# ── AI Assistant routes ────────────────────────────────────────────────────

@app.route("/assistant/suggestions")
def assistant_suggestions_route():
    """Return suggested follow-up questions for the current search."""
    query    = SESSION.get("query","")
    articles = SESSION.get("articles",[])
    return jsonify({"suggestions": assistant_suggestions(query, articles)})

@app.route("/assistant/chat", methods=["POST"])
def assistant_chat_route():
    """Streaming chat grounded in the current results.
    Body: {messages: [{role, content}, ...]}"""
    messages = _json_body().get("messages") or []
    # Basic validation/sanitation of the conversation
    clean = []
    for m in messages if isinstance(messages, list) else []:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = str(m.get("content") or "").strip()
        if role in ("user","assistant") and content:
            clean.append({"role":role, "content":content[:4000]})
    if not clean or clean[-1]["role"] != "user":
        return _sse_response(iter([_sse({"type": "error", "text": "No question provided."}),
                                   _sse({"type": "done"})]))
    # Keep only the last ~6 turns to bound the prompt size. The API requires
    # the conversation to open with a user turn, so trim any leading reply.
    clean = clean[-6:]
    while clean and clean[0]["role"] != "user":
        clean.pop(0)
    query    = SESSION.get("query","")
    articles = SESSION.get("articles",[])
    return _sse_response(assistant_chat_stream(clean, query, articles))

def _is_scihub_url(url):
    """True if the URL points at a known Sci-Hub mirror."""
    mirrors = CONFIG.get("scihub_mirrors") or DEFAULTS["scihub_mirrors"]
    hosts = []
    for m in mirrors:
        try: hosts.append(urllib.parse.urlparse(m).hostname or "")
        except Exception: pass
    try:
        h = urllib.parse.urlparse(url).hostname or ""
    except Exception:
        return False
    return any(h == host or h.endswith("." + host) for host in hosts if host)

def _abs_url(href, page_url):
    """Resolve a possibly-relative/protocol-relative href against page_url."""
    if not href:
        return None
    href = href.strip().split("#")[0]
    if not href:
        return None
    if href.startswith("//"):
        scheme = urllib.parse.urlparse(page_url).scheme or "https"
        return f"{scheme}:{href}"
    if href.startswith("/"):
        base = urllib.parse.urlparse(page_url)
        return f"{base.scheme}://{base.netloc}{href}"
    if not href.startswith(("http://", "https://")):
        return urllib.parse.urljoin(page_url, href)
    return href

def _extract_pdf_url_from_landing(html_text, page_url):
    """
    Many publisher/repository 'open access' links point at an HTML landing page
    rather than a direct PDF. Most academic pages advertise the real PDF via a
    <meta name="citation_pdf_url"> tag (Google Scholar convention); some embed it
    in <iframe>/<embed> or link it with a .pdf href. Return the best PDF URL or None.
    """
    # 1. citation_pdf_url meta tag — the most reliable signal across publishers
    m = re.search(
        r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)["\']',
        html_text, flags=re.IGNORECASE)
    if not m:
        m = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']citation_pdf_url["\']',
            html_text, flags=re.IGNORECASE)
    if m:
        u = _abs_url(m.group(1), page_url)
        if u:
            return u
    # 2. iframe/embed/href pointing at something PDF-ish
    candidates = []
    for pat in [
        r'<iframe[^>]+src\s*=\s*["\']([^"\']+)["\']',
        r'<embed[^>]+src\s*=\s*["\']([^"\']+)["\']',
        r'href\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']',
    ]:
        candidates += re.findall(pat, html_text, flags=re.IGNORECASE)
    for c in candidates:
        u = _abs_url(c, page_url)
        if u and (".pdf" in u.lower() or "/pdf" in u.lower()):
            return u
    return None

def _extract_scihub_pdf_url(html_text, page_url):
    """
    Sci-Hub returns an HTML page with the actual PDF embedded in an <iframe>,
    <embed>, or a download button. Parse out that real PDF URL and return it
    absolute, or None if not found.
    """
    candidates = []
    # Common Sci-Hub patterns: <iframe src="..."> / <embed src="..."> /
    # onclick="location.href='...'" download button.
    for pat in [
        r'<iframe[^>]+src\s*=\s*["\']([^"\']+)["\']',
        r'<embed[^>]+src\s*=\s*["\']([^"\']+)["\']',
        r'location\.href\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']',
        r'href\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']',
    ]:
        candidates += re.findall(pat, html_text, flags=re.IGNORECASE)

    for c in candidates:
        u = _abs_url(c, page_url)
        if not u:
            continue
        low = u.lower()
        if ".pdf" in low or "/pdf" in low or "downloads" in low:
            return u
    # Fallback: if exactly one iframe/embed was found, use it even without .pdf
    if candidates:
        return _abs_url(candidates[0], page_url)
    return None


_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "application/pdf,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}

def _is_private_host(host):
    """True for loopback / LAN / link-local hosts. The PDF proxy fetches URLs
    taken from third-party pages, which must never reach into this machine or
    the hospital network."""
    import ipaddress, socket
    if not host:
        return True
    host = host.strip("[]").lower()
    if host == "localhost" or host.endswith(".local") or host.endswith(".localhost"):
        return True
    try:
        addrs = {ai[4][0] for ai in socket.getaddrinfo(host, None)}
    except Exception:
        return False        # unresolvable: the fetch itself will fail
    for addr in addrs:
        ip = ipaddress.ip_address(addr.split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved \
                or ip.is_multicast or ip.is_unspecified:
            return True
    return False

def _fetch_url_bytes(url, timeout=30, referer=None):
    """
    Fetch a URL with browser-like headers; return (data_bytes, content_type).
    Handles gzip/deflate and follows redirects (urllib does this, but we add a
    Referer of the page's own origin which some publishers require).
    Raises urllib.error.HTTPError on 4xx/5xx so callers can react (e.g. 403).
    """
    import gzip, zlib
    if _is_private_host(urllib.parse.urlparse(url).hostname):
        raise urllib.error.URLError("refusing to fetch a local-network address")
    headers = dict(_BROWSER_HEADERS)
    # A same-origin Referer placates some publishers' hotlink protection.
    parsed = urllib.parse.urlparse(url)
    headers["Referer"] = referer or f"{parsed.scheme}://{parsed.netloc}/"
    req = urllib.request.Request(url, headers=headers)
    upstream = urllib.request.urlopen(req, timeout=timeout)
    raw = upstream.read()
    enc = (upstream.headers.get("Content-Encoding", "") or "").lower()
    try:
        if "gzip" in enc:
            raw = gzip.decompress(raw)
        elif "deflate" in enc:
            try: raw = zlib.decompress(raw)
            except Exception: raw = zlib.decompress(raw, -zlib.MAX_WBITS)
    except Exception:
        pass
    ctype = upstream.headers.get("Content-Type", "").lower()
    return raw, ctype

def _scihub_urls_for(url):
    """
    Given a primary access URL that's failing, find the Sci-Hub mirror URLs for
    the SAME article (matched via the session by access_link), so we can fall
    through to Sci-Hub automatically. Returns a list (possibly empty).
    """
    for a in SESSION.get("articles", []):
        if a.get("access_link") == url:
            return list(a.get("scihub") or [])
    return []

def _mirror_base(url):
    """The scheme and host of a mirror URL, e.g. https://sci-hub.ru/10.x → https://sci-hub.ru"""
    try:
        p = urllib.parse.urlsplit(url)
        return f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else ""
    except Exception:
        return ""


def _promote_mirror(base):
    """Put the mirror that just worked at the head of the list, and remember it.

    Mirrors go down and stay down (sci-hub.se was blocked in January and the
    order had to be corrected by hand). This reorders from what actually
    happened — the fetch the user asked for — so nothing extra is requested,
    and the next article starts with the mirror that answered last time."""
    if not base:
        return
    mirrors = list(CONFIG.get("scihub_mirrors") or DEFAULTS["scihub_mirrors"])
    if base not in mirrors or mirrors[0] == base:
        return
    mirrors.remove(base)
    CONFIG["scihub_mirrors"] = [base] + mirrors
    try:
        save_config(CONFIG)
    except Exception:
        pass


def _try_scihub_chain(mirrors):
    """
    Try each Sci-Hub mirror in turn: fetch the page, extract the embedded PDF,
    fetch that, and return (pdf_bytes, ctype) on the first success, else None.
    """
    for m in mirrors:
        try:
            data, ctype = _fetch_url_bytes(m)
            if ("pdf" in ctype) or data[:5] == b"%PDF-":
                _promote_mirror(_mirror_base(m))
                return data, ctype
            html_text = data.decode("utf-8", errors="replace")
            pdf_url = _extract_scihub_pdf_url(html_text, m)
            if pdf_url:
                pdata, pctype = _fetch_url_bytes(pdf_url, referer=m)
                if ("pdf" in pctype) or pdata[:5] == b"%PDF-":
                    _promote_mirror(_mirror_base(m))
                    return pdata, pctype
        except Exception:
            continue   # try the next mirror
    return None

@app.route("/pdf_proxy")
def pdf_proxy():
    """
    Fetch a PDF server-side and stream it to the client. Bypasses
    X-Frame-Options / CORS that block embedding external PDFs in an iframe.
    Only proxies links the app already surfaced (not an open relay).

    For Sci-Hub URLs, which return an HTML viewer page rather than a direct
    PDF, we parse out the embedded PDF URL and fetch that instead.
    """
    url = request.args.get("url","").strip()
    if not url or not url.lower().startswith(("http://","https://")):
        return jsonify({"error":"Invalid URL"}), 400

    # Light safety: only proxy if this URL relates to the current session's
    # known access links (prevents the proxy being used as an open relay).
    # We also accept institutional-proxy *variants* of those known URLs, since
    # the DOI button may rewrite the host (ezp.biblio.unitn.it) or wrap it as
    # ?url=<encoded>. We match by checking whether a known DOI/host appears.
    known = set()
    known_dois = set()
    for a in SESSION.get("articles", []):
        if a.get("access_link"): known.add(a["access_link"])
        for m in (a.get("scihub") or []): known.add(m)
        if a.get("doi"): known_dois.add(str(a["doi"]).lower())

    # Hosts of the user's configured library proxies. A URL on one of them
    # (EZProxy rewrites doi.org → doi-org.ezp.biblio.unitn.it) is allowed only
    # when it carries a DOI or link from the current results. The old check
    # accepted ANY URL that merely contained a known DOI somewhere, including
    # one pointing at this machine.
    proxy_hosts = set()
    for p in CONFIG.get("institution_proxies") or []:
        h = urllib.parse.urlparse((p or {}).get("url") or "").hostname
        if h:
            proxy_hosts.add(h.lower())

    def _is_allowed(u):
        if u in known:
            return True
        host = (urllib.parse.urlparse(u).hostname or "").lower()
        if not any(host == h or host.endswith("." + h) for h in proxy_hosts):
            return False
        low = urllib.parse.unquote(u).lower()
        return any(d and d in low for d in known_dois) or \
               any(k and k.lower() in low for k in known)

    if not _is_allowed(url):
        return jsonify({"error":"URL not recognized from current results"}), 403

    try:
        # ── Attempt 1: the requested URL directly ──────────────────────────
        primary_error = None
        data = ctype = None
        is_pdf = False
        try:
            data, ctype = _fetch_url_bytes(url)
            is_pdf = ("pdf" in ctype) or data[:5] == b"%PDF-"
        except urllib.error.HTTPError as e:
            primary_error = e.code            # e.g. 403 from a publisher
        except Exception:
            primary_error = "fetch"

        # ── If it's a Sci-Hub URL serving HTML, extract the embedded PDF ────
        if data is not None and not is_pdf and _is_scihub_url(url):
            html_text = data.decode("utf-8", errors="replace")
            pdf_url = _extract_scihub_pdf_url(html_text, url)
            if pdf_url:
                try:
                    data, ctype = _fetch_url_bytes(pdf_url, referer=url)
                    is_pdf = ("pdf" in ctype) or data[:5] == b"%PDF-"
                except Exception:
                    pass

        # ── If it's a publisher landing page (HTML), look for the real PDF ──
        elif data is not None and not is_pdf and "html" in (ctype or ""):
            html_text = data.decode("utf-8", errors="replace")
            pdf_url = _extract_pdf_url_from_landing(html_text, url)
            if pdf_url and pdf_url != url:
                try:
                    data, ctype = _fetch_url_bytes(pdf_url, referer=url)
                    is_pdf = ("pdf" in ctype) or data[:5] == b"%PDF-"
                except Exception:
                    pass

        # ── Fallthrough: primary route failed (403/paywall/no-PDF). If this
        #    article has Sci-Hub mirrors, try them automatically before giving
        #    up — Sci-Hub serves the PDF directly and isn't IP/paywall-gated. ─
        if not is_pdf and not _is_scihub_url(url):
            mirrors = _scihub_urls_for(url)
            if mirrors:
                got = _try_scihub_chain(mirrors)
                if got:
                    data, ctype = got
                    is_pdf = True

        # ── Success ────────────────────────────────────────────────────────
        if is_pdf and data:
            resp = Response(data, mimetype="application/pdf")
            resp.headers["Content-Disposition"] = "inline; filename=article.pdf"
            resp.headers["Cache-Control"] = "private, max-age=600"
            return resp

        # ── Honest, specific failure messages ──────────────────────────────
        if _is_scihub_url(url):
            return jsonify({"error":"scihub_no_pdf",
                            "message":"Sci-Hub doesn't have a readable PDF for this article "
                                      "(it may not be in their collection)."}), 415
        if primary_error == 403:
            return jsonify({"error":"forbidden",
                            "message":"The publisher blocked the download (403). This is common for "
                                      "paywalled journals. Try the Sci-Hub button, or open it in your browser "
                                      "where your institutional login applies."}), 415
        if primary_error:
            return jsonify({"error":"fetch_failed",
                            "message":"Couldn't reach this PDF directly. Try the Sci-Hub button, or open "
                                      "it in your browser."}), 502
        return jsonify({"error":"not_pdf",
                        "message":"This link opens a web page rather than a direct PDF. Try the Sci-Hub "
                                  "button, or open it in your browser."}), 415
    except Exception as e:
        return jsonify({"error":"fetch_failed",
                        "message":f"Couldn't fetch the PDF: {e}"}), 502

def _selected_articles(data):
    """The articles to export: the ones the window lists in `indices` (what
    the result filters leave visible), or every result when none are given."""
    articles = SESSION.get("articles", [])
    idx = data.get("indices")
    if not isinstance(idx, list):
        return articles
    picked = []
    for i in idx:
        if isinstance(i, int) and 0 <= i < len(articles):
            picked.append(articles[i])
    return picked

@app.route("/export", methods=["POST"])
def export():
    data      = _json_body()
    fmt       = data.get("format", "md")
    if fmt not in ("md", "bib", "ris", "all"):
        fmt = "md"
    synthesis = SESSION.get("last_synthesis","")
    articles  = _selected_articles(data)
    query     = SESSION.get("query","")
    if not articles: return jsonify({"error":"No articles to export"}), 400
    paths = do_export(articles, query, fmt, synthesis)
    return jsonify({"paths": paths, "count": len(articles)})

@app.route("/export/zotero/check")
def export_zotero_check():
    """Tell the frontend whether Zotero's connector is reachable right now."""
    return jsonify({"available": zotero_ping()})

@app.route("/export/zotero", methods=["POST"])
def export_zotero():
    articles = _selected_articles(_json_body())
    if not articles:
        return jsonify({"ok": False, "message": "No articles to send."}), 200
    if not zotero_ping():
        return jsonify({"ok": False, "available": False,
                        "message": "Zotero isn't running. Open the Zotero desktop app and try again."}), 200
    ok, msg = zotero_save(articles)
    return jsonify({"ok": ok, "available": True, "message": msg})

@app.route("/export/zotero/single", methods=["POST"])
def export_zotero_single():
    """Send one article (by its session index) straight to Zotero."""
    data = _json_body()
    try:
        idx = int(data.get("idx", -1))
    except Exception:
        idx = -1
    articles = SESSION.get("articles", [])
    if idx < 0 or idx >= len(articles) or articles[idx] is None:
        return jsonify({"ok": False, "message": "Article not found."}), 200
    if not zotero_ping():
        return jsonify({"ok": False, "available": False,
                        "message": "Zotero isn't running. Open the Zotero desktop app and try again."}), 200
    ok, msg = zotero_save([articles[idx]])
    return jsonify({"ok": ok, "available": True, "message": msg})

# ── Open at login (macOS) ────────────────────────────────────────────────────
# A LaunchAgent that starts MedSearch in the menu bar, window hidden. Launched
# through the installed launcher when there is one (so it is MedSearch in the
# Dock, not Python), else straight from this folder. A LaunchAgent works on
# every macOS the app supports; the newer login-item API needs macOS 13.
_LOGIN_LABEL = "com.halbarad.medsearch"
_LOGIN_AGENT = Path.home() / "Library" / "LaunchAgents" / f"{_LOGIN_LABEL}.plist"

def _open_at_login_supported():
    return sys.platform == "darwin" and not getattr(sys, "frozen", False)

def _set_open_at_login(on):
    if not on:
        _LOGIN_AGENT.unlink(missing_ok=True)
        return
    bundle_id = _launcher_bundle_id()
    if bundle_id:
        args = ["/usr/bin/open", "-b", bundle_id, "--args", "--background"]
    else:
        args = [sys.executable, str(APP_DIR_PATH / "app.py"), "--background"]
    items = "".join(f"<string>{escape_xml(a)}</string>" for a in args)
    _LOGIN_AGENT.parent.mkdir(parents=True, exist_ok=True)
    _LOGIN_AGENT.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0"><dict>'
        f'<key>Label</key><string>{_LOGIN_LABEL}</string>'
        f'<key>ProgramArguments</key><array>{items}</array>'
        f'<key>WorkingDirectory</key><string>{escape_xml(str(APP_DIR_PATH))}</string>'
        '<key>RunAtLoad</key><true/>'
        '</dict></plist>\n')

@app.route("/settings", methods=["GET","POST"])
def settings():
    if request.method == "POST":
        data = _json_body()
        secret_fields = ("anthropic_api_key","pubmed_api_key","scopus_api_key",
                         "scopus_insttoken","wos_api_key","unpaywall_email")
        # A blank field means "keep what's saved" (the field shows a masked
        # placeholder), so removing a key is an explicit request.
        for k in data.get("clear") or []:
            if k in secret_fields:
                CONFIG[k] = ""
        for k in secret_fields:
            if isinstance(data.get(k), str) and data[k].strip():
                CONFIG[k] = data[k].strip()
        # Institutional proxies: list of {label, url}; active index.
        if "institution_proxies" in data and isinstance(data["institution_proxies"], list):
            cleaned = []
            for p in data["institution_proxies"]:
                if not isinstance(p, dict):
                    continue
                url = (p.get("url") or "").strip()
                label = (p.get("label") or "").strip() or "Institution"
                if url:
                    entry = {"label": label, "url": url}
                    # Preserve the stable id for predefined institutions so the
                    # URL rehydrates into the right slot (UniTN/ASUIT/FBK) on load.
                    if p.get("id"):
                        entry["id"] = str(p["id"])
                    cleaned.append(entry)
            CONFIG["institution_proxies"] = cleaned
            # keep the legacy single field in sync with the first entry
            CONFIG["institution_proxy"] = cleaned[0]["url"] if cleaned else ""
        if "ai_monthly_cap" in data:
            try:
                CONFIG["ai_monthly_cap"] = max(0.0, float(data["ai_monthly_cap"] or 0))
            except Exception:
                CONFIG["ai_monthly_cap"] = 0.0
        if "active_proxy" in data:
            try:
                # -1 is a valid value meaning "no library / don't proxy"
                CONFIG["active_proxy"] = int(data["active_proxy"])
            except Exception:
                CONFIG["active_proxy"] = 0
        save_config(CONFIG)
        # The login item is a file outside the config, so it can fail on its
        # own (a managed Mac may refuse ~/Library/LaunchAgents). The settings
        # are already saved by then, so this is a WARNING, not a failure: the
        # page must still finish saving, or its proxy list would drift from
        # what is on disk.
        warning = None
        if "open_at_login" in data and _open_at_login_supported():
            try:
                _set_open_at_login(bool(data["open_at_login"]))
            except Exception as e:
                warning = f"Settings were saved, but opening at login couldn't be changed: {e}"
        return jsonify({"ok": True, "warning": warning} if warning else {"ok": True})
    # Mask API keys (show only last 4 chars). Email and proxy URL aren't
    # sensitive, so return them in full so the user can see and verify them.
    safe = {}
    for k, v in CONFIG.items():
        if not isinstance(v, str):
            continue
        if k in ("unpaywall_email", "institution_proxy"):
            safe[k] = v
        elif len(v) > 4:
            safe[k] = "*"*(len(v)-4) + v[-4:]
        else:
            safe[k] = "set" if v else ""
    # Non-string settings the UI needs back in full
    safe["institution_proxies"] = CONFIG.get("institution_proxies", [])
    safe["active_proxy"] = CONFIG.get("active_proxy", 0)
    safe["ai_monthly_cap"] = ai_cap()
    safe["can_open_at_login"] = _open_at_login_supported()
    safe["open_at_login"] = _LOGIN_AGENT.exists()
    return jsonify(safe)

@app.route("/history")
def history():
    return jsonify(SESSION["history"][-20:])

@app.route("/history/delete", methods=["POST"])
def history_delete():
    q = _json_body().get("query","")
    SESSION["history"] = [h for h in SESSION["history"] if h != q]
    _save_history()
    return jsonify({"ok": True, "history": SESSION["history"][-20:]})

@app.route("/history/clear", methods=["POST"])
def history_clear():
    SESSION["history"] = []
    _save_history()
    return jsonify({"ok": True})

# ══════════════════════════════════════════════════════════════════════════════
#  SAVED SEARCHES  (persisted to disk so they survive restarts)
# ══════════════════════════════════════════════════════════════════════════════

SAVED_FILE = CONFIG_DIR / "saved_searches.json"

def load_saved():
    if SAVED_FILE.exists():
        try: return json.loads(SAVED_FILE.read_text())
        except Exception: return []
    return []

def write_saved(items):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SAVED_FILE.write_text(json.dumps(items, indent=2))

@app.route("/saved", methods=["GET"])
def saved_list():
    return jsonify(load_saved())

@app.route("/saved", methods=["POST"])
def saved_add():
    data  = _json_body()
    items = load_saved()
    entry = {
        "id":        str(int(time.time()*1000)),
        "name":      data.get("name","").strip() or data.get("query","Untitled"),
        "query":     data.get("query",""),
        "sources":   data.get("sources",[]),
        "year_from": data.get("year_from"),
        "year_to":   data.get("year_to"),
        "max_results": data.get("max_results", MAX_RESULTS_DEFAULT),
        "strict":    data.get("strict", True),
        "sort":      data.get("sort") if data.get("sort") in ("relevance", "date") else "relevance",
        "created":   datetime.now().strftime("%Y-%m-%d"),
    }
    # avoid exact duplicates (same name + query)
    if not any(s["name"] == entry["name"] and s["query"] == entry["query"] for s in items):
        items.append(entry)
        write_saved(items)
    return jsonify({"ok": True, "saved": items})

@app.route("/saved/clear", methods=["POST"])
def saved_clear():
    write_saved([])
    return jsonify({"ok": True, "saved": []})

@app.route("/saved/<sid>", methods=["DELETE"])
def saved_delete(sid):
    items = [s for s in load_saved() if s["id"] != sid]
    write_saved(items)
    return jsonify({"ok": True, "saved": items})

def _existing_instance():
    """(port, token) of a MedSearch already running on this machine, or None."""
    ports = []
    try:
        ports.append(int((CONFIG_DIR / "server_port").read_text().strip()))
    except Exception:
        pass
    if 5050 not in ports:
        ports.append(5050)
    for port in ports:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/ping", timeout=1.5) as r:
                if json.loads(r.read().decode()).get("app") == "medsearch":
                    token = (CONFIG_DIR / "server_token").read_text().strip()
                    return port, token
        except Exception:
            continue
    return None

def _post_local(port, token, path, payload):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json", "X-MedSearch-Token": token})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status == 200

# ── The installed launcher (macOS) ──────────────────────────────────────────
# MedSearch.app is a stub that runs launcher.sh from this folder (see there).
# Launchers built before launcher.sh existed exec'd Python directly, which is
# why macOS filed the app under "Python", and git pull never touches them. So a
# start through one rewrites it into the stub; the next start is MedSearch.
_LAUNCHER_STUB = (
    "#!/bin/bash\n"
    "# MedSearch launcher stub: the logic is in launcher.sh in the MedSearch folder.\n"
    'exec /bin/bash "{dir}/launcher.sh" "$(cd "$(dirname "$0")/../.." && pwd)" "$@"\n')

def _bundle_path_for(bundle_id):
    """Where macOS says that bundle is, or None. Asking Launch Services keeps
    this off the disk: searching folders for it can raise a privacy prompt,
    since the launcher usually sits on the Desktop."""
    try:
        from AppKit import NSWorkspace
        url = NSWorkspace.sharedWorkspace().URLForApplicationWithBundleIdentifier_(bundle_id)
        return Path(str(url.path())) if url is not None else None
    except Exception:
        return None


def _maintain_launcher(bundle_id, upgrade_stub):
    """Keep the installed MedSearch.app in step with this folder: convert an
    old-style launcher into the stub, and give it the current icon.

    Neither reaches it through git: the stub and the icon live inside the bundle.
    Its location comes from macOS, not from searching folders, so nothing else on
    the disk is touched (the Desktop is privacy-protected, and reading around in
    it can raise a prompt)."""
    if sys.platform != "darwin" or getattr(sys, "frozen", False):
        return
    if not bundle_id or not (APP_DIR_PATH / "launcher.sh").exists():
        return
    try:
        bundle = _bundle_path_for(bundle_id)
        if bundle is None:
            return
        changed = False

        if upgrade_stub:
            exe = bundle / "Contents" / "MacOS" / "MedSearch"
            text = exe.read_text()
            # Only a launcher for THIS folder, and only the old kind.
            if "launcher.sh" not in text and str(APP_DIR_PATH / "app.py") in text:
                exe.write_text(_LAUNCHER_STUB.format(dir=APP_DIR_PATH))
                exe.chmod(0o755)
                changed = True
                print(f"  launcher updated: {bundle}")

        icon_src = APP_DIR_PATH / "icon.icns"
        icon_dst = bundle / "Contents" / "Resources" / "MedSearch.icns"
        if icon_src.exists() and icon_dst.exists() and icon_src.read_bytes() != icon_dst.read_bytes():
            icon_dst.write_bytes(icon_src.read_bytes())
            changed = True
            print("  launcher icon updated")

        if changed:
            # Finder and the Dock cache icons per bundle; a touch plus a
            # re-register is what makes the new one appear.
            bundle.touch()
            subprocess.run(["/System/Library/Frameworks/CoreServices.framework/Frameworks/"
                            "LaunchServices.framework/Support/lsregister", "-f", str(bundle)],
                           capture_output=True, timeout=20)
    except Exception as e:
        print(f"  (couldn't update the launcher: {e})")

def _write_private(path, text):
    """Write a file only this user can read (the token file)."""
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)

if __name__ == "__main__":
    import socket, argparse

    # launcher.sh sets this to tell Python which virtual environment it runs
    # in. It has done its job once we are here, and must not reach the
    # processes MedSearch starts itself (pip during an update, a restart). Its
    # absence under a MedSearch launcher means an old-style launcher, which
    # exec'd Python directly. Keep both facts; the launcher is maintained
    # further down, once this launch knows it is the one that stays.
    _old_style_launcher = "__PYVENV_LAUNCHER__" not in os.environ
    os.environ.pop("__PYVENV_LAUNCHER__", None)

    # Optional deep-link args: open the window straight on a search. e.g.  python3 app.py --query "glioma" --source guidelines
    _parser = argparse.ArgumentParser(add_help=False)
    _parser.add_argument("--query", default="")
    _parser.add_argument("--source", default="")
    _parser.add_argument("--relaunch", action="store_true")   # restart after an update
    # Opened at login: start in the menu bar with the window hidden.
    _parser.add_argument("--background", action="store_true")
    _args, _ = _parser.parse_known_args()

    # ONE WINDOW. A second double-click used to start a second server on a
    # random port with a second window. Now it hands its request to the copy
    # that is already running (bring it forward, or run the search there) and
    # exits. After an update the old copy is still exiting, so a relaunch
    # skips this check.
    if not _args.relaunch:
        _running = _existing_instance()
        if _running:
            _port, _token = _running
            try:
                if _args.query.strip():
                    _post_local(_port, _token, "/queue_search",
                                {"query": _args.query.strip(), "source": _args.source.strip()})
                # A background launch (opened at login, while a copy is already
                # running) must not pull that copy's window up: the point of
                # --background is that nothing appears.
                if not _args.background:
                    _post_local(_port, _token, "/focus", {})
            except Exception:
                pass
            sys.exit(0)

    # Only the launch that stays maintains the installed launcher: a launch
    # that hands its query to a running copy has already exited above, and
    # keeping this off that path leaves the handoff instant (it reads the
    # bundle, compares the icon and can call lsregister).
    _maintain_launcher(_launcher_bundle_id(), _old_style_launcher)

    # Find a free port (in case 5050 is taken). A relaunch waits briefly for
    # the previous copy to release 5050 rather than moving to a random port.
    def free_port(preferred=5050, wait=0.0):
        deadline = time.time() + wait
        while True:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.bind(("127.0.0.1", preferred)); s.close(); return preferred
            except OSError:
                s.close()
                if time.time() >= deadline:
                    break
                time.sleep(0.25)
        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s2.bind(("127.0.0.1", 0)); port = s2.getsockname()[1]; s2.close(); return port

    PORT = free_port(5050, wait=10.0 if _args.relaunch else 0.0)
    # If launched with a query, point the window straight at the search.
    if _args.query.strip():
        _qs = urllib.parse.urlencode({"q": _args.query.strip(),
                                      "src": (_args.source or "").strip()})
        URL = f"http://127.0.0.1:{PORT}/?{_qs}"
    else:
        URL = f"http://127.0.0.1:{PORT}"

    # Record the chosen port and this launch's token so a second launch can
    # find this server and hand it its request. Best-effort.
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        (CONFIG_DIR / "server_port").write_text(str(PORT))
        _write_private(CONFIG_DIR / "server_token", APP_TOKEN)
    except Exception:
        pass

    def run_server():
        app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True, use_reloader=False)

    # Try to open a native window via pywebview; fall back to a browser tab.
    try:
        import webview  # pywebview

        # JS-callable API: lets the page open a real in-app browser window for
        # any URL the server can't fetch directly (publisher pages, paywalled
        # PDFs via the library proxy, JS-rendered viewers). This window is a
        # full browser — it runs JavaScript and carries the user's login
        # session/cookies, so institutional access and paywalls just work.
        class Api:
            def open_external(self, url, title=None):
                try:
                    if not url or not str(url).lower().startswith(("http://", "https://")):
                        return {"ok": False, "error": "bad url"}
                    webview.create_window(
                        title or "MedSearch — Article",
                        url,
                        width=1100, height=860,
                        min_size=(800, 600),
                    )
                    return {"ok": True}
                except Exception as e:
                    return {"ok": False, "error": str(e)}

        api = Api()
        # Start Flask in a background thread
        t = threading.Thread(target=run_server, daemon=True)
        t.start()
        print(f"\n  🔬  MedSearch {LOCAL_VERSION}  —  native window on {URL}\n")
        _MAIN_WINDOW = webview.create_window(
            "MedSearch",
            URL,
            width=1280, height=860,
            min_size=(940, 640),
            js_api=api,
            hidden=_args.background,
        )

        def _start_statusbar():
            """The menu bar item (macOS). Runs in pywebview's start thread; the
            item itself is built on the main thread once the window exists."""
            if sys.platform != "darwin":
                return
            try:
                import statusbar
                from PyObjCTools import AppHelper
                from webview.platforms.cocoa import BrowserView
            except Exception as e:
                print(f"  (menu bar item unavailable: {e})")
                return
            for _ in range(100):                      # up to 10 s for the window
                if _MAIN_WINDOW.uid in BrowserView.instances:
                    break
                time.sleep(0.1)

            def _history_newest_first():
                seen, out = set(), []
                for q in reversed(SESSION["history"]):
                    if q not in seen:
                        seen.add(q); out.append(q)
                return out

            def _set_default_source(key):
                CONFIG["default_source"] = key
                save_config(CONFIG)

            def _install():
                global _STATUSBAR
                try:
                    _STATUSBAR = statusbar.install(
                        _MAIN_WINDOW, background=_args.background,
                        icon_path=RESOURCE_DIR / "menubar_icon.png",
                        log_path=CONFIG_DIR / "menubar.log",
                        recent_searches=_history_newest_first,
                        get_source=lambda: CONFIG.get("default_source", "pubmed"),
                        set_source=_set_default_source)
                    print("  menu bar item ready")
                except Exception as e:
                    print(f"  (menu bar item failed: {e})")
            AppHelper.callAfter(_install)
        # Persist the embedded browser's cookies and session so an institutional
        # login carries across every article window AND survives app restarts —
        # log in once, not for every paper. By default pywebview runs in private
        # mode (no cookies saved), which is why each window asked to log in again.
        # If this pywebview build doesn't support these options, fall back to a
        # plain start so the app still launches (just without persisted login).
        try:
            browser_data_dir = str(CONFIG_DIR / "browser_data")
            os.makedirs(browser_data_dir, exist_ok=True)
            webview.start(_start_statusbar, private_mode=False, storage_path=browser_data_dir)
        except TypeError:
            webview.start(_start_statusbar)
    except ImportError:
        import webbrowser
        print(f"\n  🔬  MedSearch {LOCAL_VERSION}  —  starting…")
        print("  (pywebview not installed — opening in browser instead)")
        print(f"  Open: {URL}\n")
        threading.Timer(1.2, lambda: webbrowser.open(URL)).start()
        run_server()
