import sqlite3
import pandas as pd
from pathlib import Path


# SEO issue definitions: (label, base_impact_score, category, recommendation_template)
# Base impact score 1-10, where 10 = critical
SEO_ISSUES = {
    # --- Critical (8-10) ---
    "broken_links": {
        "label": "Broken Internal Links (4xx)",
        "base_impact": 10,
        "category": "Crawlability",
        "effort": "Medium",
        "recommendation": (
            "Fix or redirect {count} broken internal link(s). "
            "Example: '{example}' returns a 4xx error. "
            "Update the link or set up a 301 redirect to the correct URL."
        ),
    },
    "missing_title": {
        "label": "Missing Page Title",
        "base_impact": 9,
        "category": "On-Page SEO",
        "effort": "Low",
        "recommendation": (
            "{count} page(s) have no title tag. "
            "Example: '{example}' — add a unique, descriptive <title> of 50-60 characters."
        ),
    },
    "missing_meta_description": {
        "label": "Missing Meta Description",
        "base_impact": 7,
        "category": "On-Page SEO",
        "effort": "Low",
        "recommendation": (
            "{count} page(s) are missing a meta description. "
            "Example: '{example}' — write a compelling summary of 120-160 characters."
        ),
    },
    "missing_h1": {
        "label": "Missing H1 Tag",
        "base_impact": 8,
        "category": "On-Page SEO",
        "effort": "Low",
        "recommendation": (
            "{count} page(s) have no H1. "
            "Example: '{example}' — add one descriptive H1 per page that matches the page topic."
        ),
    },
    "duplicate_title": {
        "label": "Duplicate Page Title",
        "base_impact": 8,
        "category": "On-Page SEO",
        "effort": "Medium",
        "recommendation": (
            "{count} page(s) share duplicate titles. "
            "Example: '{example}' — each page must have a unique title tag."
        ),
    },
    "duplicate_meta_description": {
        "label": "Duplicate Meta Description",
        "base_impact": 6,
        "category": "On-Page SEO",
        "effort": "Medium",
        "recommendation": (
            "{count} page(s) share meta descriptions. "
            "Example: '{example}' — write unique meta descriptions per page."
        ),
    },
    "missing_canonical": {
        "label": "Missing Canonical Tag",
        "base_impact": 7,
        "category": "Technical SEO",
        "effort": "Low",
        "recommendation": (
            "{count} page(s) have no canonical tag. "
            "Example: '{example}' — add <link rel='canonical' href='...'> to prevent duplicate content issues."
        ),
    },
    "non_canonical": {
        "label": "Non-Canonical Page Receiving Links",
        "base_impact": 8,
        "category": "Technical SEO",
        "effort": "Medium",
        "recommendation": (
            "{count} page(s) are non-canonical but receive internal links. "
            "Example: '{example}' — update internal links to point to the canonical version."
        ),
    },
    "redirect_chain": {
        "label": "Redirect Chains",
        "base_impact": 7,
        "category": "Technical SEO",
        "effort": "Medium",
        "recommendation": (
            "{count} redirect chain(s) detected. "
            "Example: '{example}' — consolidate to a single 301 redirect to the final destination."
        ),
    },
    "thin_content": {
        "label": "Thin Content (Low Word Count)",
        "base_impact": 6,
        "category": "Content",
        "effort": "High",
        "recommendation": (
            "{count} page(s) have fewer than 300 words. "
            "Example: '{example}' — expand content to adequately cover the topic, or consolidate/noindex the page."
        ),
    },
    "missing_alt_text": {
        "label": "Images Missing Alt Text",
        "base_impact": 5,
        "category": "Accessibility & SEO",
        "effort": "Low",
        "recommendation": (
            "{count} image(s) have no alt attribute. "
            "Example: '{example}' — add descriptive alt text to all images."
        ),
    },
    "title_too_long": {
        "label": "Page Title Too Long (>60 chars)",
        "base_impact": 5,
        "category": "On-Page SEO",
        "effort": "Low",
        "recommendation": (
            "{count} title(s) exceed 60 characters and may be truncated in search results. "
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
            "Example: '{example}' — expand to 50-60 characters."
        ),
    },
    "low_text_ratio": {
        "label": "Low Text-to-HTML Ratio",
        "base_impact": 4,
        "category": "Content",
        "effort": "High",
        "recommendation": (
            "{count} page(s) have a very low text-to-HTML ratio (under 10%). "
            "Example: '{example}' — reduce bloated HTML or add more meaningful content."
        ),
    },
    "http_urls": {
        "label": "Internal Links to HTTP (Non-HTTPS)",
        "base_impact": 7,
        "category": "Technical SEO",
        "effort": "Low",
        "recommendation": (
            "{count} internal link(s) point to HTTP instead of HTTPS. "
            "Example: '{example}' — update all links to use HTTPS."
        ),
    },
    "noindex_pages": {
        "label": "Pages Blocked by Noindex",
        "base_impact": 6,
        "category": "Crawlability",
        "effort": "Low",
        "recommendation": (
            "{count} page(s) have a noindex directive. "
            "Example: '{example}' — verify these pages should intentionally be excluded from indexing."
        ),
    },
}


