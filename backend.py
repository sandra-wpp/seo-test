import pandas as pd
import math
import io
import zipfile
from pathlib import Path


# ─── SEO Issue Definitions ────────────────────────────────────────────────────
# base_impact: 1-10 (SEO best practice severity)
# effort: Low / Medium / High (implementation cost)

SEO_ISSUES = {
    "broken_links": {
        "label": "Broken Internal Links (4xx)",
        "base_impact": 10,
        "category": "Crawlability",
        "effort": "Medium",
        "recommendation": (
            "{count} page(s) return a 4xx error and are unreachable by users and search engines. "
            "Fix or redirect each broken URL. Example: '{example}' returns a client error. "
            "Set up a 301 redirect to the correct destination or update the link."
        ),
    },
    "missing_title": {
        "label": "Missing Page Title",
        "base_impact": 9,
        "category": "On-Page SEO",
        "effort": "Low",
        "recommendation": (
            "{count} page(s) have no <title> tag. Titles are one of the strongest on-page SEO signals. "
            "Example: '{example}' — add a unique, descriptive title of 50-60 characters."
        ),
    },
    "duplicate_title": {
        "label": "Duplicate Page Title",
        "base_impact": 8,
        "category": "On-Page SEO",
        "effort": "Medium",
        "recommendation": (
            "{count} page(s) share identical title tags, causing keyword cannibalisation. "
            "Example: '{example}' — each page needs a unique title."
        ),
    },
    "missing_h1": {
        "label": "Missing H1 Tag",
        "base_impact": 8,
        "category": "On-Page SEO",
        "effort": "Low",
        "recommendation": (
            "{count} page(s) have no H1 tag. H1 tells search engines what the page is about. "
            "Example: '{example}' — add one clear H1 per page that matches the page topic and target keyword."
        ),
    },
    "multiple_h1": {
        "label": "Multiple H1 Tags",
        "base_impact": 6,
        "category": "On-Page SEO",
        "effort": "Low",
        "recommendation": (
            "{count} page(s) have more than one H1. Use exactly one H1 per page. "
            "Example: '{example}' — demote secondary headings to H2."
        ),
    },
    "missing_meta_description": {
        "label": "Missing Meta Description",
        "base_impact": 7,
        "category": "On-Page SEO",
        "effort": "Low",
        "recommendation": (
            "{count} page(s) have no meta description. While not a direct ranking factor, "
            "this reduces click-through rate from search results. "
            "Example: '{example}' — write a compelling 120-160 character summary."
        ),
    },
    "duplicate_meta_description": {
        "label": "Duplicate Meta Description",
        "base_impact": 6,
        "category": "On-Page SEO",
        "effort": "Medium",
        "recommendation": (
            "{count} page(s) share identical meta descriptions. "
            "Example: '{example}' — write a unique meta description per page."
        ),
    },
    "title_too_long": {
        "label": "Page Title Too Long (>60 chars)",
        "base_impact": 5,
        "category": "On-Page SEO",
        "effort": "Low",
        "recommendation": (
            "{count} title(s) exceed 60 characters and will be truncated in search results. "
            "Example: '{example}' — shorten to 50-60 characters."
        ),
    },
    "title_too_short": {
        "label": "Page Title Too Short (<30 chars)",
        "base_impact": 4,
        "category": "On-Page SEO",
        "effort": "Low",
        "recommendation": (
            "{count} title(s) are under 30 characters and underutilise the tag. "
            "Example: '{example}' — expand to 50-60 characters to include the target keyword."
        ),
    },
    "missing_canonical": {
        "label": "Missing Canonical Tag",
        "base_impact": 7,
        "category": "Technical SEO",
        "effort": "Low",
        "recommendation": (
            "{count} page(s) have no canonical tag, leaving Google to guess the preferred URL. "
            "Example: '{example}' — add <link rel='canonical' href='[url]'> in the <head>."
        ),
    },
    "non_canonical_inlinked": {
        "label": "Non-Canonical Pages Receiving Internal Links",
        "base_impact": 8,
        "category": "Technical SEO",
        "effort": "Medium",
        "recommendation": (
            "{count} non-canonical page(s) are receiving internal links, wasting link equity. "
            "Example: '{example}' — update internal links to point directly to the canonical URL."
        ),
    },
    "redirect_chain": {
        "label": "Redirect Chains (3xx)",
        "base_impact": 7,
        "category": "Technical SEO",
        "effort": "Medium",
        "recommendation": (
            "{count} redirect(s) detected. Chains dilute PageRank and slow page load. "
            "Example: '{example}' — consolidate to a single 301 redirect to the final URL."
        ),
    },
    "noindex_pages": {
        "label": "Pages with Noindex Directive",
        "base_impact": 6,
        "category": "Crawlability",
        "effort": "Low",
        "recommendation": (
            "{count} page(s) are blocked from indexing via noindex. "
            "Example: '{example}' — verify each page intentionally excludes itself from search results."
        ),
    },
    "thin_content": {
        "label": "Thin Content (< 300 Words)",
        "base_impact": 6,
        "category": "Content",
        "effort": "High",
        "recommendation": (
            "{count} page(s) have fewer than 300 words. Thin pages rank poorly and may be devalued. "
            "Example: '{example}' — expand the content, merge with a related page, or add a noindex directive."
        ),
    },
    "missing_alt_text": {
        "label": "Images Missing Alt Text",
        "base_impact": 5,
        "category": "Accessibility & SEO",
        "effort": "Low",
        "recommendation": (
            "{count} image(s) have no alt attribute, missing an opportunity for image search visibility "
            "and failing accessibility standards. "
            "Example: '{example}' — add descriptive alt text to every content image."
        ),
    },
    "http_pages": {
        "label": "Internal Pages on HTTP (Not HTTPS)",
        "base_impact": 7,
        "category": "Technical SEO",
        "effort": "Low",
        "recommendation": (
            "{count} internal URL(s) are served over HTTP instead of HTTPS. "
            "Example: '{example}' — enforce HTTPS sitewide and update all internal links."
        ),
    },
    "low_word_count": {
        "label": "Very Low Word Count (< 100 Words)",
        "base_impact": 5,
        "category": "Content",
        "effort": "High",
        "recommendation": (
            "{count} page(s) have fewer than 100 words and are essentially empty. "
            "Example: '{example}' — add meaningful content or noindex/redirect the page."
        ),
    },
}


