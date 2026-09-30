"""
Database layer: SQLAlchemy models and duplicate-safe ETL for diagnostic center sales.
"""
from datetime import datetime
import pandas as pd
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker

DB_URL = "sqlite:///diagnostic_sales.db"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sales_date = Column(Date, nullable=False, index=True)
    invoice_no = Column(String, nullable=False, index=True)
    department = Column(String, nullable=False, index=True)
    item_no = Column(String)
    item_name = Column(String, nullable=False)
    item_rate = Column(Float, default=0.0)
    item_qty = Column(Float, default=0.0)
    cancel_qty = Column(Float, default=0.0)
    net_qty = Column(Float, default=0.0)
    item_total = Column(Float, default=0.0)
    vat = Column(Float, default=0.0)
    emr_charge = Column(Float, default=0.0)
    serv_charge = Column(Float, default=0.0)
    total_sale = Column(Float, default=0.0)
    referral_doctor = Column(String, index=True)
    mpo_name = Column(String, index=True)
    source_file = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Composite uniqueness ensures identical re-uploads never create duplicate lines
    __table_args__ = (
        UniqueConstraint(
            "sales_date", "invoice_no", "item_no", "item_name", name="uq_txn_line"
        ),
    )


def init_db():
    """Create all tables and indexes if they do not already exist."""
    Base.metadata.create_all(engine)


def ingest_dataframe(df: pd.DataFrame, source_file: str = "upload.xlsx") -> dict:
    """
    Cleans raw uploaded data, calculates net metrics, and inserts cleanly.
    Idempotent: Uses INSERT OR IGNORE to skip existing records automatically.
    """
    required = {"Sales Date", "Invoice No", "Department", "Item Name"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Uploaded file missing essential columns: {missing}")

    clean = df.dropna(subset=["Sales Date", "Invoice No", "Item Name"]).copy()
    clean["Sales Date"] = pd.to_datetime(clean["Sales Date"], errors="coerce")
    clean = clean.dropna(subset=["Sales Date"])

    num_cols = [
        "Item Rate", "Item Qty.", "Cencel Qty", "Item Total",
        "VAT", "Emr. Charge", "Serv. Charge", "Total Sale"
    ]
    for c in num_cols:
        clean[c] = pd.to_numeric(clean[c], errors="coerce").fillna(
            0.0) if c in clean.columns else 0.0

    if "Item No" not in clean.columns:
        clean["Item No"] = ""
    clean["Item No"] = clean["Item No"].astype(str).str.strip()

    records = []
    for _, r in clean.iterrows():
        qty = float(r["Item Qty."])
        cancel = float(r["Cencel Qty"])
        records.append({
            "sales_date": r["Sales Date"].date(),
            "invoice_no": str(r["Invoice No"]).strip(),
            "department": str(r["Department"]).strip(),
            "item_no": str(r["Item No"]).strip(),
            "item_name": str(r["Item Name"]).strip(),
            "item_rate": float(r["Item Rate"]),
            "item_qty": qty,
            "cancel_qty": cancel,
            "net_qty": qty - cancel,  # Auto net metric
            "item_total": float(r["Item Total"]),
            "vat": float(r["VAT"]),
            "emr_charge": float(r["Emr. Charge"]),
            "serv_charge": float(r["Serv. Charge"]),
            "total_sale": float(r["Total Sale"]),
            "referral_doctor": str(r.get("Referral Doctor", "") or "SELF / UNASSIGNED").strip(),
            "mpo_name": str(r.get("MPO Name", "") or "DIRECT / UNASSIGNED").strip(),
            "source_file": source_file,
        })

    if not records:
        return {"inserted": 0, "read": 0, "duplicates_skipped": 0}

    with engine.begin() as conn:
        before = conn.execute(
            text("SELECT COUNT(*) FROM transactions")).scalar()
        conn.execute(
            text("""
            INSERT OR IGNORE INTO transactions (
                sales_date, invoice_no, department, item_no, item_name,
                item_rate, item_qty, cancel_qty, net_qty, item_total,
                vat, emr_charge, serv_charge, total_sale,
                referral_doctor, mpo_name, source_file
            ) VALUES (
                :sales_date, :invoice_no, :department, :item_no, :item_name,
                :item_rate, :item_qty, :cancel_qty, :net_qty, :item_total,
                :vat, :emr_charge, :serv_charge, :total_sale,
                :referral_doctor, :mpo_name, :source_file
            )
            """),
            records,
        )
        after = conn.execute(
            text("SELECT COUNT(*) FROM transactions")).scalar()

    inserted = after - before
    return {
        "inserted": inserted,
        "read": len(records),
        "duplicates_skipped": len(records) - inserted,
    }


def load_all() -> pd.DataFrame:
    """Load all records from SQLite into a Pandas DataFrame."""
    df = pd.read_sql("SELECT * FROM transactions", engine)
    if not df.empty:
        df["sales_date"] = pd.to_datetime(df["sales_date"])
        df["dow"] = df["sales_date"].dt.day_name()
    return df
