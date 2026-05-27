import streamlit as st
import pandas as pd
import textwrap
from fpdf import FPDF

from backend import load_csv_bytes, analyse, issues_to_dataframe

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SEO Action Prioritizer",
    page_icon="🔍",
    layout="wide",
)

st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .effort-low { color: #28a745; font-weight: 600; }
    .effort-medium { color: #fd7e14; font-weight: 600; }
    .effort-high { color: #dc3545; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ─── Header ───────────────────────────────────────────────────────────────────
st.title("SEO Action Prioritizer")
st.caption("Upload a Screaming Frog CSV export to get prioritised, actionable SEO recommendations.")

with st.expander("How to export from Screaming Frog", expanded=False):
    st.markdown("""
**Two options:**

**Option A — Export the main crawl (recommended):**
1. Run your crawl in Screaming Frog
2. Go to **Reports > Export > All Tabs** — this exports one CSV per tab
3. Upload the **internal_html.csv** file here (or any tab CSV)

**Option B — Export a specific tab:**
1. In Screaming Frog, click on any tab (e.g. Page Titles, Meta Description, H1, etc.)
2. Click **Export** in the top bar
3. Upload the resulting CSV here

The app detects which columns are present and runs only the relevant checks.
    """)

st.divider()

# ─── Upload ───────────────────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "Upload Screaming Frog CSV export",
    type=["csv"],
    help="Export from Screaming Frog: Reports > Export > All Tabs, then upload internal_html.csv",
)

if not uploaded:
    st.info("Upload a CSV file to get started.")
    st.stop()

# ─── Load ────────────────────────────────────────────────────────────────────
with st.spinner("Reading file..."):
    try:
        df = load_csv_bytes(uploaded.getvalue(), uploaded.name)
    except Exception as e:
        st.error(f"Could not read CSV: {e}")
        st.stop()

if df.empty or len(df.columns) < 2:
    st.error("The file appears empty or has no recognisable columns.")
    st.stop()

with st.expander(f"Columns detected ({len(df.columns)})", expanded=False):
    st.write(list(df.columns))

# ─── Analyse ─────────────────────────────────────────────────────────────────
with st.spinner("Analysing SEO issues..."):
    issues = analyse(df)
    result_df = issues_to_dataframe(issues)

if not issues:
    st.success("No SEO issues detected in this export. Either the site is clean or the CSV does not contain the relevant columns.")
    st.stop()

# ─── Summary metrics ─────────────────────────────────────────────────────────
st.subheader("Summary")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Issues Found", len(issues))
c2.metric("Total Instances", int(result_df["Instances"].sum()))
c3.metric("Quick Wins (Low Effort)", int((result_df["Effort"] == "Low").sum()))
c4.metric("Top Priority Score", result_df["Priority Score"].max())

st.divider()

# ─── Filters ─────────────────────────────────────────────────────────────────
st.subheader("Prioritised Actions")
f1, f2 = st.columns(2)
with f1:
    cat_filter = st.multiselect("Filter by Category", sorted(result_df["Category"].unique()), default=[])
with f2:
    effort_filter = st.multiselect("Filter by Effort", ["Low", "Medium", "High"], default=[])

filtered = result_df.copy()
if cat_filter:
    filtered = filtered[filtered["Category"].isin(cat_filter)]
if effort_filter:
    filtered = filtered[filtered["Effort"].isin(effort_filter)]

# ─── Issue cards ─────────────────────────────────────────────────────────────
effort_color = {"Low": "green", "Medium": "orange", "High": "red"}

for _, row in filtered.iterrows():
    with st.expander(
        f"#{row['Rank']}  {row['Issue']}  —  {row['Instances']} instance(s)  |  Effort: {row['Effort']}  |  Score: {row['Priority Score']}",
        expanded=row["Rank"] <= 3,
    ):
        ca, cb, cc = st.columns(3)
        ca.markdown(f"**Category:** {row['Category']}")
        cb.markdown(f"**Effort:** :{effort_color.get(row['Effort'], 'gray')}[{row['Effort']}]")
        cc.markdown(f"**Priority Score:** `{row['Priority Score']}`")

        st.markdown("**Recommendation:**")
        st.write(row["Recommendation"])

        if row["Example URLs"] and row["Example URLs"].strip() not in ("", "N/A"):
            st.markdown("**Example URLs:**")
            for url in row["Example URLs"].split("\n"):
                if url.strip():
                    st.code(url.strip(), language=None)

st.divider()

# ─── Full table ───────────────────────────────────────────────────────────────
with st.expander("View full data table"):
    st.dataframe(filtered.drop(columns=["Example URLs"]), use_container_width=True, hide_index=True)

# ─── PDF export ───────────────────────────────────────────────────────────────
def generate_pdf(df_out: pd.DataFrame, source_name: str) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "SEO Action Prioritizer Report", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Source: {source_name}", ln=True)
    pdf.cell(0, 6, f"Issues: {len(df_out)}   |   Total instances: {int(df_out['Instances'].sum())}", ln=True)
    pdf.ln(4)

    for _, row in df_out.iterrows():
        pdf.set_fill_color(0, 102, 204)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f"#{row['Rank']}  {row['Issue']}"[:90], fill=True, ln=True)

        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 6, f"Category: {row['Category']}   |   Effort: {row['Effort']}   |   Instances: {row['Instances']}   |   Score: {row['Priority Score']}", ln=True)

        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, "Recommendation:", ln=True)
        pdf.set_font("Helvetica", "", 9)
        for line in textwrap.wrap(row["Recommendation"], width=100):
            pdf.cell(0, 5, line, ln=True)

        if row["Example URLs"] and row["Example URLs"].strip() not in ("", "N/A"):
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, "Example URLs:", ln=True)
            pdf.set_font("Helvetica", "", 8)
            for url in row["Example URLs"].split("\n"):
                if url.strip():
                    pdf.cell(0, 5, url.strip()[:110], ln=True)

        pdf.ln(4)

    return pdf.output(dest="S").encode("latin-1")


st.subheader("Export")
if st.button("Generate PDF Report", type="primary"):
    with st.spinner("Building PDF..."):
        pdf_bytes = generate_pdf(filtered, uploaded.name)
    st.download_button("Download PDF", data=pdf_bytes, file_name="seo_action_report.pdf", mime="application/pdf")
