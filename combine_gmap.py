"""
combine_gmap.py
───────────────
Combines all CSV files in gmap_data/ into a single deduplicated file.

USAGE
-----
    python combine_gmap.py
"""

import glob
import os
import pandas as pd

INPUT_DIR   = "gmap_data"
OUTPUT_FILE = os.path.join(INPUT_DIR, "all_combined.csv")

files = [f for f in glob.glob(os.path.join(INPUT_DIR, "*.csv"))
         if not f.endswith("all_combined.csv")]

if not files:
    print(f"No CSV files found in {INPUT_DIR}/")
    exit()

print(f"Found {len(files)} file(s):")
for f in sorted(files):
    print(f"  {f}")

df = pd.concat([pd.read_csv(f, encoding="utf-8-sig") for f in files], ignore_index=True)
before = len(df)

df = df.drop_duplicates(subset="Name", keep="first").reset_index(drop=True)
after = len(df)

df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

print(f"\n✅  Combined → {OUTPUT_FILE}")
print(f"   {before} total rows  →  {after} unique businesses  ({before - after} duplicates removed)")