# ─── Column name normalisation ────────────────────────────────────────────────
# Screaming Frog CSV column names vary slightly between versions and export types.
# This maps common variants to a canonical name.

COL_MAP = {
    "address": "Address",
    "url": "Address",
    "status code": "Status Code",
    "status_code": "Status Code",
    "indexability": "Indexability",
    "indexability status": "Indexability Status",
    "title 1": "Title 1",
    "title": "Title 1",
    "title 1 length": "Title 1 Length",
    "title length": "Title 1 Length",
    "meta description 1": "Meta Description 1",
    "meta description": "Meta Description 1",
    "meta description 1 length": "Meta Description 1 Length",
    "h1-1": "H1-1",
    "h1 1": "H1-1",
    "h1-1 length": "H1-1 Length",
    "h1-2": "H1-2",
    "canonical link element 1": "Canonical Link Element 1",
    "canonical": "Canonical Link Element 1",
    "word count": "Word Count",
    "inlinks": "Inlinks",
    "outlinks": "Outlinks",
    "alt text": "Alt Text",
    "alt": "Alt Text",
    "src": "Src",
    "source": "Src",
    "redirect url": "Redirect URL",
}


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise column names to canonical Screaming Frog names."""
    df.columns = [c.strip() for c in df.columns]
    rename = {}
    for col in df.columns:
        mapped = COL_MAP.get(col.lower())
        if mapped and mapped not in df.columns:
            rename[col] = mapped
    return df.rename(columns=rename)


# ─── CSV loading ──────────────────────────────────────────────────────────────

def load_csv_bytes(data: bytes, filename: str = "") -> pd.DataFrame:
    """Load a CSV from raw bytes, normalise columns."""
    try:
        df = pd.read_csv(io.BytesIO(data), encoding="utf-8", low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(io.BytesIO(data), encoding="latin-1", low_memory=False)
    return normalise_columns(df)


def load_dbseospider(file_bytes: bytes) -> dict[str, pd.DataFrame]:
    """
    Extract CSVs from a .dbseospider ZIP export.
    Screaming Frog does NOT embed CSVs in the ZIP — the ZIP contains a Derby DB.
    This function returns an empty dict and is kept as a fallback.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            csvs = {}
            for name in z.namelist():
                if name.lower().endswith(".csv"):
                    csvs[Path(name).stem.lower()] = load_csv_bytes(z.read(name), name)
            return csvs
    except Exception:
        return {}


