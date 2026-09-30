"""
Analytics and KPI aggregation functions across all functional modules.
"""
import pandas as pd

DOW_ORDER = ["Saturday", "Sunday", "Monday",
             "Tuesday", "Wednesday", "Thursday", "Friday"]


def filter_range(df: pd.DataFrame, start, end) -> pd.DataFrame:
    mask = (df["sales_date"] >= pd.Timestamp(start)) & (
        df["sales_date"] <= pd.Timestamp(end))
    return df[mask]


def kpis(df: pd.DataFrame) -> dict:
    inv = df.groupby("invoice_no")["total_sale"].sum()
    days_count = max(df["sales_date"].dt.date.nunique(), 1)
    single_item_inv = (df.groupby("invoice_no")[
                       "item_name"].nunique() == 1).sum()
    return {
        "gross_revenue": df["total_sale"].sum(),
        "net_revenue": df.loc[df["net_qty"] > 0, "total_sale"].clip(lower=0).sum(),
        "invoices": df["invoice_no"].nunique(),
        "tests_conducted": df["item_qty"].sum(),
        "cancelled_tests": df["cancel_qty"].sum(),
        "avg_ticket": inv.mean() if not inv.empty else 0.0,
        "median_ticket": inv.median() if not inv.empty else 0.0,
        "days": days_count,
        "daily_run_rate": df["total_sale"].sum() / days_count,
        "single_test_invoices": single_item_inv,
    }


def day_of_week(df: pd.DataFrame) -> pd.DataFrame:
    inv = df.groupby(["invoice_no", "dow"]).agg(
        total=("total_sale", "sum")).reset_index()
    g = inv.groupby("dow").agg(invoices=("total", "count"),
                               avg_ticket=("total", "mean"))
    g["revenue"] = df.groupby("dow")["total_sale"].sum()
    return g.reindex(DOW_ORDER).fillna(0)


def daily_trend(df: pd.DataFrame) -> pd.DataFrame:
    d = df.groupby(df["sales_date"].dt.date).agg(
        revenue=("total_sale", "sum"), invoices=("invoice_no", "nunique")
    )
    d.index = pd.to_datetime(d.index)
    return d


def department_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("department").agg(
        revenue=("total_sale", "sum"),
        tests=("net_qty", "sum"),
        unique_tests=("item_name", "nunique"),
    )
    total_rev = max(g["revenue"].sum(), 1)
    g["share_pct"] = g["revenue"] / total_rev * 100
    return g.sort_values("revenue", ascending=False)


def hero_products(df: pd.DataFrame, top: int = 15) -> pd.DataFrame:
    g = (
        df.groupby(["department", "item_name"])
        .agg(
            revenue=("total_sale", "sum"),
            qty=("net_qty", "sum"),
            avg_rate=("item_rate", "mean"),
        )
        .sort_values("revenue", ascending=False)
        .reset_index()
    )
    tot = max(df["total_sale"].sum(), 1)
    g["share_pct"] = g["revenue"] / tot * 100
    g["cum_share_pct"] = g["revenue"].cumsum() / tot * 100
    return g.head(top)


def doctor_concentration(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("referral_doctor").agg(
        revenue=("total_sale", "sum"),
        invoices=("invoice_no", "nunique"),
        mpo=("mpo_name", lambda x: x.mode().iat[0] if len(
            x.mode()) else "Unassigned"),
    )
    tot = max(g["revenue"].sum(), 1)
    g["share_pct"] = g["revenue"] / tot * 100
    g["avg_ticket"] = g["revenue"] / g["invoices"]
    return g.sort_values("revenue", ascending=False)


def churn_detector(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Detects doctors who referred only 1 invoice during the period."""
    per_doc = df.groupby("referral_doctor").agg(
        invoices=("invoice_no", "nunique"),
        revenue=("total_sale", "sum"),
        last_seen=("sales_date", "max"),
        mpo=("mpo_name", lambda x: x.mode().iat[0] if len(
            x.mode()) else "Unassigned"),
    )
    churned = per_doc[per_doc["invoices"] == 1].sort_values(
        "revenue", ascending=False)
    return churned, per_doc


def mpo_performance(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("mpo_name").agg(
        revenue=("total_sale", "sum"),
        invoices=("invoice_no", "nunique"),
        doctors=("referral_doctor", "nunique"),
    )
    tot = max(g["revenue"].sum(), 1)
    g["avg_ticket"] = g["revenue"] / g["invoices"]
    g["share_pct"] = g["revenue"] / tot * 100
    return g.sort_values("revenue", ascending=False)


def basket_analysis(df: pd.DataFrame) -> dict:
    per_inv = df.groupby("invoice_no")["item_name"].nunique()
    return {
        "single_test_pct": (per_inv == 1).mean() * 100,
        "multi_test_pct": (per_inv > 1).mean() * 100,
        "avg_items": per_inv.mean(),
        "distribution": per_inv.value_counts().sort_index(),
    }


def targets(df: pd.DataFrame, company_growth_pct: float, mpo_multipliers: dict = None) -> pd.DataFrame:
    mpo_multipliers = mpo_multipliers or {}
    base = mpo_performance(df)[["revenue", "invoices"]].rename(
        columns={"revenue": "baseline_revenue",
                 "invoices": "baseline_invoices"}
    )
    rows = []
    for mpo, r in base.iterrows():
        mult = float(mpo_multipliers.get(mpo, 1.0))
        target_rev = r["baseline_revenue"] * \
            (1 + company_growth_pct / 100) * mult
        rows.append({
            "mpo_name": mpo,
            "baseline_revenue": round(r["baseline_revenue"], 2),
            "company_growth_pct": company_growth_pct,
            "mpo_multiplier": mult,
            "target_revenue": round(target_rev, 2),
            "uplift": round(target_rev - r["baseline_revenue"], 2),
        })
    return pd.DataFrame(rows)
