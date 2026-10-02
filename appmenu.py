# MedSearch — what its menu bar item and its tray icon both offer.
# Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
"""The parts of MedSearch's menu that do not depend on the system: the sources a
quick search can target, how a search is handed to the page, and how a close
asks the page first. statusbar.py draws them in the macOS menu bar, tray.py by
the Windows clock; both import them from here, so the two menus cannot drift.
"""
from __future__ import annotations

import json
import threading

# The sources a quick search can target (key, label), in the order the menu lists them.
SOURCES = [
    ("pubmed",         "PubMed"),
    ("guidelines",     "Guidelines"),
    ("cochrane",       "Cochrane"),
    ("clinicaltrials", "ClinicalTrials.gov"),
    ("arxiv",          "arXiv"),
    ("scopus",         "Scopus"),
    ("wos",            "Web of Science"),
    ("europepmc",      "Europe PMC"),
    ("openalex",       "OpenAlex"),
    ("crossref",       "Crossref"),
    ("core",           "CORE"),
    ("ieee",           "IEEE Xplore"),
    ("semanticscholar", "Semantic Scholar"),
    ("all",            "All sources"),
]
LABELS = dict(SOURCES)
RECENTS_SHOWN = 6
PAGE_ANSWER_WAIT = 1.0     # seconds a close waits for the page to say it closed a dialog

QUICK_SEARCH_TITLE = "MedSearch quick search"


def quick_search_hint(source: str) -> str:
    return (f"Search {LABELS.get(source, 'PubMed')} "
            "(change the source under Default source in this menu).")


def short(query: str) -> str:
    """A recent search as a menu shows it."""
    return query if len(query) <= 60 else query[:57] + "…"


def search_js(query: str, source: str) -> str:
    """What runs a search in the page, as the page's own Search does."""
    return f"runSearchWithSource({json.dumps(query)}, {json.dumps(source)}, 0)"


def page_closed_a_dialog(window, wait: float = PAGE_ANSWER_WAIT) -> bool:
    """Ask the page to close its top dialog (the PDF viewer, Settings…); True only
    when it says it did. An answer that is not a plain yes (none within `wait`, a
    blank or reloading page, an error) counts as nothing open, so the window can
    always be closed. Call it off the GUI thread: evaluate_js needs that thread."""
    answer = []

    def ask():
        try:
            answer.append(window.evaluate_js(
                "typeof closeTopDialog === 'function' && closeTopDialog() === true"))
        except Exception:
            pass

    t = threading.Thread(target=ask, daemon=True)
    t.start()
    t.join(wait)
    return bool(answer) and answer[0] is True
