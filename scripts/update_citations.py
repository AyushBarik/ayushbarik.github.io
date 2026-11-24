"""Builds data/citations.json, the citation numbers shown on the home page.

For every paper on index.html that has citation buttons, this collects the list of papers citing
it from up to three sources, then merges the lists so a citing paper found by several sources
counts once:

  - Semantic Scholar (free API, no key)
  - OpenAlex (free API, no key)
  - Google Scholar, through SerpApi (needs SERPAPI_KEY; skipped when it is not set)

Citing papers are matched by DOI, arXiv ID or title. Google Scholar shortens some long titles
with an ellipsis, so a title also matches a longer one that starts with it.

Papers are read from index.html: each <li id="paperN"> with a Semantic Scholar button
(data-s2-paper) and/or an OpenAlex button (data-oa-work). Google Scholar papers are matched to
them by title from the author profile.

SerpApi searches are limited (the free plan allows 250 a month), so Google Scholar is read
sparingly:

  - One search reads the author profile, which gives every paper's "Cited by" count (up to 100
    papers). A paper whose count has not changed keeps its saved citing list, so a quiet day
    costs one search no matter how many papers there are.
  - When a count goes up, only the new citing papers are fetched: the paper's "Cited by" results
    sorted newest first, one page of 20 per search, stopping at the first already-saved paper.
    So a change costs one search however many citations the paper has.
  - The whole list is fetched again (one search per 20 citing papers) only for a paper with no
    saved list, a count that went down, or new citing papers the newest-first results did not
    show.
  - Each run first checks the searches left on the account (free), and spends at most 1/30 of
    them, keeping a few in reserve. Updates that do not fit wait for a later run, cheapest first,
    so the quota is never used up.

If a source fails, the last saved data for that source is kept.

Usage: python3 scripts/update_citations.py
"""

import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
OUT = os.path.join(ROOT, "data", "citations.json")

S2_AUTHOR = "2205313776"
GS_AUTHOR = "4lZA3SUAAAAJ"

SERPAPI = "https://serpapi.com/search.json?"
GS_PAGE = 20  # Google Scholar results per search, the most SerpApi returns
GS_RESERVE = 5  # SerpApi searches never spent by this script, kept for manual runs


def serpapi_key():
    """The SerpApi key: SERPAPI_KEY from the environment (as in the GitHub Action), or else from
    serp.env next to index.html, which holds either a KEY=value line or the bare key. The key is
    only passed to SerpApi; it is never printed."""
    key = os.environ.get("SERPAPI_KEY")
    if key:
        return key
    path = os.path.join(ROOT, "serp.env")
    if not os.path.exists(path):
        return None
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        value = line.split("=", 1)[1] if "=" in line else line
        return value.strip().strip("'\"") or None
    return None


def redact(text, secret):
    return str(text).replace(secret, "***") if secret else str(text)


def get_json(url, retries=4):
    """GET a URL as JSON, waiting and retrying on rate limits (429) and server errors."""
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "citation-updater"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if attempt == retries or (error.code != 429 and error.code < 500):
                raise
        except urllib.error.URLError:
            if attempt == retries:
                raise
        time.sleep(5 * (attempt + 1))


def norm_title(title):
    return re.sub(r"[^a-z0-9]", "", html.unescape(title or "").lower())


def read_papers():
    """The listed papers, from the citation buttons on index.html."""
    page = open(INDEX, encoding="utf-8").read()
    papers = []
    for match in re.finditer(r'<li id="(paper\d+)"(.*?)</li>', page, re.S):
        key, body = match.groups()
        s2 = re.search(r'data-s2-paper="([^"]+)"', body)
        oa = re.search(r'data-oa-work="([^"]+)"', body)
        title = re.search(r'class="paper-title"[^>]*>(.*?)</a>', body, re.S)
        if s2 or oa:
            papers.append({
                "key": key,
                "title": html.unescape(re.sub(r"<[^>]+>", "", title.group(1))) if title else "",
                "s2": s2 and s2.group(1),
                "oa": oa and oa.group(1),
            })
    return papers


