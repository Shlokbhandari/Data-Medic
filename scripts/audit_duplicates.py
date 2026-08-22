import pandas as pd
import re
from pathlib import Path

def audit_duplicates():
    data_dir = Path("data")
    clean_csv = data_dir / "orders_large_clean.csv"
    messy_csv = data_dir / "orders_large_messy.csv"
    manifest_csv = data_dir / "defect_manifest.csv"

    clean_df = pd.read_csv(clean_csv, dtype=str, keep_default_na=False)
    messy_df = pd.read_csv(messy_csv, dtype=str, keep_default_na=False)
    manifest_df = pd.read_csv(manifest_csv, dtype=str, keep_default_na=False)

    dup_types = ['duplicate_transaction_id', 'duplicate_order_id']
    dups = manifest_df[manifest_df['defect_type'].isin(dup_types)]

    count_ge_2 = 0
    count_eq_1 = 0
    rows_eq_1 = []

    print(f"{'Row':<5} | {'Defect Type':<26} | {'Source Row':<10} | {'Messy Val':<15} | {'Occurrences':<11} | {'Source Curr Val':<15} | {'Source Still Holds Val?'}")
    print("-" * 120)

    for _, row in dups.iterrows():
        defect_type = row['defect_type']
        manifest_row_idx = int(row['row_index'])
        desc = row['description']
        
        match = re.search(r'row (\d+)', desc)
        if match:
            source_row_idx = int(match.group(1))
        else:
            source_row_idx = None
            
        col = 'transaction_id' if defect_type == 'duplicate_transaction_id' else 'order_id'
        
        messy_val = messy_df.at[manifest_row_idx, col]
        occurrences = (messy_df[col] == messy_val).sum()
        
        source_curr_val = messy_df.at[source_row_idx, col] if source_row_idx is not None else "N/A"
        source_still_holds = (source_curr_val == messy_val)
        
        print(f"{manifest_row_idx:<5} | {defect_type:<26} | {source_row_idx:<10} | {messy_val:<15} | {occurrences:<11} | {source_curr_val:<15} | {source_still_holds}")
        
        if occurrences >= 2:
            count_ge_2 += 1
        elif occurrences == 1:
            count_eq_1 += 1
            rows_eq_1.append(manifest_row_idx)

    print("\n--- Summary ---")
    print(f"Total manifest entries: {len(dups)}")
    print(f"Occurrences >= 2: {count_ge_2}")
    print(f"Occurrences == 1: {count_eq_1}")
    if rows_eq_1:
        print(f"Row indices with exactly 1 occurrence: {', '.join(map(str, rows_eq_1))}")

if __name__ == "__main__":
    audit_duplicates()
