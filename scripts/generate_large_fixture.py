"""
Generates a large-scale test fixture for DataMedic stress testing.

Outputs:
  data/orders_large_clean.csv   — ~5,000 rows of plausible, consistent e-commerce data
  data/orders_large_messy.csv   — same rows, with injected defects
  data/defect_manifest.csv      — ground truth: which row has which defect(s)

Everything is deterministic (seed=42). Re-running produces identical files.
"""

import csv
import json
import random
import copy
from datetime import datetime, timedelta
from pathlib import Path


SEED = 42
NUM_ROWS = 5000
OUTPUT_DIR = Path(__file__).resolve().parent.parent / 'data'

CLEAN_CSV = OUTPUT_DIR / 'orders_large_clean.csv'
MESSY_CSV = OUTPUT_DIR / 'orders_large_messy.csv'
MANIFEST_CSV = OUTPUT_DIR / 'defect_manifest.csv'

COLUMNS = ['order_id', 'customer_email', 'price', 'transaction_id', 'order_date']

FIRST_NAMES = [
    'alice', 'bob', 'charlie', 'david', 'eve', 'frank', 'grace', 'heidi',
    'ivan', 'judy', 'kevin', 'laura', 'mallory', 'nina', 'oscar', 'peggy',
    'quentin', 'romeo', 'sybil', 'trent', 'uma', 'victor', 'wendy', 'xander',
    'yasmin', 'zach', 'aria', 'blake', 'casey', 'drew', 'eli', 'fiona',
    'gabe', 'harper', 'iris', 'jude', 'kai', 'luna', 'miles', 'nora',
    'owen', 'pia', 'quinn', 'ray', 'sam', 'tara', 'uri', 'val', 'wren', 'zoe',
]
DOMAINS = ['example.com', 'mail.com', 'shop.net', 'test.org', 'inbox.io']

START_DATE = datetime(2026, 1, 1)
DATE_RANGE_DAYS = 200


def generate_clean_rows(rng):
    """Produces 5000 internally consistent e-commerce order rows."""
    rows = []
    txn_counter = 100000

    for i in range(NUM_ROWS):
        order_id = 10001 + i
        name = rng.choice(FIRST_NAMES)
        domain = rng.choice(DOMAINS)
        email = f"{name}{rng.randint(1, 999)}@{domain}"

        # Realistic price distribution: most orders $5-$200, occasional high-value
        price_bucket = rng.random()
        if price_bucket < 0.70:
            price = round(rng.uniform(5.0, 80.0), 2)
        elif price_bucket < 0.90:
            price = round(rng.uniform(80.0, 200.0), 2)
        elif price_bucket < 0.97:
            price = round(rng.uniform(200.0, 500.0), 2)
        else:
            price = round(rng.uniform(500.0, 2000.0), 2)

        txn_id = f"txn_{txn_counter}"
        txn_counter += 1

        days_offset = rng.randint(0, DATE_RANGE_DAYS)
        order_date = (START_DATE + timedelta(days=days_offset)).strftime('%Y-%m-%d')

        rows.append({
            'order_id': order_id,
            'customer_email': email,
            'price': price,
            'transaction_id': txn_id,
            'order_date': order_date,
        })

    return rows


