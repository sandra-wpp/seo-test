import streamlit as st
import pandas as pd
import tempfile
import os
from pathlib import Path
from io import BytesIO
from fpdf import FPDF
import textwrap

from backend import load_database, analyse_crawl, issues_to_dataframe

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SEO Action Prioritizer",
    page_icon="🔍",
    layout="wide",
)

# ─── Styling ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .metric-card {
        background: #f8f9fa;
        border-left: 4px solid #0066cc;
        padding: 1rem 1.2rem;
        border-radius: 6px;
        margin-bottom: 0.5rem;
    }
    .effort-low { color: #28a745; font-weight: 600; }
    .effort-medium { color: #fd7e14; font-weight: 600; }
    .effort-high { color: #dc3545; font-weight: 600; }
    .rank-badge {
        background: #0066cc;
        color: white;
        border-radius: 50%;
        padding: 2px 8px;
        font-weight: 700;
        font-size: 0.85rem;
    }
    h1 { font-size: 1.8rem !important; }
</style>
""", unsafe_allow_html=True)


# ─── Header ───────────────────────────────────────────────────────────────────
st.title("SEO Action Prioritizer")
st.caption("Upload a Screaming Frog crawl file (.dbseospider) to get prioritised SEO actions.")

st.divider()

# ─── File upload ──────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "Upload Screaming Frog crawl database",
    type=["dbseospider"],
    help="Export from Screaming Frog: File > Save As > .dbseospider",
)

if not uploaded_file:
    st.info("Upload a .dbseospider file to get started.")
    st.stop()

# ─── Load and analyse ─────────────────────────────────────────────────────────
with st.spinner("Analysing crawl data..."):
    # Write to temp file and explicitly flush+close before SQLite opens it
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".dbseospider")
    try:
        file_bytes = uploaded_file.getvalue()
        with os.fdopen(tmp_fd, "wb") as tmp:
            tmp.write(file_bytes)
            tmp.flush()
        # tmp is now fully closed — safe for SQLite to open
        conn = load_database(tmp_path)
        issues = analyse_crawl(conn)
        conn.close()
    except Exception as e:
        st.error(f"Failed to read crawl file: {e}")
        st.stop()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

if not issues:
    st.success("No SEO issues detected in this crawl. Good job!")
    st.stop()

df = issues_to_dataframe(issues)

# ─── Summary metrics ──────────────────────────────────────────────────────────
st.subheader("Summary")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Issues Found", len(issues))
col2.metric("Total Instances", int(df["Instances"].sum()))
col3.metric("Quick Wins (Low Effort)", int((df["Effort"] == "Low").sum()))
col4.metric("Top Priority Score", df["Priority Score"].max())

st.divider()

# ─── Filters ─────────────────────────────────────────────────────────────────
st.subheader("Prioritised Actions")

filter_col1, filter_col2 = st.columns(2)
with filter_col1:
    category_filter = st.multiselect(
        "Filter by Category",
        options=sorted(df["Category"].unique()),
        default=[],
    )
with filter_col2:
    effort_filter = st.multiselect(
        "Filter by Effort",
        options=["Low", "Medium", "High"],
        default=[],
    )

filtered_df = df.copy()
if category_filter:
    filtered_df = filtered_df[filtered_df["Category"].isin(category_filter)]
if effort_filter:
    filtered_df = filtered_df[filtered_df["Effort"].isin(effort_filter)]

# ─── Issue cards ─────────────────────────────────────────────────────────────
effort_color = {"Low": "green", "Medium": "orange", "High": "red"}

for _, row in filtered_df.iterrows():
    with st.expander(
        f"#{row['Rank']}  {row['Issue']}  —  {row['Instances']} instance(s)  |  Effort: {row['Effort']}  |  Score: {row['Priority Score']}",
        expanded=row["Rank"] <= 3,
    ):
        col_a, col_b, col_c = st.columns(3)
        col_a.markdown(f"**Category:** {row['Category']}")
        col_b.markdown(f"**Effort:** :{effort_color.get(row['Effort'], 'gray')}[{row['Effort']}]")
        col_c.markdown(f"**Priority Score:** `{row['Priority Score']}`")

        st.markdown("**Recommendation:**")
        st.write(row["Recommendation"])

        if row["Example URLs"] and row["Example URLs"] != "N/A":
            st.markdown("**Example URLs:**")
            for url in row["Example URLs"].split("\n"):
                if url.strip():
                    st.code(url.strip(), language=None)

st.divider()

# ─── Raw data table ───────────────────────────────────────────────────────────
with st.expander("View full data table"):
    st.dataframe(
        filtered_df.drop(columns=["Example URLs"]),
        use_container_width=True,
        hide_index=True,
    )

# ─── PDF export ───────────────────────────────────────────────────────────────
def generate_pdf(issues_df: pd.DataFrame, filename: str) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "SEO Action Prioritizer Report", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Source file: {filename}", ln=True)
    pdf.cell(0, 6, f"Total issues: {len(issues_df)}  |  Total instances: {int(issues_df['Instances'].sum())}", ln=True)
    pdf.ln(4)

    for _, row in issues_df.iterrows():
        # Issue header
        pdf.set_fill_color(0, 102, 204)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 11)
        header = f"#{row['Rank']}  {row['Issue']}"
        pdf.cell(0, 8, header[:90], fill=True, ln=True)

        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 9)

        # Meta row
        meta = f"Category: {row['Category']}   |   Effort: {row['Effort']}   |   Instances: {row['Instances']}   |   Priority Score: {row['Priority Score']}"
        pdf.cell(0, 6, meta, ln=True)

        # Recommendation
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, "Recommendation:", ln=True)
        pdf.set_font("Helvetica", "", 9)
        wrapped = textwrap.wrap(row["Recommendation"], width=100)
        for line in wrapped:
            pdf.cell(0, 5, line, ln=True)

        # Example URLs
        if row["Example URLs"] and row["Example URLs"] != "N/A":
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, "Example URLs:", ln=True)
            pdf.set_font("Helvetica", "", 8)
            for url in row["Example URLs"].split("\n"):
                if url.strip():
                    pdf.cell(0, 5, url.strip()[:100], ln=True)

        pdf.ln(4)

    return pdf.output(dest="S").encode("latin-1")


st.subheader("Export")
if st.button("Generate PDF Report", type="primary"):
    with st.spinner("Building PDF..."):
        pdf_bytes = generate_pdf(filtered_df, uploaded_file.name)
    st.download_button(
        label="Download PDF",
        data=pdf_bytes,
        file_name="seo_action_report.pdf",
        mime="application/pdf",
    )
