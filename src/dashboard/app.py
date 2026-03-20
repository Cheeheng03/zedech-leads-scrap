"""Streamlit dashboard for viewing and managing leads."""

import sys
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.storage.database import Business, get_session, init_db
from src.storage.exporter import query_leads


def main():
    st.set_page_config(page_title="Zedech SME Lead Dashboard", layout="wide")
    st.title("Google Maps SME Leads - Malaysia")

    init_db()
    db = get_session()

    # --- Sidebar filters ---
    st.sidebar.header("Filters")

    all_states = sorted([r[0] for r in db.query(Business.state).distinct().all() if r[0]])
    selected_states = st.sidebar.multiselect("States", all_states, default=all_states)

    all_sectors = sorted([r[0] for r in db.query(Business.sector_query).distinct().all() if r[0]])
    selected_sectors = st.sidebar.multiselect("Sectors (search terms)", all_sectors)

    all_categories = sorted([r[0] for r in db.query(Business.category).distinct().all() if r[0]])
    selected_categories = st.sidebar.multiselect("Categories", all_categories)

    all_statuses = ["none", "social_only"]
    selected_statuses = st.sidebar.multiselect(
        "Website Status", all_statuses, default=all_statuses
    )

    min_score = st.sidebar.slider("Minimum Score", 0, 12, 0)

    show_contacted = st.sidebar.radio(
        "Contact Status", ["All", "Not Contacted", "Contacted"], index=1
    )

    google_confirmed = st.sidebar.checkbox("Google-confirmed no site only", value=False)

    # --- Sort options ---
    st.sidebar.header("Sort")
    sort_col = st.sidebar.selectbox(
        "Sort by",
        ["Score", "Rating", "Reviews", "Name", "State", "City", "Sector", "Category"],
        index=0,
    )
    sort_order = st.sidebar.radio("Order", ["Descending", "Ascending"], index=0)

    # --- Query data ---
    contacted_filter = None
    if show_contacted == "Not Contacted":
        contacted_filter = False
    elif show_contacted == "Contacted":
        contacted_filter = True

    df = query_leads(
        db,
        min_score=min_score,
        states=selected_states if selected_states else None,
        website_status=selected_statuses if selected_statuses else None,
        contacted=contacted_filter,
        sectors=selected_sectors if selected_sectors else None,
    )

    if selected_categories:
        df = df[df["Category"].isin(selected_categories)]

    if google_confirmed:
        df = df[df["Google Confirmed No Site"] == True]

    # Apply sorting
    if len(df) > 0:
        ascending = sort_order == "Ascending"
        df = df.sort_values(by=sort_col, ascending=ascending, na_position="last")
        df = df.reset_index(drop=True)

    # --- Stats row ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Leads", len(df))
    col2.metric("Avg Score", f"{df['Score'].mean():.1f}" if len(df) > 0 else "0")
    col3.metric("With Phone", len(df[df["Phone"].notna()]) if len(df) > 0 else 0)
    col4.metric(
        "Google Confirmed",
        len(df[df["Google Confirmed No Site"] == True]) if len(df) > 0 else 0,
    )

    st.divider()

    # --- Charts ---
    if len(df) > 0:
        st.subheader("Top 15 Categories")
        cat_counts = df["Category"].value_counts().head(15)
        st.bar_chart(cat_counts)

        st.divider()

    # --- Data table ---
    st.subheader(f"Leads ({len(df)} results)")

    if len(df) > 0:
        edited_df = st.data_editor(
            df,
            column_config={
                "Google Maps URL": st.column_config.LinkColumn("Google Maps URL"),
                "Contacted": st.column_config.CheckboxColumn("Contacted"),
            },
            disabled=[
                "Name", "Phone", "Address", "City", "State", "Category", "Sector",
                "Website Status", "Rating", "Reviews", "Photos", "Score",
                "Score Breakdown", "Google Confirmed No Site", "Google Maps URL",
                "Notes", "Scraped At",
            ],
            hide_index=True,
            use_container_width=True,
        )

        if st.button("Save Contact Status Changes"):
            _save_contacted_changes(db, df, edited_df)
            st.success("Changes saved!")
            st.rerun()

        st.divider()

        # --- Export ---
        st.subheader("Export")
        exp_col1, exp_col2 = st.columns(2)

        with exp_col1:
            csv_data = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", csv_data, "leads.csv", "text/csv")

        with exp_col2:
            buffer = BytesIO()
            df.to_excel(buffer, index=False, engine="openpyxl")
            st.download_button(
                "Download Excel",
                buffer.getvalue(),
                "leads.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    else:
        st.info("No leads match the current filters.")

    db.close()


def _save_contacted_changes(db, original_df: pd.DataFrame, edited_df: pd.DataFrame):
    """Persist contacted status changes to the database."""
    if "Google Maps URL" not in original_df.columns:
        return

    for idx in range(len(original_df)):
        orig_contacted = original_df.iloc[idx].get("Contacted", False)
        new_contacted = edited_df.iloc[idx].get("Contacted", False)

        if orig_contacted != new_contacted:
            maps_url = original_df.iloc[idx]["Google Maps URL"]
            biz = (
                db.query(Business)
                .filter(Business.google_maps_url == maps_url)
                .first()
            )
            if biz:
                biz.contacted = bool(new_contacted)

    db.commit()


if __name__ == "__main__":
    main()