DEFECT_TYPE_TO_COLUMNS = {
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


def inject_defects(rows, rng):
    """Injects defects into a copy of the clean rows. Returns (messy_rows, manifest).

    Defect categories:
      A = Covered by existing checks
      B = Not covered by any existing check
      C = Unusual but legitimate (should NOT be flagged)
    """
    messy = copy.deepcopy(rows)
    manifest = []

    # Tracks (row_index, column) -> index in manifest, so we can detect
    # when a later injection overwrites a cell already claimed by an earlier entry
    cell_owners = {}

    def record_entry(entry):
        """Appends entry to manifest with effective=True, then checks for
        same-cell collisions and marks the earlier entry as shadowed."""
        entry['effective'] = True
        manifest.append(entry)
        entry_idx = len(manifest) - 1
        for col in DEFECT_TYPE_TO_COLUMNS[entry['defect_type']]:
            cell_key = (entry['row_index'], col)
            if cell_key in cell_owners:
                manifest[cell_owners[cell_key]]['effective'] = False
            cell_owners[cell_key] = entry_idx

    # Pre-select row indices for each defect type, avoiding overlap where needed
    all_indices = list(range(NUM_ROWS))
    rng.shuffle(all_indices)
    pointer = 0

    def take(n):
        nonlocal pointer
        selected = all_indices[pointer:pointer + n]
        pointer += n
        return selected

    # =========================================================================
    # CATEGORY A: Defects existing checks SHOULD catch
    # =========================================================================

    # A1: Duplicate transaction_id (existing check: dup on transaction_id)
    dup_txn_indices = take(30)
    dup_pairs = [(dup_txn_indices[i], dup_txn_indices[i+1]) for i in range(0, 30, 2)]
    for orig_idx, dup_idx in dup_pairs:
        messy[dup_idx]['transaction_id'] = messy[orig_idx]['transaction_id']
        record_entry({
            'row_index': dup_idx,
            'order_id': messy[dup_idx]['order_id'],
            'defect_type': 'duplicate_transaction_id',
            'category': 'A_covered',
            'description': f"transaction_id copied from row {orig_idx}",
        })

    # A2: Null price (existing check: price.isna)
    null_price_indices = take(20)
    for idx in null_price_indices:
        messy[idx]['price'] = ''
        record_entry({
            'row_index': idx,
            'order_id': messy[idx]['order_id'],
            'defect_type': 'null_price',
            'category': 'A_covered',
            'description': 'Price set to empty string (will parse as NaN)',
        })

    # A3: Zero price (existing check: price == 0)
    zero_price_indices = take(12)
    for idx in zero_price_indices:
        messy[idx]['price'] = 0
        record_entry({
            'row_index': idx,
            'order_id': messy[idx]['order_id'],
            'defect_type': 'zero_price',
            'category': 'A_covered',
            'description': 'Price set to exactly 0',
        })

    # A4: Null customer_email (existing check: baseline drift catches this)
    null_email_indices = take(15)
    for idx in null_email_indices:
        messy[idx]['customer_email'] = ''
        record_entry({
            'row_index': idx,
            'order_id': messy[idx]['order_id'],
            'defect_type': 'null_customer_email',
            'category': 'A_covered',
            'description': 'Email set to empty (baseline drift should fire)',
        })

    # =========================================================================
    # CATEGORY B: Defects NOTHING currently covers
    # =========================================================================

    # B1: Negative price — monitor checks for null and zero but never for negative
    negative_price_indices = take(10)
    for idx in negative_price_indices:
        messy[idx]['price'] = round(-rng.uniform(5.0, 100.0), 2)
        record_entry({
            'row_index': idx,
            'order_id': messy[idx]['order_id'],
            'defect_type': 'negative_price',
            'category': 'B_uncovered',
            'description': f"Price set to {messy[idx]['price']} (negative)",
        })

    # B2: Future order_date — dates well past today, indicating clock/timezone bug
    future_date_indices = take(8)
    for idx in future_date_indices:
        future = datetime(2028, 6, 15) + timedelta(days=rng.randint(0, 365))
        messy[idx]['order_date'] = future.strftime('%Y-%m-%d')
        record_entry({
            'row_index': idx,
            'order_id': messy[idx]['order_id'],
            'defect_type': 'future_date',
            'category': 'B_uncovered',
            'description': f"order_date set to {messy[idx]['order_date']} (far future)",
        })

    # B3: Wrong date format — DD/MM/YYYY instead of YYYY-MM-DD
    bad_format_date_indices = take(10)
    for idx in bad_format_date_indices:
        orig = messy[idx]['order_date']
        parts = orig.split('-')
        messy[idx]['order_date'] = f"{parts[2]}/{parts[1]}/{parts[0]}"
        record_entry({
            'row_index': idx,
            'order_id': messy[idx]['order_id'],
            'defect_type': 'wrong_date_format',
            'category': 'B_uncovered',
            'description': f"order_date changed from {orig} to {messy[idx]['order_date']}",
        })

    # B4: Malformed email — missing @ or domain, but not empty
    bad_email_indices = take(12)
    for idx in bad_email_indices:
        variant = rng.choice(['no_at', 'no_domain', 'double_at', 'spaces'])
        orig = messy[idx]['customer_email']
        if variant == 'no_at':
            messy[idx]['customer_email'] = orig.replace('@', '')
        elif variant == 'no_domain':
            messy[idx]['customer_email'] = orig.split('@')[0] + '@'
        elif variant == 'double_at':
            messy[idx]['customer_email'] = orig.replace('@', '@@')
        elif variant == 'spaces':
            messy[idx]['customer_email'] = f"  {orig}  "
        record_entry({
            'row_index': idx,
            'order_id': messy[idx]['order_id'],
            'defect_type': 'malformed_email',
            'category': 'B_uncovered',
            'description': f"Email corrupted ({variant}): '{messy[idx]['customer_email']}'",
        })

    # B5: Duplicate order_id — monitor only checks transaction_id dups, not order_id
    dup_orderid_indices = take(8)
    dup_oid_pairs = [(dup_orderid_indices[i], dup_orderid_indices[i+1]) for i in range(0, 8, 2)]
    for orig_idx, dup_idx in dup_oid_pairs:
        messy[dup_idx]['order_id'] = messy[orig_idx]['order_id']
        record_entry({
            'row_index': dup_idx,
            'order_id': messy[dup_idx]['order_id'],
            'defect_type': 'duplicate_order_id',
            'category': 'B_uncovered',
            'description': f"order_id copied from row {orig_idx}",
        })

    # B6: Extreme outlier price — technically positive but absurdly high for e-commerce
    outlier_price_indices = take(6)
    for idx in outlier_price_indices:
        messy[idx]['price'] = round(rng.uniform(50000, 500000), 2)
        record_entry({
            'row_index': idx,
            'order_id': messy[idx]['order_id'],
            'defect_type': 'extreme_outlier_price',
            'category': 'B_uncovered',
            'description': f"Price set to {messy[idx]['price']} (extreme outlier)",
        })

    # B7: Whitespace-only transaction_id — not empty (not null), but effectively blank
    whitespace_txn_indices = take(5)
    for idx in whitespace_txn_indices:
        messy[idx]['transaction_id'] = '   '
        record_entry({
            'row_index': idx,
            'order_id': messy[idx]['order_id'],
            'defect_type': 'whitespace_transaction_id',
            'category': 'B_uncovered',
            'description': 'transaction_id set to whitespace-only string',
        })

    # =========================================================================
    # CATEGORY C: Unusual but LEGITIMATE — should NOT be flagged
    # =========================================================================

    # C1: Very low price — cheap but real (stickers, digital goods, clearance)
    low_price_indices = take(15)
    for idx in low_price_indices:
        messy[idx]['price'] = round(rng.uniform(0.01, 1.99), 2)
        record_entry({
            'row_index': idx,
            'order_id': messy[idx]['order_id'],
            'defect_type': 'very_low_price',
            'category': 'C_legitimate',
            'description': f"Price set to {messy[idx]['price']} (cheap but real)",
        })

    # C2: High-value order — expensive but legitimate (electronics, furniture)
    high_value_indices = take(10)
    for idx in high_value_indices:
        messy[idx]['price'] = round(rng.uniform(1500, 4999), 2)
        record_entry({
            'row_index': idx,
            'order_id': messy[idx]['order_id'],
            'defect_type': 'high_value_order',
            'category': 'C_legitimate',
            'description': f"Price set to {messy[idx]['price']} (expensive but legitimate)",
        })

    # C3: Weekend date — legitimate orders placed on Saturday/Sunday
    weekend_indices = take(20)
    for idx in weekend_indices:
        # Find the next Saturday from a base date
        base = START_DATE + timedelta(days=rng.randint(0, DATE_RANGE_DAYS))
        days_until_sat = (5 - base.weekday()) % 7
        sat = base + timedelta(days=days_until_sat)
        messy[idx]['order_date'] = sat.strftime('%Y-%m-%d')
        record_entry({
            'row_index': idx,
            'order_id': messy[idx]['order_id'],
            'defect_type': 'weekend_order',
            'category': 'C_legitimate',
            'description': f"Order date set to {messy[idx]['order_date']} (weekend, legitimate)",
        })

    # C4: Plus-addressed email — gmail-style user+tag@domain, valid but unusual
    plus_email_indices = take(10)
    for idx in plus_email_indices:
        parts = messy[idx]['customer_email'].split('@')
        if len(parts) == 2:
            tag = rng.choice(['promo', 'orders', 'test', 'work', 'personal'])
            messy[idx]['customer_email'] = f"{parts[0]}+{tag}@{parts[1]}"
        record_entry({
            'row_index': idx,
            'order_id': messy[idx]['order_id'],
            'defect_type': 'plus_addressed_email',
            'category': 'C_legitimate',
            'description': f"Email set to {messy[idx]['customer_email']} (plus-addressed, legitimate)",
        })

    # =========================================================================
    # MULTI-DEFECT ROWS: rows that already got one defect, inject a second
    # =========================================================================

    # Pick 8 rows that already have a defect, add a second one
    already_defective = [m['row_index'] for m in manifest if m['category'] != 'C_legitimate']
    rng.shuffle(already_defective)
    multi_defect_targets = already_defective[:8]

    for idx in multi_defect_targets:
        existing_types = [m['defect_type'] for m in manifest if m['row_index'] == idx]

        if 'null_price' not in existing_types and 'zero_price' not in existing_types and 'negative_price' not in existing_types:
            messy[idx]['order_date'] = '31/02/2026'
            record_entry({
                'row_index': idx,
                'order_id': messy[idx]['order_id'],
                'defect_type': 'impossible_date',
                'category': 'B_uncovered',
                'description': f"order_date set to 31/02/2026 (impossible date, second defect on this row)",
            })
        else:
            messy[idx]['customer_email'] = 'not-an-email'
            record_entry({
                'row_index': idx,
                'order_id': messy[idx]['order_id'],
                'defect_type': 'malformed_email',
                'category': 'B_uncovered',
                'description': f"Email set to 'not-an-email' (second defect on this row)",
            })

    return messy, manifest


def write_csv(path, rows):
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_manifest(path, manifest):
    fieldnames = ['row_index', 'order_id', 'defect_type', 'category', 'effective', 'description']
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest)


