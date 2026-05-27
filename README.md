# SEO Action Prioritizer

A Streamlit app for SEO consultants that turns a Screaming Frog crawl into a prioritised action plan.

---

## What it does

Upload a `.dbseospider` crawl file. The app reads the SQLite database, detects SEO issues, scores each one by **SEO impact x instance count**, and outputs ranked actions with concrete recommendations and example URLs.

Priority score formula:

```
priority_score = base_impact_score * (1 + log10(instance_count))
```

Instance count boosts priority logarithmically — 1000 broken links ranks higher than 10, but not 1000x higher.

---

## Issues detected

| Category | Issues |
|---|---|
| Crawlability | Broken links (4xx), Noindex pages |
| On-Page SEO | Missing/duplicate title, Missing/duplicate meta description, Missing H1, Title too long/short |
| Technical SEO | Missing canonical, Non-canonical receiving links, Redirect chains, HTTP internal links |
| Content | Thin content (<300 words), Low text-to-HTML ratio |
| Accessibility | Images missing alt text |

---

## Setup

### Requirements

- Python 3.11+
- Mac or Linux

### Install

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/seo-prioritizer.git
cd seo-prioritizer

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Run locally

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## Usage

1. Open Screaming Frog and run a crawl.
2. Go to **File > Save As** and save as `.dbseospider`.
3. Upload the file in the app.
4. Review prioritised issues — the top 3 expand by default.
5. Filter by category or effort level.
6. Click **Generate PDF Report** and download.

---

## Deploy to Streamlit Cloud

1. Push the repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io).
3. Connect your GitHub repo, set `app.py` as the entry point.
4. Deploy — no server setup needed.

---

## File structure

```
seo-prioritizer/
├── app.py            # Streamlit UI
├── backend.py        # SQLite parsing, scoring logic, issue definitions
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

---

## Extending the app

To add a new issue type, add an entry to `SEO_ISSUES` in `backend.py` and add the corresponding query in `analyse_crawl()`. Follow the existing pattern.

---

## Notes

- The `.dbseospider` format is a standard SQLite database. Column names match Screaming Frog's internal schema. If Screaming Frog changes column names in a future version, update the queries in `backend.py`.
- Only internal HTML pages (status 200) are analysed unless otherwise specified.
- The app does not send any data externally. Everything runs locally or on Streamlit Cloud.
