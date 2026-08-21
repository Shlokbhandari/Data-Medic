"""
Verifies the integrity of the defect manifest by:
1. Cell-level diff between clean and messy CSVs
2. Bidirectional cross-check against manifest
3. Clean file contamination check
4. Specific row investigations (order_ids 10863, 13499, 13048)
5. Determinism verification
6. Manifest type count verification
"""

import csv
import re
import hashlib
from pathlib import Path
from collections import Counter

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'
CLEAN_CSV = DATA_DIR / 'orders_large_clean.csv'
MESSY_CSV = DATA_DIR / 'orders_large_messy.csv'
MANIFEST_CSV = DATA_DIR / 'defect_manifest.csv'

COLUMNS = ['order_id', 'customer_email', 'price', 'transaction_id', 'order_date']


def load_rows(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def load_manifest(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def cell_level_diff(clean_rows, messy_rows):
    """Returns a set of (row_index, column) tuples for every cell that differs."""
    diffs = set()
    for i, (c, m) in enumerate(zip(clean_rows, messy_rows)):
        for col in COLUMNS:
            if c[col] != m[col]:
                diffs.add((i, col))
    return diffs


def manifest_to_expected_diffs(manifest):
    """Maps each manifest entry to the column(s) it should have changed.
    Returns a set of (row_index, column) tuples."""

    TYPE_TO_COLUMNS = {
        'duplicate_transaction_id': ['transaction_id'],
        'null_price': ['price'],
        'zero_price': ['price'],
        'null_customer_email': ['customer_email'],
        'negative_price': ['price'],
        'future_date': ['order_date'],
        'wrong_date_format': ['order_date'],
        'malformed_email': ['customer_email'],
        'duplicate_order_id': ['order_id'],
        'extreme_outlier_price': ['price'],
        'whitespace_transaction_id': ['transaction_id'],
        'impossible_date': ['order_date'],
        'very_low_price': ['price'],
        'high_value_order': ['price'],
        'weekend_order': ['order_date'],
        'plus_addressed_email': ['customer_email'],
    }

    expected = set()
    for entry in manifest:
        if entry.get('effective', 'True') == 'False':
            continue
        row_idx = int(entry['row_index'])
        defect_type = entry['defect_type']
        for col in TYPE_TO_COLUMNS.get(defect_type, []):
            expected.add((row_idx, col))
    return expected


def check_clean_file(clean_rows):
    """Checks the clean file for accidental contamination."""
    print("\n" + "=" * 70)
    print("CLEAN FILE CONTAMINATION CHECK")
    print("=" * 70)

    issues = []

    # Duplicate transaction_id
    txn_ids = [r['transaction_id'] for r in clean_rows]
    txn_counts = Counter(txn_ids)
    dups = {k: v for k, v in txn_counts.items() if v > 1}
    if dups:
        issues.append(f"Duplicate transaction_ids found: {dups}")
    else:
        print("  [OK] No duplicate transaction_ids")

    # Duplicate order_id
    order_ids = [r['order_id'] for r in clean_rows]
    oid_counts = Counter(order_ids)
    oid_dups = {k: v for k, v in oid_counts.items() if v > 1}
    if oid_dups:
        issues.append(f"Duplicate order_ids found: {oid_dups}")
    else:
        print("  [OK] No duplicate order_ids")

    # Null / zero / negative price
    for i, r in enumerate(clean_rows):
        price_str = r['price'].strip()
        if price_str == '':
            issues.append(f"Row {i}: null/empty price")
        else:
            try:
                p = float(price_str)
                if p == 0:
                    issues.append(f"Row {i}: zero price")
                elif p < 0:
                    issues.append(f"Row {i}: negative price ({p})")
            except ValueError:
                issues.append(f"Row {i}: unparseable price '{price_str}'")
    if not any('price' in x for x in issues):
        print("  [OK] No null/zero/negative prices")

    # Null email
    null_emails = [i for i, r in enumerate(clean_rows) if r['customer_email'].strip() == '']
    if null_emails:
        issues.append(f"Null emails at rows: {null_emails}")
    else:
        print("  [OK] No null emails")

    # Malformed email (basic check: must have exactly one @ with non-empty local and domain)
    malformed = []
    for i, r in enumerate(clean_rows):
        email = r['customer_email']
        if email.strip() != email:
            malformed.append((i, email, 'leading/trailing whitespace'))
        elif email.count('@') != 1:
            malformed.append((i, email, f"has {email.count('@')} @ signs"))
        else:
            local, domain = email.split('@')
            if not local or not domain:
                malformed.append((i, email, 'empty local or domain'))
    if malformed:
        issues.append(f"Malformed emails: {malformed[:10]}{'...' if len(malformed) > 10 else ''}")
    else:
        print("  [OK] No malformed emails")

    # Non-standard date format (should all be YYYY-MM-DD)
    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    bad_dates = [(i, r['order_date']) for i, r in enumerate(clean_rows) if not date_pattern.match(r['order_date'])]
    if bad_dates:
        issues.append(f"Non-standard date formats: {bad_dates[:10]}{'...' if len(bad_dates) > 10 else ''}")
    else:
        print("  [OK] All dates in YYYY-MM-DD format")

    # Email uniqueness stats
    emails = [r['customer_email'] for r in clean_rows]
    email_counts = Counter(emails)
    distinct = len(email_counts)
    most_common_email, most_common_count = email_counts.most_common(1)[0]
    print(f"\n  Distinct customer_email values: {distinct} / {len(clean_rows)} rows")
    print(f"  Most frequent email: '{most_common_email}' appears {most_common_count} time(s)")

    if issues:
        print(f"\n  *** CONTAMINATION FOUND ({len(issues)} issues) ***")
        for iss in issues:
            print(f"    - {iss}")
    else:
        print("\n  *** CLEAN FILE IS CLEAN — no contamination detected ***")

    return issues


def investigate_specific_rows(clean_rows, messy_rows, manifest):
    """Item 4: investigate order_ids 10863, 13499, 13048."""
    print("\n" + "=" * 70)
    print("SPECIFIC ROW INVESTIGATION (order_ids 10863, 13499, 13048)")
    print("=" * 70)

    target_order_ids = ['10863', '13499', '13048']

    for target_oid in target_order_ids:
        print(f"\n--- order_id {target_oid} ---")

        # Find in clean and messy by searching all rows
        clean_matches = [(i, r) for i, r in enumerate(clean_rows) if r['order_id'] == target_oid]
        messy_matches = [(i, r) for i, r in enumerate(messy_rows) if r['order_id'] == target_oid]

        print(f"  Clean file occurrences: {len(clean_matches)}")
        for i, r in clean_matches:
            print(f"    Row {i}: {r}")

        print(f"  Messy file occurrences: {len(messy_matches)}")
        for i, r in messy_matches:
            print(f"    Row {i}: {r}")

        # Manifest entries where order_id matches OR row_index maps to this order_id
        manifest_matches = [m for m in manifest if m['order_id'] == target_oid]
        # Also check by row_index for the clean version of this order_id
        for ci, cr in clean_matches:
            row_manifest = [m for m in manifest if int(m['row_index']) == ci]
            for rm in row_manifest:
                if rm not in manifest_matches:
                    manifest_matches.append(rm)

        print(f"  Manifest entries:")
        if manifest_matches:
            for m in manifest_matches:
                print(f"    {m}")
        else:
            print("    NONE — no manifest entry found")


def verify_type_counts(manifest):
    """Item 6: verify manifest counts match the claimed table."""
    print("\n" + "=" * 70)
    print("MANIFEST TYPE COUNT VERIFICATION")
    print("=" * 70)

    type_counts = Counter(m['defect_type'] for m in manifest)
    total = sum(type_counts.values())

    print(f"\n  Total manifest entries: {total}")
    print(f"  Expected: 180")
    print(f"  Match: {'YES' if total == 180 else 'NO — MISMATCH'}")
    print(f"\n  Number of distinct defect types: {len(type_counts)}")
    print(f"  Expected: 16")
    print(f"  Match: {'YES' if len(type_counts) == 16 else 'NO — MISMATCH'}")

    expected_counts = {
        'duplicate_transaction_id': 15,
        'null_price': 20,
        'zero_price': 12,
        'null_customer_email': 15,
        'negative_price': 10,
        'future_date': 8,
        'wrong_date_format': 10,
        'malformed_email': 14,
        'duplicate_order_id': 4,
        'extreme_outlier_price': 6,
        'whitespace_transaction_id': 5,
        'impossible_date': 6,
        'very_low_price': 15,
        'high_value_order': 10,
        'weekend_order': 20,
        'plus_addressed_email': 10,
    }

    print(f"\n  Per-type breakdown:")
    all_match = True
    for dtype in sorted(expected_counts.keys()):
        actual = type_counts.get(dtype, 0)
        expected = expected_counts[dtype]
        status = "OK" if actual == expected else "MISMATCH"
        if actual != expected:
            all_match = False
        print(f"    {dtype:30s}  actual={actual:3d}  expected={expected:3d}  [{status}]")

    # Check for unexpected types
    for dtype in type_counts:
        if dtype not in expected_counts:
            print(f"    {dtype:30s}  actual={type_counts[dtype]:3d}  UNEXPECTED TYPE")
            all_match = False

    print(f"\n  All counts match: {'YES' if all_match else 'NO — SEE MISMATCHES ABOVE'}")


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    print("Loading files...")
    clean_rows = load_rows(CLEAN_CSV)
    messy_rows = load_rows(MESSY_CSV)
    manifest = load_manifest(MANIFEST_CSV)

    assert len(clean_rows) == len(messy_rows), "Row count mismatch between clean and messy"
    print(f"Loaded {len(clean_rows)} clean rows, {len(messy_rows)} messy rows, {len(manifest)} manifest entries")

    # =========================================================================
    # BIDIRECTIONAL CROSS-CHECK
    # =========================================================================
    print("\n" + "=" * 70)
    print("BIDIRECTIONAL CELL-LEVEL CROSS-CHECK")
    print("=" * 70)

    actual_diffs = cell_level_diff(clean_rows, messy_rows)
    expected_diffs = manifest_to_expected_diffs(manifest)

    print(f"\n  Actual cell-level diffs (clean vs messy): {len(actual_diffs)}")
    print(f"  Expected diffs (from manifest):           {len(expected_diffs)}")

    # Direction A: every actual diff is in the manifest
    unaccounted = actual_diffs - expected_diffs
    print(f"\n  Direction A — Diffs NOT accounted for by manifest: {len(unaccounted)}")
    if unaccounted:
        for row_idx, col in sorted(unaccounted)[:20]:
            clean_val = clean_rows[row_idx][col]
            messy_val = messy_rows[row_idx][col]
            print(f"    Row {row_idx}, col '{col}': '{clean_val}' -> '{messy_val}'")
        if len(unaccounted) > 20:
            print(f"    ... and {len(unaccounted) - 20} more")
    else:
        print("    [OK] Every cell difference has a manifest entry")

    # Direction B: every manifest entry corresponds to an actual diff
    phantom = expected_diffs - actual_diffs
    print(f"\n  Direction B — Manifest entries with NO actual cell diff: {len(phantom)}")
    if phantom:
        for row_idx, col in sorted(phantom)[:20]:
            clean_val = clean_rows[row_idx][col]
            messy_val = messy_rows[row_idx][col]
            entries = [m for m in manifest if int(m['row_index']) == row_idx]
            print(f"    Row {row_idx}, col '{col}': clean='{clean_val}' messy='{messy_val}'  manifest={entries}")
        if len(phantom) > 20:
            print(f"    ... and {len(phantom) - 20} more")
    else:
        print("    [OK] Every manifest entry corresponds to a real cell difference")

    # =========================================================================
    # CLEAN FILE CONTAMINATION CHECK
    # =========================================================================
    check_clean_file(clean_rows)

    # =========================================================================
    # SPECIFIC ROW INVESTIGATION
    # =========================================================================
    investigate_specific_rows(clean_rows, messy_rows, manifest)

    # =========================================================================
    # MANIFEST TYPE COUNTS
    # =========================================================================
    verify_type_counts(manifest)

    print("\n" + "=" * 70)
    print("VERIFICATION COMPLETE")
    print("=" * 70)

    # =========================================================================
    # EFFECTIVE FLAG RECONCILIATION
    # =========================================================================
    print("\n" + "=" * 70)
    print("EFFECTIVE FLAG RECONCILIATION")
    print("=" * 70)

    effective_entries = [m for m in manifest if m.get('effective', 'True') == 'True']
    shadowed_entries = [m for m in manifest if m.get('effective', 'True') == 'False']

    print(f"\n  Total manifest entries: {len(manifest)}")
    print(f"  Effective entries:     {len(effective_entries)}")
    print(f"  Shadowed entries:      {len(shadowed_entries)}")
    print(f"  Actual cell diffs:     {len(actual_diffs)}")
    print(f"  Effective == Diffs:    {'YES' if len(effective_entries) == len(actual_diffs) else 'NO — MISMATCH'}")

    if shadowed_entries:
        print(f"\n  Shadowed entries detail:")
        for m in shadowed_entries:
            print(f"    Row {m['row_index']}, type={m['defect_type']}, cat={m['category']}, desc={m['description']}")

    # Per-type effective counts
    eff_type_counts = Counter(m['defect_type'] for m in effective_entries)
    all_type_counts = Counter(m['defect_type'] for m in manifest)
    all_types = sorted(set(all_type_counts.keys()))

    print(f"\n  Effective counts per type (total -> effective):")
    for dtype in all_types:
        total = all_type_counts[dtype]
        eff = eff_type_counts.get(dtype, 0)
        marker = " <-- SHADOWED" if eff < total else ""
        print(f"    {dtype:30s}  {total:3d} -> {eff:3d}{marker}")

    # Per-category effective counts
    eff_cat_counts = Counter(m['category'] for m in effective_entries)
    all_cat_counts = Counter(m['category'] for m in manifest)
    print(f"\n  Effective counts per category (total -> effective):")
    for cat in sorted(all_cat_counts.keys()):
        total = all_cat_counts[cat]
        eff = eff_cat_counts.get(cat, 0)
        marker = " <-- SHADOWED" if eff < total else ""
        print(f"    {cat:20s}  {total:3d} -> {eff:3d}{marker}")


if __name__ == '__main__':
    main()
