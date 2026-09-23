# MedSearch — improvements asked for on 23 September 2026

From using MedSearch as a library (`import app`) for literature work on TRACTomator: a bibliography of the
Trento group's papers for the method guides, and a prior-art check on streamline warping. In order of value.

## 1. "Cited by" — forward citations
**Why:** a prior-art sweep ("has anyone done X since paper P?") is best done forwards: who cites P. Keyword
searches miss work that uses other words for the same idea. Today's example: who cites Tractome
(doi:10.1007/s10618-015-0408-z) and BundleWarp (doi:10.1016/j.media.2026.104114).
**What:** a function (and a route/UI entry if it fits the app) that takes a DOI and returns the works citing it,
as ordinary article records. Scopus offers this through its API with the key already configured (a `REFEID`
search, or the citing-documents query). Any other source that can answer cheaply is welcome: e.g. PubMed's
"cited in" through NCBI elink `pubmed_pubmed_citedin`, which needs no new key. Merge across sources by DOI/PMID.

**Status (1.16): done.** `app.cited_by(doi)` asks PubMed (elink "cited in", no key) and Scopus (`DOI()` for the
EID, then `REFEID()`), merges them, newest first, and reports each source as ok / no key / not indexed / failed.
In the window, the citation graph's "Cited by" column now merges these with OpenCitations. Not built: a separate
result list of citing papers in the window (the graph already had a place for them). Live check: Tractome is not
in PubMed ("not indexed", correctly), and Scopus could not be reached from the machine the check ran on, so the
Scopus parsing is checked by tests only.

## 2. Scopus records with their abstracts
**Why:** Scopus results carry no abstract, so every Scopus-only hit needs a second, manual PubMed lookup by DOI
(`search_pubmed('"<doi>"[AID]', ...)`) before it can be judged.
**What:** fill a Scopus record's `abstract` automatically, for example from PubMed by DOI when the record has one,
batched (one E-utilities call for many DOIs, not one per record). Records that have no PubMed counterpart keep an
empty abstract, marked as such, never an error. Keep it within the rate limits the app already respects.

**Status (1.16): done.** Every Scopus search (and Scopus's "cited by") fills abstracts through
`app.fill_abstracts_from_pubmed`: one esearch + one efetch per 50 DOIs, through the shared NCBI limiter. A record
left without one carries `abstract_note` (no DOI / not in PubMed / in PubMed without abstract / PubMed could not
be asked, with the reason); the window shows it on the card. The record also takes PubMed's PMID, retraction flag
and publication types.

## 3. A compact, merged output mode
**Why:** a multi-source search returns the same paper several times and long records; reading them costs about
twice what a merged list would.
**What:** one function that runs a query across the chosen sources and returns ONE list, deduplicated by
DOI > PMID > normalised title, each entry keeping the set of sources that found it, and a per-source count
**including failures stated as failures**. A source that errored must never look like a source that found
nothing. A compact form (year · first author · journal · title · DOI · sources) for printing.

**Status (1.16): done, as library functions only.** `app.merged_search(query, sources=…, keywords=…)` returns
one list (`found_in` on each entry) and a report per source; `app.merge_articles` does the dedup;
`app.compact_report(result)` / `app.compact_line(article)` print it. The window's own search already dedups and
reports failures, so it is unchanged.

## Known traps to handle while there (from earlier use)
- Long natural-language queries work only in Scopus; PubMed and Web of Science want short keyword queries. The
  merged search may accept both forms, or say which it used per source.
- Scopus rejects `max_results` above 25.
- `search_wos` takes no `strict` argument, although `SOURCES` rows carry a `takes_strict` flag.
- Web of Science has no key configured; it should report "no key", not "0 results".

**Status (1.16):** all four handled in `merged_search`: `keywords=` goes to every source but Scopus, and each
report says what was sent; Scopus is asked in pages of 25 (in `search_scopus` itself, so the window gains it
too); `strict` is passed only where the row's flag says so; a missing key is status "no key".

**Checked live on his machine, 23 Sep (after the agent's report):** Scopus's cited-by cannot work with his key:
`REFEID` is refused with "Use of certain field restrictions in the search query is not allowed for this
requestor" — an entitlement of the key, not a bug. `DOI()` lookups work. The app used to hide Scopus's own reason
behind "likely a query-syntax issue"; `_scopus_get` now passes Scopus's statusText on, and names this case
(test added; 132 pass). Cited-by therefore rests on PubMed's "cited in" and OpenCitations until the key gains the
entitlement (a question for the library / Elsevier).
