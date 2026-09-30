"""
CLI Batch Ingestion Script
Usage: python ingest.py /path/to/daily_sales.xlsx
"""
import sys
import pandas as pd
from db import init_db, ingest_dataframe

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest.py <sales_file.xlsx>")
        sys.exit(1)

    file_path = sys.argv[1]
    init_db()
    sheets = pd.read_excel(file_path, sheet_name=None)

    for name, df in sheets.items():
        try:
            res = ingest_dataframe(df, file_path)
            print(
                f"[{name}] Read: {res['read']} | Inserted: {res['inserted']} | Duplicates Skipped: {res['duplicates_skipped']}")
        except ValueError as err:
            print(f"[{name}] Skipped: {err}")
