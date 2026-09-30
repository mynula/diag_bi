"""
Streamlit BI Dashboard for Medical Diagnostic Centers.
Run: streamlit run app.py
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import db as database
import analytics as an

st.set_page_config(page_title="Diagnostic Center BI",
                   layout="wide", page_icon="🏥")


def fmt(n):
    return f"{n:,.0f}"


database.init_db()
df = database.load_all()

if df.empty:
    st.warning(
        "⚠️ No data in database yet. Go to 'Data Upload' in the sidebar or run: python ingest.py Sale_data.xlsx")
    st.stop()

min_d, max_d = df["sales_date"].min(), df["sales_date"].max()

st.sidebar.title("🏥 Navigation & Filters")
start, end = st.sidebar.date_input(
    "Date Range",
    (min_d.date(), max_d.date()),
    min_value=min_d.date(),
    max_value=max_d.date(),
)

view = st.sidebar.radio(
    "Modules",
    [
        "A · Executive Snapshot",
        "B · Specialized Diagnostics Engine",
        "C · Doctor CRM & Risk Monitor",
        "D · MPO Field Force Tracker",
        "E · Patient Basket & Cross-Sell",
        "F · Dynamic Targets & Forecasting",
        "📁 Data Upload",
    ],
)

dff = an.filter_range(df, start, end)

# ----------------- MODULE A -----------------
if view.startswith("A"):
    st.header("📈 Executive Snapshot & Daily Run Rates")
    k = an.kpis(dff)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Gross Revenue (BDT)", fmt(k["gross_revenue"]))
    c2.metric("Invoices", fmt(k["invoices"]))
    c3.metric("Tests Conducted", fmt(k["tests_conducted"]))
    c4.metric("Avg Ticket (BDT)", fmt(k["avg_ticket"]))
    c5.metric("Daily Run Rate (BDT)", fmt(k["daily_run_rate"]))

    st.subheader("Daily Revenue & 7-Day Moving Average")
    trend = an.daily_trend(dff)
    fig_trend = go.Figure()
    fig_trend.add_bar(
        x=trend.index, y=trend["revenue"], name="Daily Revenue", marker_color="#1f77b4")
    fig_trend.add_scatter(
        x=trend.index,
        y=trend["revenue"].rolling(7, min_periods=1).mean(),
        name="7-Day Moving Avg",
        line=dict(color="#ff7f0e", width=3),
    )
    st.plotly_chart(fig_trend, use_container_width=True)

    st.subheader("Day-of-Week Rhythm (Peak Volume vs. High-Ticket Slump)")
    dow = an.day_of_week(dff).reset_index()
    fig_dow = go.Figure()
    fig_dow.add_bar(x=dow["dow"], y=dow["revenue"],
                    name="Total Revenue (BDT)", marker_color="#2ca02c")
    fig_dow.add_scatter(
        x=dow["dow"], y=dow["avg_ticket"], name="Avg Ticket (BDT)", yaxis="y2", line=dict(color="#d62728", width=3)
    )
    fig_dow.update_layout(yaxis2=dict(
        overlaying="y", side="right", title="Avg Ticket (BDT)"))
    st.plotly_chart(fig_dow, use_container_width=True)

# ----------------- MODULE B -----------------
elif view.startswith("B"):
    st.header("🧬 Specialized Diagnostics & Revenue Engine")
    dep = an.department_breakdown(dff).reset_index()

    col1, col2 = st.columns([3, 2])
    with col1:
        st.plotly_chart(
            px.pie(dep, names="department", values="revenue",
                   hole=0.45, title="Department Revenue Share"),
            use_container_width=True,
        )
    with col2:
        st.dataframe(dep.style.format(
            {"revenue": fmt, "share_pct": "{:.1f}%"}), use_container_width=True, height=450)

    st.subheader("Hero Product Anchors (Top Margin & Volume Drivers)")
    heroes = an.hero_products(dff, top=15)
    st.dataframe(
        heroes.style.format({"revenue": fmt, "qty": fmt, "avg_rate": fmt,
                            "share_pct": "{:.1f}%", "cum_share_pct": "{:.1f}%"}),
        use_container_width=True,
    )

# ----------------- MODULE C -----------------
elif view.startswith("C"):
    st.header("🩺 Doctor Referral CRM & Concentration Risk")
    docs = an.doctor_concentration(dff)
    churned, per_doc = an.churn_detector(dff)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Referrers", len(docs))
    c2.metric("Top 10 Referrer Share",
              f"{docs.head(10)['share_pct'].sum():.1f}%")
    c3.metric("Top Doctor Dependency", f"{docs.iloc[0]['share_pct']:.1f}%")
    c4.metric("One-and-Done Doctors",
              f"{len(churned)} ({len(churned)/max(len(per_doc), 1)*100:.0f}%)")

    st.subheader("Top Referrers Watchlist")
    st.dataframe(docs.head(20).style.format(
        {"revenue": fmt, "avg_ticket": fmt, "share_pct": "{:.1f}%"}), use_container_width=True)

    st.subheader("⚠️ One-and-Done Churn Detector (Reactivation Campaign List)")
    st.caption("Doctors who referred only 1 patient in the selected timeframe. High-leverage targets for field reactivation.")
    churn_view = churned.reset_index().rename(
        columns={"referral_doctor": "Doctor Name"})
    st.dataframe(churn_view.style.format(
        {"revenue": fmt}), use_container_width=True, height=350)
    st.download_button(
        "⬇️ Download Reactivation CSV",
        churn_view.to_csv(index=False).encode(),
        "doctor_reactivation_list.csv",
        "text/csv",
    )

# ----------------- MODULE D -----------------
elif view.startswith("D"):
    st.header("👔 MPO Field Force Performance Tracker")
    mpo = an.mpo_performance(dff).reset_index()

    st.plotly_chart(
        px.bar(mpo, x="mpo_name", y="revenue", color="revenue",
               title="Revenue Generated by MPO", color_continuous_scale="Blues"),
        use_container_width=True,
    )
    st.dataframe(mpo.style.format(
        {"revenue": fmt, "avg_ticket": fmt, "share_pct": "{:.1f}%"}), use_container_width=True)

    walkin = dff[dff["mpo_name"] == "DIRECT / UNASSIGNED"]["total_sale"].sum()
    st.metric("Walk-In / Unassigned Direct Revenue", fmt(walkin),
              f"{walkin/max(dff['total_sale'].sum(), 1)*100:.1f}% of total")

# ----------------- MODULE E -----------------
elif view.startswith("E"):
    st.header("🛒 Patient Basket & Cross-Selling Analytics")
    b = an.basket_analysis(dff)

    c1, c2, c3 = st.columns(3)
    c1.metric("Single-Test Invoices", f"{b['single_test_pct']:.1f}%")
    c2.metric("Multi-Test Bundles", f"{b['multi_test_pct']:.1f}%")
    c3.metric("Avg Tests / Invoice", f"{b['avg_items']:.2f}")

    dist = b["distribution"].head(8)
    st.plotly_chart(
        px.bar(x=dist.index.astype(str), y=dist.values, labels={
               "x": "Tests per Invoice", "y": "Number of Invoices"}, title="Basket Size Distribution"),
        use_container_width=True,
    )

# ----------------- MODULE F -----------------
elif view.startswith("F"):
    st.header("🎯 Dynamic MPO Targets & Growth Forecasting")
    global_growth = st.slider(
        "Global Company Growth Target (%)", -10.0, 50.0, 15.0, step=1.0)

    mpo = an.mpo_performance(dff)
    st.subheader("Individual MPO Multipliers")
    cols = st.columns(3)
    multipliers = {}
    for i, rep in enumerate(mpo.index):
        with cols[i % 3]:
            multipliers[rep] = st.number_input(
                f"{rep[:25]} Multiplier", min_value=0.5, max_value=3.0, value=1.0, step=0.1)

    targets_df = an.targets(dff, global_growth, multipliers)
    st.subheader("Forecasted Target Matrix")
    st.dataframe(targets_df.style.format(
        {"baseline_revenue": fmt, "target_revenue": fmt, "uplift": fmt}), use_container_width=True)
    st.download_button(
        "⬇️ Export Target Sheet (CSV)",
        targets_df.to_csv(index=False).encode(),
        f"mpo_target_sheet_{global_growth:.0f}pct.csv",
        "text/csv",
    )

# ----------------- MODULE UPLOAD -----------------
else:
    st.header("📁 Daily Sales Data Upload")
    uploaded = st.file_uploader(
        "Upload Excel File (e.g. daily sales ledger)", type=["xlsx", "xls"])
    if uploaded is not None:
        sheets = pd.read_excel(uploaded, sheet_name=None)
        total_inserted = 0
        for sheet_name, frame in sheets.items():
            try:
                res = database.ingest_dataframe(frame, uploaded.name)
                total_inserted += res["inserted"]
                st.success(
                    f"Sheet '{sheet_name}': Read {res['read']} rows, Inserted {res['inserted']} new, Skipped {res['duplicates_skipped']} duplicates.")
            except Exception as e:
                st.error(f"Sheet '{sheet_name}' error: {e}")
        if total_inserted > 0:
            st.cache_data.clear()
            st.rerun()