# ─── Analysis ─────────────────────────────────────────────────────────────────

def analyse(df: pd.DataFrame) -> list[dict]:
    """
    Run all SEO checks against the internal HTML dataframe.
    Returns a list of issue dicts, sorted by priority score descending.
    """
    issues = []

    def col(name):
        return name in df.columns

    def first_urls(mask, n=3):
        if "Address" not in df.columns:
            return []
        return df.loc[mask, "Address"].dropna().head(n).tolist()

    # Filter to 200 OK HTML pages as the base set where applicable
    if col("Status Code"):
        ok = df["Status Code"] == 200
    else:
        ok = pd.Series(True, index=df.index)

    if col("Content Type"):
        html = df["Content Type"].str.contains("text/html", na=False, case=False)
        ok = ok & html

    # ── Broken links ──────────────────────────────────────────────────────────
    if col("Status Code"):
        mask = (df["Status Code"] >= 400) & (df["Status Code"] < 500)
        if mask.sum():
            issues.append(_build("broken_links", mask.sum(), first_urls(mask)))

    # ── Missing title ─────────────────────────────────────────────────────────
    if col("Title 1"):
        mask = ok & (df["Title 1"].isna() | (df["Title 1"].str.strip() == ""))
        if mask.sum():
            issues.append(_build("missing_title", mask.sum(), first_urls(mask)))

    # ── Duplicate title ───────────────────────────────────────────────────────
    if col("Title 1"):
        titles = df.loc[ok, "Title 1"].dropna()
        dup_titles = titles[titles.duplicated(keep=False) & (titles.str.strip() != "")]
        if len(dup_titles):
            mask = ok & df.index.isin(dup_titles.index)
            issues.append(_build("duplicate_title", len(dup_titles), first_urls(mask)))

    # ── Title too long ────────────────────────────────────────────────────────
    if col("Title 1 Length"):
        mask = ok & (pd.to_numeric(df["Title 1 Length"], errors="coerce") > 60)
        if mask.sum():
            issues.append(_build("title_too_long", mask.sum(), first_urls(mask)))
    elif col("Title 1"):
        mask = ok & (df["Title 1"].str.len() > 60)
        if mask.sum():
            issues.append(_build("title_too_long", mask.sum(), first_urls(mask)))

    # ── Title too short ───────────────────────────────────────────────────────
    if col("Title 1 Length"):
        mask = ok & (pd.to_numeric(df["Title 1 Length"], errors="coerce") < 30) & (pd.to_numeric(df["Title 1 Length"], errors="coerce") > 0)
        if mask.sum():
            issues.append(_build("title_too_short", mask.sum(), first_urls(mask)))
    elif col("Title 1"):
        mask = ok & (df["Title 1"].str.len() < 30) & (df["Title 1"].str.len() > 0)
        if mask.sum():
            issues.append(_build("title_too_short", mask.sum(), first_urls(mask)))

    # ── Missing meta description ──────────────────────────────────────────────
    if col("Meta Description 1"):
        mask = ok & (df["Meta Description 1"].isna() | (df["Meta Description 1"].str.strip() == ""))
        if mask.sum():
            issues.append(_build("missing_meta_description", mask.sum(), first_urls(mask)))

    # ── Duplicate meta description ────────────────────────────────────────────
    if col("Meta Description 1"):
        mds = df.loc[ok, "Meta Description 1"].dropna()
        dup_mds = mds[mds.duplicated(keep=False) & (mds.str.strip() != "")]
        if len(dup_mds):
            mask = ok & df.index.isin(dup_mds.index)
            issues.append(_build("duplicate_meta_description", len(dup_mds), first_urls(mask)))

    # ── Missing H1 ────────────────────────────────────────────────────────────
    if col("H1-1"):
        mask = ok & (df["H1-1"].isna() | (df["H1-1"].str.strip() == ""))
        if mask.sum():
            issues.append(_build("missing_h1", mask.sum(), first_urls(mask)))

    # ── Multiple H1s ──────────────────────────────────────────────────────────
    if col("H1-2"):
        mask = ok & df["H1-2"].notna() & (df["H1-2"].astype(str).str.strip() != "") & (df["H1-2"].astype(str) != "nan")
        if mask.sum():
            issues.append(_build("multiple_h1", mask.sum(), first_urls(mask)))

    # ── Missing canonical ─────────────────────────────────────────────────────
    if col("Canonical Link Element 1"):
        mask = ok & (df["Canonical Link Element 1"].isna() | (df["Canonical Link Element 1"].str.strip() == ""))
        if mask.sum():
            issues.append(_build("missing_canonical", mask.sum(), first_urls(mask)))

    # ── Non-canonical receiving inlinks ───────────────────────────────────────
    if col("Canonical Link Element 1") and col("Inlinks") and col("Address"):
        non_canon = ok & df["Canonical Link Element 1"].notna() & \
                    (df["Canonical Link Element 1"].str.strip() != "") & \
                    (df["Canonical Link Element 1"].str.strip() != df["Address"].str.strip()) & \
                    (pd.to_numeric(df["Inlinks"], errors="coerce") > 0)
        if non_canon.sum():
            issues.append(_build("non_canonical_inlinked", non_canon.sum(), first_urls(non_canon)))

    # ── Redirect chains ───────────────────────────────────────────────────────
    if col("Status Code"):
        mask = df["Status Code"].isin([301, 302, 307, 308])
        if mask.sum():
            issues.append(_build("redirect_chain", mask.sum(), first_urls(mask)))

    # ── Noindex ───────────────────────────────────────────────────────────────
    if col("Indexability"):
        mask = df["Indexability"].str.lower().str.contains("non-index", na=False)
        if mask.sum():
            issues.append(_build("noindex_pages", mask.sum(), first_urls(mask)))
    elif col("Indexability Status"):
        mask = df["Indexability Status"].str.lower().str.contains("noindex", na=False)
        if mask.sum():
            issues.append(_build("noindex_pages", mask.sum(), first_urls(mask)))

    # ── Thin content ─────────────────────────────────────────────────────────
    if col("Word Count"):
        wc = pd.to_numeric(df["Word Count"], errors="coerce")
        mask = ok & (wc < 300) & (wc >= 100)
        if mask.sum():
            issues.append(_build("thin_content", mask.sum(), first_urls(mask)))

        mask2 = ok & (wc < 100) & wc.notna()
        if mask2.sum():
            issues.append(_build("low_word_count", mask2.sum(), first_urls(mask2)))

    # ── Missing alt text ──────────────────────────────────────────────────────
    if col("Alt Text") or col("Alt"):
        alt_col = "Alt Text" if col("Alt Text") else "Alt"
        mask = df[alt_col].isna() | (df[alt_col].str.strip() == "")
        if mask.sum():
            issues.append(_build("missing_alt_text", mask.sum(), first_urls(mask)))

    # ── HTTP pages ────────────────────────────────────────────────────────────
    if col("Address"):
        mask = ok & df["Address"].str.startswith("http://", na=False)
        if mask.sum():
            issues.append(_build("http_pages", mask.sum(), first_urls(mask)))

    # Sort by priority score
    issues.sort(key=lambda x: x["priority_score"], reverse=True)
    for i, issue in enumerate(issues, 1):
        issue["rank"] = i

    return issues


def _build(key: str, count: int, examples: list) -> dict:
    cfg = SEO_ISSUES[key]
    instance_multiplier = 1 + math.log10(max(count, 1))
    priority_score = round(cfg["base_impact"] * instance_multiplier, 2)
    example_str = examples[0] if examples else "N/A"
    return {
        "key": key,
        "label": cfg["label"],
        "category": cfg["category"],
        "effort": cfg["effort"],
        "instances": count,
        "base_impact": cfg["base_impact"],
        "priority_score": priority_score,
        "recommendation": cfg["recommendation"].format(count=count, example=example_str),
        "examples": examples,
        "rank": None,
    }


def issues_to_dataframe(issues: list[dict]) -> pd.DataFrame:
    if not issues:
        return pd.DataFrame()
    rows = []
    for issue in issues:
        rows.append({
            "Rank": issue["rank"],
            "Issue": issue["label"],
            "Category": issue["category"],
            "Instances": issue["instances"],
            "Effort": issue["effort"],
            "Priority Score": issue["priority_score"],
            "Recommendation": issue["recommendation"],
            "Example URLs": "\n".join(issue["examples"]),
        })
    return pd.DataFrame(rows)