def load_database(file_path: str) -> sqlite3.Connection:
    """Load the Screaming Frog .dbseospider SQLite database."""
    conn = sqlite3.connect(file_path)
    return conn


def get_available_tables(conn: sqlite3.Connection) -> list:
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [row[0] for row in cursor.fetchall()]


def safe_query(conn, query, fallback=None):
    """Run a query and return a DataFrame, or empty DataFrame on error."""
    try:
        return pd.read_sql_query(query, conn)
    except Exception:
        return fallback if fallback is not None else pd.DataFrame()


def analyse_crawl(conn: sqlite3.Connection) -> list[dict]:
    """
    Extract SEO issues from the Screaming Frog database.
    Returns a list of issue dicts sorted by priority score.
    """
    issues = []
    tables = get_available_tables(conn)

    # Helper: get example URLs
    def first_urls(df, url_col="Address", n=3):
        if df.empty or url_col not in df.columns:
            return []
        return df[url_col].dropna().head(n).tolist()

    # --- Broken internal links (4xx) ---
    if "internal_html" in tables or "all_inlinks" in tables:
        df = safe_query(
            conn,
            "SELECT Address, Status_Code FROM internal_html WHERE Status_Code >= 400 AND Status_Code < 500",
        )
        if df.empty:
            df = safe_query(
                conn,
                "SELECT Destination AS Address FROM all_inlinks WHERE Status_Code >= 400 AND Status_Code < 500",
            )
        if not df.empty:
            count = len(df)
            examples = first_urls(df)
            issues.append(_build_issue("broken_links", count, examples))

    # --- Missing title ---
    df = safe_query(
        conn,
        "SELECT Address, Title FROM internal_html WHERE (Title IS NULL OR Title = '') AND Status_Code = 200",
    )
    if not df.empty:
        issues.append(_build_issue("missing_title", len(df), first_urls(df)))

    # --- Duplicate title ---
    df = safe_query(
        conn,
        """
        SELECT Address, Title FROM internal_html
        WHERE Status_Code = 200 AND Title IS NOT NULL AND Title != ''
        AND Title IN (
            SELECT Title FROM internal_html
            WHERE Status_Code = 200 AND Title IS NOT NULL AND Title != ''
            GROUP BY Title HAVING COUNT(*) > 1
        )
        """,
    )
    if not df.empty:
        issues.append(_build_issue("duplicate_title", len(df), first_urls(df)))

    # --- Title too long (>60 chars) ---
    df = safe_query(
        conn,
        "SELECT Address, Title FROM internal_html WHERE Status_Code = 200 AND LENGTH(Title) > 60",
    )
    if not df.empty:
        issues.append(_build_issue("title_too_long", len(df), first_urls(df)))

    # --- Title too short (<30 chars) ---
    df = safe_query(
        conn,
        "SELECT Address, Title FROM internal_html WHERE Status_Code = 200 AND Title IS NOT NULL AND LENGTH(Title) < 30 AND LENGTH(Title) > 0",
    )
    if not df.empty:
        issues.append(_build_issue("title_too_short", len(df), first_urls(df)))

    # --- Missing meta description ---
    df = safe_query(
        conn,
        "SELECT Address, Meta_Description FROM internal_html WHERE Status_Code = 200 AND (Meta_Description IS NULL OR Meta_Description = '')",
    )
    if not df.empty:
        issues.append(_build_issue("missing_meta_description", len(df), first_urls(df)))

    # --- Duplicate meta description ---
    df = safe_query(
        conn,
        """
        SELECT Address, Meta_Description FROM internal_html
        WHERE Status_Code = 200 AND Meta_Description IS NOT NULL AND Meta_Description != ''
        AND Meta_Description IN (
            SELECT Meta_Description FROM internal_html
            WHERE Status_Code = 200 AND Meta_Description IS NOT NULL AND Meta_Description != ''
            GROUP BY Meta_Description HAVING COUNT(*) > 1
        )
        """,
    )
    if not df.empty:
        issues.append(_build_issue("duplicate_meta_description", len(df), first_urls(df)))

    # --- Missing H1 ---
    df = safe_query(
        conn,
        "SELECT Address, H1_1 FROM internal_html WHERE Status_Code = 200 AND (H1_1 IS NULL OR H1_1 = '')",
    )
    if not df.empty:
        issues.append(_build_issue("missing_h1", len(df), first_urls(df)))

    # --- Missing canonical ---
    df = safe_query(
        conn,
        "SELECT Address, Canonical_Link_Element_1 FROM internal_html WHERE Status_Code = 200 AND (Canonical_Link_Element_1 IS NULL OR Canonical_Link_Element_1 = '')",
    )
    if not df.empty:
        issues.append(_build_issue("missing_canonical", len(df), first_urls(df)))

    # --- Non-canonical receiving links ---
    df = safe_query(
        conn,
        """
        SELECT Address FROM internal_html
        WHERE Status_Code = 200
        AND Canonical_Link_Element_1 IS NOT NULL
        AND Canonical_Link_Element_1 != ''
        AND Canonical_Link_Element_1 != Address
        AND Inlinks > 0
        """,
    )
    if not df.empty:
        issues.append(_build_issue("non_canonical", len(df), first_urls(df)))

    # --- Redirect chains ---
    df = safe_query(
        conn,
        "SELECT Address, Redirect_URL FROM internal_html WHERE Status_Code IN (301, 302) AND Redirect_URL IS NOT NULL",
    )
    if not df.empty:
        issues.append(_build_issue("redirect_chain", len(df), first_urls(df)))

    # --- Thin content (<300 words) ---
    df = safe_query(
        conn,
        "SELECT Address, Word_Count FROM internal_html WHERE Status_Code = 200 AND Word_Count < 300 AND Word_Count IS NOT NULL",
    )
    if not df.empty:
        issues.append(_build_issue("thin_content", len(df), first_urls(df)))

    # --- Low text-to-HTML ratio ---
    df = safe_query(
        conn,
        "SELECT Address, Text_Ratio FROM internal_html WHERE Status_Code = 200 AND Text_Ratio < 10 AND Text_Ratio IS NOT NULL",
    )
    if not df.empty:
        issues.append(_build_issue("low_text_ratio", len(df), first_urls(df)))

    # --- Images missing alt text ---
    if "images" in tables or "internal_images" in tables:
        tbl = "images" if "images" in tables else "internal_images"
        df = safe_query(
            conn,
            f"SELECT src AS Address FROM {tbl} WHERE (Alt_Text IS NULL OR Alt_Text = '')",
        )
        if not df.empty:
            issues.append(_build_issue("missing_alt_text", len(df), first_urls(df)))

    # --- HTTP internal links ---
    df = safe_query(
        conn,
        "SELECT Address FROM internal_html WHERE Status_Code = 200 AND Address LIKE 'http://%'",
    )
    if not df.empty:
        issues.append(_build_issue("http_urls", len(df), first_urls(df)))

    # --- Noindex pages ---
    df = safe_query(
        conn,
        "SELECT Address, Indexability FROM internal_html WHERE Indexability = 'Non-Indexable' AND Indexability_Status LIKE '%noindex%'",
    )
    if not df.empty:
        issues.append(_build_issue("noindex_pages", len(df), first_urls(df)))

    # Sort by priority score descending
    issues.sort(key=lambda x: x["priority_score"], reverse=True)

    # Add rank
    for i, issue in enumerate(issues, 1):
        issue["rank"] = i

    return issues


def _build_issue(key: str, count: int, examples: list) -> dict:
    """Build a single issue dict with priority score."""
    cfg = SEO_ISSUES[key]
    base = cfg["base_impact"]

    # Priority score: base impact * log-scaled instance count
    import math
    instance_multiplier = 1 + math.log10(max(count, 1))
    priority_score = round(base * instance_multiplier, 2)

    example_str = examples[0] if examples else "N/A"
    recommendation = cfg["recommendation"].format(count=count, example=example_str)

    return {
        "key": key,
        "label": cfg["label"],
        "category": cfg["category"],
        "effort": cfg["effort"],
        "instances": count,
        "base_impact": base,
        "priority_score": priority_score,
        "recommendation": recommendation,
        "examples": examples,
        "rank": None,
    }


def issues_to_dataframe(issues: list[dict]) -> pd.DataFrame:
    """Convert issue list to a clean DataFrame for display."""
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