def fetch_s2(papers):
    """{paper key: [citing paper, ...]} from Semantic Scholar, in one request."""
    data = get_json(
        f"https://api.semanticscholar.org/graph/v1/author/{S2_AUTHOR}/papers"
        "?fields=citations.title,citations.externalIds&limit=100"
    )
    by_id = {p["paperId"]: p.get("citations") or [] for p in data["data"]}
    lists = {}
    for paper in papers:
        if paper["s2"] in by_id:
            lists[paper["key"]] = [
                {
                    "title": c.get("title"),
                    "doi": (c.get("externalIds") or {}).get("DOI"),
                    "arxiv": (c.get("externalIds") or {}).get("ArXiv"),
                }
                for c in by_id[paper["s2"]]
            ]
    return lists


def fetch_oa(papers):
    """{paper key: [citing work, ...]} from OpenAlex, following result pages with a cursor."""
    works = {p["oa"]: p["key"] for p in papers if p["oa"]}
    lists = {key: [] for key in works.values()}
    cursor = "*"
    while cursor:
        data = get_json(
            "https://api.openalex.org/works?" + urllib.parse.urlencode({
                "filter": "cites:" + "|".join(works),
                "select": "display_name,doi,referenced_works",
                "per-page": 200,
                "cursor": cursor,
            })
        )
        for work in data["results"]:
            citing = {"title": work.get("display_name"), "doi": work.get("doi")}
            for ref in work.get("referenced_works") or []:
                key = works.get(ref.rsplit("/", 1)[-1])
                if key:
                    lists[key].append(citing)
        cursor = data["meta"].get("next_cursor") if data["results"] else None
    return lists


