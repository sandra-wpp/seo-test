import pandas as pd
import math
import io
import zipfile
from pathlib import Path


# ─── SEO Issue Definitions ────────────────────────────────────────────────────
# base_impact: 1-10 (SEO best practice severity)
# effort: Low / Medium / High

SEO_ISSUES = {
    "broken_links": {
        "label": "Broken Internal Links (4xx)",
        "base_impact": 10,
        "category": "Crawlability",
        "effort": "Medium",
        "recommendation": (
            "{count} page(s) return a 4xx error. Fix or redirect each one. "
            "Example: '{example}' — set up a 301 redirect to the correct destination or remove the link."
        ),
    },
    "missing_title": {
        "label": "Missing Page Title",
        "base_impact": 9,
        "category": "On-Page SEO",
        "effort": "Low",
        "recommendation": (
            "{count} page(s) have no <title> tag. "
            "Example: '{example}' — add a unique, descriptive title of 50-60 characters."
        ),
    },
    "duplicate_title": {
        "label": "Duplicate Page Title",
        "base_impact": 8,
        "category": "On-Page SEO",
        "effort": "Medium",
        "recommendation": (
            "{count} page(s) share identical titles, causing keyword cannibalisation. "
            "Example: '{example}' — each page needs a unique title tag."
        ),
    },
    "missing_h1": {
        "label": "Missing H1 Tag",
        "base_impact": 8,
        "category": "On-Page SEO",
        "effort": "Low",
        "recommendation": (
            "{count} page(s) have no H1 tag. "
            "Example: '{example}' — add one clear H1 per page matching the target keyword."
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
            "{count} page(s) have no meta description, reducing click-through rate from search results. "
            "Example: '{example}' — write a unique 120-160 character summary."
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
            "{count} page(s) have fewer than 300 words. "
            "Example: '{example}' — expand the content, merge with a related page, or add a noindex directive."
        ),
    },
    "missing_alt_text": {
        "label": "Images Missing Alt Text",
        "base_impact": 5,
        "category": "Accessibility & SEO",
        "effort": "Low",
        "recommendation": (
            "{count} image(s) have no alt attribute, missing image search visibility and failing accessibility. "
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


# ─── Column normalisation ─────────────────────────────────────────────────────
# Maps Screaming Frog column name variants to canonical names.

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
    "content type": "Content Type",
    "type": "Content Type",
}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    rename = {}
    for col in df.columns:
        mapped = COL_MAP.get(col.lower())
        if mapped and mapped not in df.columns:
            rename[col] = mapped
    return df.rename(columns=rename)


def _read_csv_bytes(data: bytes) -> pd.DataFrame:
    """Read CSV bytes, try UTF-8 then latin-1."""
    try:
        df = pd.read_csv(io.BytesIO(data), encoding="utf-8", low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(io.BytesIO(data), encoding="latin-1", low_memory=False)
    return _normalise_columns(df)


def _read_xls_bytes(data: bytes) -> pd.DataFrame:
    """
    Read a Screaming Frog .xls export.
    Screaming Frog exports .xls files in BIFF8 format. We try openpyxl first
    (works if SF saved as xlsx-compatible), then xlrd (if installed), then
    raise a clear error pointing to the CSV fallback.
    """
    buf = io.BytesIO(data)
    # Try openpyxl — works if the file is actually an xlsx saved with .xls extension
    try:
        df = pd.read_excel(buf, engine="openpyxl")
        return _normalise_columns(df)
    except Exception:
        pass
    # Try xlrd — handles true BIFF8 .xls files
    buf.seek(0)
    try:
        df = pd.read_excel(buf, engine="xlrd")
        return _normalise_columns(df)
    except ImportError:
        raise ValueError(
            "Screaming Frog exports .xls in a legacy Excel format that requires the 'xlrd' library. "
            "Either install it (pip install xlrd) or export as CSV from Screaming Frog instead: "
            "in the export dialog, change the format to CSV before saving."
        )


def _read_file_bytes(data: bytes, filename: str) -> pd.DataFrame:
    """Dispatch to the right reader based on file extension."""
    if filename.lower().endswith(".xls"):
        return _read_xls_bytes(data)
    return _read_csv_bytes(data)


# ─── Public loaders ───────────────────────────────────────────────────────────

def load_single_file(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Load a single Screaming Frog CSV or XLS export."""
    return _read_file_bytes(file_bytes, filename)


def load_zip_of_csvs(file_bytes: bytes) -> pd.DataFrame:
    """
    Load a ZIP of Screaming Frog CSVs (from Bulk Export > Issues > All).
    Merges all CSVs that contain an 'Address' column into one DataFrame,
    keeping the superset of columns.
    """
    frames = []
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
        for name in z.namelist():
            if not (name.lower().endswith(".csv") or name.lower().endswith(".xls")):
                continue
            try:
                df = _read_file_bytes(z.read(name), name)
                if "Address" in df.columns:
                    frames.append(df)
            except Exception:
                continue

    if not frames:
        return pd.DataFrame()

    # Merge on Address — outer join so we keep all columns
    merged = frames[0]
    for df in frames[1:]:
        new_cols = [c for c in df.columns if c not in merged.columns and c != "Address"]
        if new_cols:
            merged = merged.merge(df[["Address"] + new_cols], on="Address", how="outer")
        else:
            # Still merge to pick up any new rows (e.g. broken link URLs not in base)
            merged = pd.concat([merged, df[merged.columns.intersection(df.columns)]], ignore_index=True).drop_duplicates(subset=["Address"])

    return merged


# ─── Analysis ─────────────────────────────────────────────────────────────────

def analyse(df: pd.DataFrame) -> list[dict]:
    """Run all SEO checks. Returns issue list sorted by priority score."""
    issues = []

    def col(name):
        return name in df.columns

    def first_urls(mask, n=3):
        if "Address" not in df.columns:
            return []
        return df.loc[mask, "Address"].dropna().head(n).tolist()

    # Base filter: 200 OK HTML pages
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

    # ── Redirect chains ───────────────────────────────────────────────────────
    if col("Status Code"):
        mask = df["Status Code"].isin([301, 302, 307, 308])
        if mask.sum():
            issues.append(_build("redirect_chain", mask.sum(), first_urls(mask)))

    # ── Missing title ─────────────────────────────────────────────────────────
    if col("Title 1"):
        mask = ok & (df["Title 1"].isna() | (df["Title 1"].astype(str).str.strip() == ""))
        if mask.sum():
            issues.append(_build("missing_title", mask.sum(), first_urls(mask)))

    # ── Duplicate title ───────────────────────────────────────────────────────
    if col("Title 1"):
        titles = df.loc[ok, "Title 1"].dropna()
        titles = titles[titles.astype(str).str.strip() != ""]
        dup = titles[titles.duplicated(keep=False)]
        if len(dup):
            mask = ok & df.index.isin(dup.index)
            issues.append(_build("duplicate_title", len(dup), first_urls(mask)))

    # ── Title too long ────────────────────────────────────────────────────────
    if col("Title 1 Length"):
        mask = ok & (pd.to_numeric(df["Title 1 Length"], errors="coerce") > 60)
        if mask.sum():
            issues.append(_build("title_too_long", mask.sum(), first_urls(mask)))
    elif col("Title 1"):
        mask = ok & (df["Title 1"].astype(str).str.len() > 60)
        if mask.sum():
            issues.append(_build("title_too_long", mask.sum(), first_urls(mask)))

    # ── Title too short ───────────────────────────────────────────────────────
    if col("Title 1 Length"):
        tl = pd.to_numeric(df["Title 1 Length"], errors="coerce")
        mask = ok & (tl < 30) & (tl > 0)
        if mask.sum():
            issues.append(_build("title_too_short", mask.sum(), first_urls(mask)))
    elif col("Title 1"):
        tl = df["Title 1"].astype(str).str.len()
        mask = ok & (tl < 30) & (tl > 0)
        if mask.sum():
            issues.append(_build("title_too_short", mask.sum(), first_urls(mask)))

    # ── Missing meta description ──────────────────────────────────────────────
    if col("Meta Description 1"):
        mask = ok & (df["Meta Description 1"].isna() | (df["Meta Description 1"].astype(str).str.strip() == ""))
        if mask.sum():
            issues.append(_build("missing_meta_description", mask.sum(), first_urls(mask)))

    # ── Duplicate meta description ────────────────────────────────────────────
    if col("Meta Description 1"):
        mds = df.loc[ok, "Meta Description 1"].dropna()
        mds = mds[mds.astype(str).str.strip() != ""]
        dup = mds[mds.duplicated(keep=False)]
        if len(dup):
            mask = ok & df.index.isin(dup.index)
            issues.append(_build("duplicate_meta_description", len(dup), first_urls(mask)))

    # ── Missing H1 ────────────────────────────────────────────────────────────
    if col("H1-1"):
        mask = ok & (df["H1-1"].isna() | (df["H1-1"].astype(str).str.strip().isin(["", "nan"])))
        if mask.sum():
            issues.append(_build("missing_h1", mask.sum(), first_urls(mask)))

    # ── Multiple H1s ──────────────────────────────────────────────────────────
    if col("H1-2"):
        mask = ok & df["H1-2"].notna() & (~df["H1-2"].astype(str).str.strip().isin(["", "nan"]))
        if mask.sum():
            issues.append(_build("multiple_h1", mask.sum(), first_urls(mask)))

    # ── Missing canonical ─────────────────────────────────────────────────────
    if col("Canonical Link Element 1"):
        mask = ok & (df["Canonical Link Element 1"].isna() | (df["Canonical Link Element 1"].astype(str).str.strip() == ""))
        if mask.sum():
            issues.append(_build("missing_canonical", mask.sum(), first_urls(mask)))

    # ── Non-canonical receiving inlinks ───────────────────────────────────────
    if col("Canonical Link Element 1") and col("Inlinks") and col("Address"):
        non_canon = (
            ok
            & df["Canonical Link Element 1"].notna()
            & (~df["Canonical Link Element 1"].astype(str).str.strip().isin(["", "nan"]))
            & (df["Canonical Link Element 1"].astype(str).str.strip() != df["Address"].astype(str).str.strip())
            & (pd.to_numeric(df["Inlinks"], errors="coerce") > 0)
        )
        if non_canon.sum():
            issues.append(_build("non_canonical_inlinked", non_canon.sum(), first_urls(non_canon)))

    # ── Noindex ───────────────────────────────────────────────────────────────
    if col("Indexability"):
        mask = df["Indexability"].astype(str).str.lower().str.contains("non-index", na=False)
        if mask.sum():
            issues.append(_build("noindex_pages", mask.sum(), first_urls(mask)))
    elif col("Indexability Status"):
        mask = df["Indexability Status"].astype(str).str.lower().str.contains("noindex", na=False)
        if mask.sum():
            issues.append(_build("noindex_pages", mask.sum(), first_urls(mask)))

    # ── Thin content ──────────────────────────────────────────────────────────
    if col("Word Count"):
        wc = pd.to_numeric(df["Word Count"], errors="coerce")
        mask = ok & (wc >= 100) & (wc < 300)
        if mask.sum():
            issues.append(_build("thin_content", mask.sum(), first_urls(mask)))
        mask2 = ok & (wc < 100) & wc.notna()
        if mask2.sum():
            issues.append(_build("low_word_count", mask2.sum(), first_urls(mask2)))

    # ── Missing alt text ──────────────────────────────────────────────────────
    if col("Alt Text"):
        mask = df["Alt Text"].isna() | (df["Alt Text"].astype(str).str.strip().isin(["", "nan"]))
        if mask.sum():
            issues.append(_build("missing_alt_text", mask.sum(), first_urls(mask)))

    # ── HTTP pages ────────────────────────────────────────────────────────────
    if col("Address"):
        mask = ok & df["Address"].astype(str).str.startswith("http://", na=False)
        if mask.sum():
            issues.append(_build("http_pages", mask.sum(), first_urls(mask)))

    issues.sort(key=lambda x: x["priority_score"], reverse=True)
    for i, issue in enumerate(issues, 1):
        issue["rank"] = i
    return issues


def _build(key: str, count: int, examples: list) -> dict:
    cfg = SEO_ISSUES[key]
    score = round(cfg["base_impact"] * (1 + math.log10(max(count, 1))), 2)
    example_str = examples[0] if examples else "N/A"
    return {
        "key": key,
        "label": cfg["label"],
        "category": cfg["category"],
        "effort": cfg["effort"],
        "instances": count,
        "base_impact": cfg["base_impact"],
        "priority_score": score,
        "recommendation": cfg["recommendation"].format(count=count, example=example_str),
        "examples": examples,
        "rank": None,
    }


def issues_to_dataframe(issues: list[dict]) -> pd.DataFrame:
    if not issues:
        return pd.DataFrame()
    return pd.DataFrame([{
        "Rank": i["rank"],
        "Issue": i["label"],
        "Category": i["category"],
        "Instances": i["instances"],
        "Effort": i["effort"],
        "Priority Score": i["priority_score"],
        "Recommendation": i["recommendation"],
        "Example URLs": "\n".join(i["examples"]),
    } for i in issues])
