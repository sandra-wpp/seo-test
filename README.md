# SEO Action Prioritizer

A Streamlit app for SEO consultants that turns a Screaming Frog CSV export into a prioritised action plan.

---

## What it does

Upload a Screaming Frog CSV export. The app detects which columns are present, runs all applicable SEO checks, scores each issue by **SEO impact x instance count**, and outputs ranked actions with concrete recommendations and example URLs.

Priority score formula:
```
priority_score = base_impact_score * (1 + log10(instance_count))
```

---

## How to export from Screaming Frog

**Option A — Full crawl export (recommended):**
1. Run your crawl in Screaming Frog
2. Go to **Reports > Export > All Tabs**
3. Upload the **internal_html.csv** from the exported folder

**Option B — Single tab export:**
1. Click any tab in Screaming Frog (Page Titles, H1, etc.)
2. Click **Export** in the top bar
3. Upload the resulting CSV

The app detects columns automatically and skips checks it cannot run.

---

## Issues detected (17 types)

| Category | Issues |
|---|---|
| Crawlability | Broken links (4xx), Noindex pages |
| On-Page SEO | Missing/duplicate title, Missing/duplicate meta description, Missing/multiple H1, Title too long/short |
| Technical SEO | Missing canonical, Non-canonical receiving links, Redirect chains, HTTP pages |
| Content | Thin content (<300 words), Very low word count (<100 words) |
| Accessibility | Images missing alt text |

---

## Setup (Mac)

```bash
git clone https://github.com/YOUR_USERNAME/seo-prioritizer.git
cd seo-prioritizer
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

App runs at `http://localhost:8501`.

---

## Deploy to Streamlit Cloud

1. Push repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect repo, set `app.py` as entry point
4. Deploy

---

## File structure

```
seo-prioritizer/
├── app.py            # Streamlit UI
├── backend.py        # CSV parsing, SEO checks, scoring logic
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

---

## Note on .dbseospider files

The `.dbseospider` format is a ZIP containing an **Apache Derby** (Java) database — not SQLite. It cannot be opened without a Java runtime and the Derby JDBC driver. Screaming Frog's standard CSV export is the correct way to extract crawl data for external tools.