def gs_budget(api_key):
    """How many SerpApi searches this run may spend: 1/30 of the searches left on the account
    after a small reserve, but at least 2 (the profile and one update) while that many are left
    above the reserve. Spending a share of what is left never touches the reserve, whatever day
    the monthly quota resets. Checking the account does not use a search."""
    try:
        account = get_json("https://serpapi.com/account.json?" + urllib.parse.urlencode(
            {"api_key": api_key}), retries=1)
        left = int(account["total_searches_left"])
    except Exception as error:
        print(f"SerpApi account check failed, spending at most 2 searches: {redact(error, api_key)}",
              file=sys.stderr)
        return 2
    spare = left - GS_RESERVE
    return max(min(spare, 2), spare // 30) if spare > 0 else 0


def gs_search(params, api_key):
    return get_json(SERPAPI + urllib.parse.urlencode({**params, "api_key": api_key}))


def gs_citing(result):
    """A citing paper from one Google Scholar result, with any arXiv ID or DOI in its link."""
    link = result.get("link") or ""
    arxiv = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", link)
    doi = re.search(r"doi\.org/(10\.[^?#]+)", link)
    return {"title": result.get("title"), "arxiv": arxiv and arxiv.group(1), "doi": doi and doi.group(1)}


def gs_all_citing(cites_id, api_key, max_searches):
    """Every citing paper of one paper, in relevance order, reading at most `max_searches` pages.
    Returns (papers, searches)."""
    citing, start, searches = [], 0, 0
    while searches < max_searches:
        results = gs_search({"engine": "google_scholar", "cites": cites_id, "num": GS_PAGE,
                             "start": start}, api_key).get("organic_results", [])
        searches += 1
        citing.extend(gs_citing(r) for r in results)
        if len(results) < GS_PAGE:
            break
        start += GS_PAGE
    return citing, searches


def gs_new_citing(cites_id, known, wanted, api_key, max_searches):
    """Citing papers of one paper that are not in `known`, read newest first (scisbd=2: sorted
    by date added, abstracts and full papers both) until `wanted` are found, an already-known
    paper shows up (everything after it is older), the results run out, or `max_searches` is
    reached. Returns (new papers, searches)."""
    seen = [record(p) for p in known]
    new, start, searches = [], 0, 0
    while searches < max_searches:
        results = gs_search({"engine": "google_scholar", "cites": cites_id, "scisbd": 2,
                             "num": GS_PAGE, "start": start}, api_key).get("organic_results", [])
        searches += 1
        reached_known = False
        for result in results:
            citing = gs_citing(result)
            rec = record(citing)
            if any(same_paper(rec, s) for s in seen):
                reached_known = True
                continue
            new.append(citing)
            seen.append(rec)
        if len(new) >= wanted or reached_known or len(results) < GS_PAGE:
            break
        start += GS_PAGE
    return new, searches


def pages(n):
    return -(-n // GS_PAGE)


def fetch_gs(papers, api_key, previous, budget):
    """Google Scholar data through SerpApi, spending at most `budget` searches.

    Returns (lists, profile, counts, searches): {paper key: [citing paper, ...]}, the profile's
    own citations / h-index / i10-index, each paper's "Cited by" count that its list matches,
    and how many searches were used. A paper whose update does not fit the budget keeps its
    saved list and count, so the next run sees the change again and picks it up.
    """
    author = gs_search({"engine": "google_scholar_author", "author_id": GS_AUTHOR, "num": 100},
                       api_key)
    spent = 1
    table = {}
    for row in author.get("cited_by", {}).get("table", []):
        for name, values in row.items():
            table[name] = values.get("all")
    profile = {"citations": table.get("citations"), "h": table.get("h_index"), "i10": table.get("i10_index")}

    by_title = {norm_title(a.get("title")): a for a in author.get("articles", [])}
    old_lists = previous.get("lists", {}).get("gs", {})
    old_counts = previous.get("gs_cited_by", {})
    lists, counts, changed = {}, {}, []
    for paper in papers:
        key = paper["key"]
        article = by_title.get(norm_title(paper["title"]))
        if not article:
            if key in old_lists:  # Missing from this response: keep what was saved.
                lists[key] = old_lists[key]
                if key in old_counts:
                    counts[key] = old_counts[key]
            continue
        cited = article.get("cited_by") or {}
        count = cited.get("value") or 0
        old, old_count = old_lists.get(key), old_counts.get(key)
        if count == 0:
            lists[key], counts[key] = [], 0
        elif old is not None and old_count == count:
            lists[key], counts[key] = old, count
        else:
            # Newest-first reading only works for new citations added to a saved list.
            incremental = old is not None and old_count is not None and count > old_count
            cost = pages(count - old_count) if incremental else pages(count)
            changed.append((cost, key, count, cited.get("cites_id"), old, old_count, incremental))

    for cost, key, count, cites_id, old, old_count, incremental in sorted(changed, key=lambda c: c[0]):
        def keep_old():
            if old is not None:
                lists[key] = old
                if old_count is not None:
                    counts[key] = old_count

        if not cites_id or spent + cost > budget:
            print(f"gs: {key} changed to {count}, waiting for a later run (needs {cost} searches)")
            keep_old()
            continue
        if incremental:
            new, used = gs_new_citing(cites_id, old, count - old_count, api_key, budget - spent)
            spent += used
            if len(new) >= count - old_count:
                lists[key], counts[key] = new + old, count
                print(f"gs: {key} {old_count} -> {count}, read {len(new)} new citing papers in {used} searches")
                continue
            # Not all new citing papers showed up newest first: read the whole list if it fits.
            if spent + pages(count) > budget:
                print(f"gs: {key} found {len(new)} of {count - old_count} new citing papers, "
                      "reading the whole list on a later run")
                keep_old()
                continue
        citing, used = gs_all_citing(cites_id, api_key, budget - spent)
        spent += used
        lists[key], counts[key] = citing, count
        print(f"gs: {key} -> {count}, read the whole list ({len(citing)} papers) in {used} searches")
    return lists, profile, counts, spent


def same_paper(a, b):
    """Whether two citing-paper records are the same paper."""
    for field in ("doi", "arxiv"):
        if a[field] & b[field]:
            return True
    ta, tb = a["title"], b["title"]
    if not ta or not tb:
        return False
    if ta == tb:
        return True
    short, full = sorted((ta, tb), key=len)
    # A title Google Scholar shortened with an ellipsis matches a longer one it begins.
    if (a["cut"] or b["cut"]) and len(short) >= 30 and full.startswith(short):
        return True
    # A long title matches one that adds a prefix or subtitle around it, as in
    # "Nuha: Clean-Room Verification of ..." and "Clean-Room Verification of ...".
    return len(short) >= 40 and short in full


def record(paper):
    title = paper.get("title") or ""
    doi = (paper.get("doi") or "").lower().replace("https://doi.org/", "")
    arxiv = {paper["arxiv"].lower()} if paper.get("arxiv") else set()
    arxiv_doi = re.match(r"10\.48550/arxiv\.(.+)", doi)
    if arxiv_doi:
        arxiv.add(arxiv_doi.group(1))
    return {
        "title": norm_title(title),
        "cut": title.rstrip().endswith(("…", "...")),
        "doi": {doi} if doi else set(),
        "arxiv": arxiv,
    }


def distinct_count(lists):
    """Number of distinct citing papers across several lists, merging records as they match."""
    groups = []
    for citing in (record(p) for lst in lists for p in lst):
        matches = [g for g in groups if any(same_paper(citing, m) for m in g)]
        merged = [citing]
        for group in matches:
            merged.extend(group)
            groups.remove(group)
        groups.append(merged)
    return len(groups)


def metrics(counts):
    ranked = sorted(counts, reverse=True)
    return {
        "citations": sum(ranked),
        "h": sum(1 for i, c in enumerate(ranked) if c >= i + 1),
        "i10": sum(1 for c in ranked if c >= 10),
    }


def main():
    papers = read_papers()
    try:
        previous = json.load(open(OUT, encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    old_lists = previous.get("lists", {})
    lists, failed = {}, []

    for name, fetch in (("s2", fetch_s2), ("oa", fetch_oa)):
        try:
            lists[name] = fetch(papers)
        except Exception as error:  # Keep the last good data for a source that fails.
            failed.append(name)
            print(f"{name} failed, keeping previous data: {error}", file=sys.stderr)
            if name in old_lists:
                lists[name] = old_lists[name]

    gs_profile = previous.get("gs_profile")
    gs_counts = previous.get("gs_cited_by", {})
    api_key = serpapi_key()
    budget = gs_budget(api_key) if api_key else 0
    if api_key and budget < 1:
        print("SerpApi: no searches left above the reserve, keeping previous Google Scholar data")
    if budget >= 1:
        try:
            lists["gs"], gs_profile, gs_counts, searches = fetch_gs(papers, api_key, previous, budget)
            print(f"SerpApi searches used: {searches} (budget for this run: {budget})")
        except Exception as error:
            failed.append("gs")
            print(f"gs failed, keeping previous data: {redact(error, api_key)}", file=sys.stderr)
            if "gs" in old_lists:
                lists["gs"] = old_lists["gs"]
    elif "gs" in old_lists:
        lists["gs"] = old_lists["gs"]

    sources = [s for s in ("gs", "s2", "oa") if s in lists]
    per_paper = {}
    for paper in papers:
        entry = {s: len(lists[s][paper["key"]]) for s in sources if paper["key"] in lists[s]}
        # The Google Scholar button shows Scholar's own "Cited by" number, which can be a little
        # higher than the results it lists.
        if "gs" in entry and paper["key"] in gs_counts:
            entry["gs"] = gs_counts[paper["key"]]
        entry["combined"] = distinct_count(
            [lists[s][paper["key"]] for s in sources if paper["key"] in lists[s]]
        )
        per_paper[paper["key"]] = entry

    result = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "sources": sources,
        "totals": metrics([p["combined"] for p in per_paper.values()]),
        "papers": per_paper,
        "gs_profile": gs_profile,
        "gs_cited_by": gs_counts,
        "lists": lists,
    }
    # Leave the file alone when nothing but the date changed, so no empty commits are made.
    unchanged = {k: v for k, v in previous.items() if k != "updated"} == \
        {k: v for k, v in result.items() if k != "updated"}
    if not unchanged:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=1, ensure_ascii=False)
            f.write("\n")
    print(json.dumps({"sources": sources, "totals": result["totals"], "papers": per_paper}, indent=1))
    if failed and not lists:
        sys.exit(1)


if __name__ == "__main__":
    main()