def main():
    rng = random.Random(SEED)

    print("Generating 5,000 clean rows...")
    clean_rows = generate_clean_rows(rng)

    print("Injecting defects...")
    messy_rows, manifest = inject_defects(clean_rows, rng)

    print(f"Writing {CLEAN_CSV}...")
    write_csv(CLEAN_CSV, clean_rows)

    print(f"Writing {MESSY_CSV}...")
    write_csv(MESSY_CSV, messy_rows)

    print(f"Writing {MANIFEST_CSV}...")
    write_manifest(MANIFEST_CSV, manifest)

    # Summary
    from collections import Counter
    type_counts = Counter(m['defect_type'] for m in manifest)
    cat_counts = Counter(m['category'] for m in manifest)
    multi = len([idx for idx in set(m['row_index'] for m in manifest)
                 if sum(1 for m2 in manifest if m2['row_index'] == idx) > 1])

    print(f"\n--- Summary ---")
    print(f"Clean rows:  {len(clean_rows)}")
    print(f"Messy rows:  {len(messy_rows)}")
    print(f"Total defect entries in manifest: {len(manifest)}")
    print(f"Rows with multiple defects: {multi}")
    print(f"\nBy category:")
    for cat, count in sorted(cat_counts.items()):
        print(f"  {cat}: {count}")
    print(f"\nBy type:")
    for dtype, count in sorted(type_counts.items()):
        print(f"  {dtype}: {count}")


if __name__ == '__main__':
    main()
