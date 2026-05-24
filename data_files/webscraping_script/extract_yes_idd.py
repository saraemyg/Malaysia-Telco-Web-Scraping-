"""
Extract Yes IDD rates from the embedded `var jsonIdd` in yes_roaming.html.
(The diagnostic confirmed this variable exists in the same dumped file.)

Usage:
  python extract_yes_idd.py
Outputs:
  yes_idd.csv  (one row per country Ã— plan_type)
"""
import json
import re
from pathlib import Path

import pandas as pd

BASE      = Path(__file__).parent
HTML_FILE = BASE / "data" / "html_debug" / "yes_roaming.html"
OUT_CSV   = BASE / "data" / "source" / "yes_idd.csv"


def extract_balanced(s: str, start: int) -> str | None:
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        c = s[i]
        if esc:
            esc = False
        elif c == "\\":
            esc = True
        elif c == '"':
            in_str = not in_str
        elif not in_str:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return s[start : i + 1]
    return None


def parse_money(raw) -> float | None:
    if raw is None:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", str(raw).replace(",", ""))
    return float(m.group(1)) if m else None


def main():
    if not HTML_FILE.exists():
        raise SystemExit(f"Missing {HTML_FILE}")
    html = HTML_FILE.read_text(encoding="utf-8", errors="ignore")
    idx = html.find("var jsonIdd")
    if idx == -1:
        raise SystemExit("Could not find 'var jsonIdd' â€” page structure may have changed.")
    brace_start = html.find("{", idx)
    raw = extract_balanced(html, brace_start)
    if not raw:
        raise SystemExit("Could not find matching closing brace.")
    data = json.loads(raw)
    print(f"Loaded {len(data)} country entries from yes_idd JSON")

    # First, inspect structure
    first_country = next(iter(data.values()))
    print(f"\nTop-level keys for first country: {list(first_country.keys())}")
    nested = {k: v for k, v in first_country.items() if isinstance(v, dict)}
    if nested:
        print(f"Nested plan-type keys: {list(nested.keys())}")
        sample_section = next(iter(nested.values()))
        print(f"Fields inside each plan-type section: {list(sample_section.keys())}")

    # Flatten: one row per (country Ã— plan_type)
    rows = []
    for country_key, info in data.items():
        if not isinstance(info, dict):
            continue
        country_name = info.get("country_name") or country_key
        country_slug = info.get("country_slug")
        # Find all dict-valued children (these are plan-type sections like prepaid/postpaid)
        section_keys = [k for k, v in info.items() if isinstance(v, dict)]
        if not section_keys:
            # Single-section schema
            rows.append({
                "brand": "Yes",
                "country": country_name,
                "country_slug": country_slug,
                "plan_type": "all",
                **{k: v for k, v in info.items() if not isinstance(v, dict)},
                "source_url": "https://www.yes.my/roaming/",
            })
            continue
        for plan_type in section_keys:
            section = info[plan_type]
            # Merge country-level scalars + section's scalars
            row = {
                "brand": "Yes",
                "country": country_name,
                "country_slug": country_slug,
                "plan_type": plan_type,
            }
            for k, v in section.items():
                if isinstance(v, (dict, list)):
                    row[k] = json.dumps(v)  # preserve nested as JSON string
                else:
                    row[k] = v
            # Try to derive numeric MYR columns from any common rate-like fields
            for src_field, num_field in [
                ("iddRate", "idd_rate_myr"),
                ("callRate", "call_rate_myr"),
                ("rate", "rate_myr"),
                ("smsRate", "sms_rate_myr"),
                ("ratePerMinute", "rate_per_minute_myr"),
            ]:
                if src_field in row and num_field not in row:
                    row[num_field] = parse_money(row[src_field])
            row["source_url"] = "https://www.yes.my/roaming/"
            rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False)
    print(f"\nWrote {len(df)} rows to {OUT_CSV}")
    print(f"Distinct countries: {df['country'].nunique()}")
    print(f"Plan types: {df['plan_type'].unique().tolist()}")
    print(f"\nAll columns captured:\n  " + "\n  ".join(df.columns))
    print(f"\nSample (first 5 rows):")
    print(df.head().to_string(index=False))


if __name__ == "__main__":
    main()

