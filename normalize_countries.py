"""
normalize_countries.py
Normalizes variant country names in idd.csv to canonical names,
then deduplicates (brand, country, plan_type) by keeping the best-filled row.
Run after consolidate_idd.py (and after re-applying TuneTalk/U Mobile fixes).
"""
import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
from pathlib import Path

BASE = Path(__file__).parent

# ── Canonical name mapping ─────────────────────────────────────────────────
# Key = variant found in data, Value = canonical name
NORM = {
    # Antigua and Barbuda
    "Antigua & Barbuda":                    "Antigua and Barbuda",
    "Antigua And Barbuda":                  "Antigua and Barbuda",

    # Australia / territories
    "Australia - Christmas Island":         "Christmas Island",
    "Australia - Cocos Island":             "Cocos Islands",
    "Australian Territories":               "Australia",
    "Christmas Islands":                    "Christmas Island",

    # Bermuda
    "Bermuda & West Indies":                "Bermuda",

    # Bolivia (keep, no variants needed)

    # Bosnia and Herzegovina
    "Bosnia":                               "Bosnia and Herzegovina",
    "Bosnia & Herzegovina":                 "Bosnia and Herzegovina",
    "Bosnia Herzegovina":                   "Bosnia and Herzegovina",

    # Botswana
    "Bostwana":                             "Botswana",

    # British Virgin Islands
    "UK Virgin Islands":                    "British Virgin Islands",
    "USA UK Virgin Islands":                "British Virgin Islands",
    "Virgin Island (UK)":                   "British Virgin Islands",

    # Brunei
    "Brunei Darussalam":                    "Brunei",

    # Burundi
    "Burundi Kingdom":                      "Burundi",

    # Cape Verde
    "Cape Verde Island":                    "Cape Verde",
    "Cape Verde Islands":                   "Cape Verde",

    # Cayman Islands
    "Caymen Island":                        "Cayman Islands",

    # Chile (Easter Island is part of Chile)
    "Chile Easter Island":                  "Chile",

    # Congo (Republic of)
    "Congo Brazzaville":                    "Congo",

    # Democratic Republic of the Congo
    "Congo DR":                             "Democratic Republic of the Congo",
    "Congo Demoratic Rep. (formerly Zaire)":"Democratic Republic of the Congo",
    "D.R. Congo (Zaire)":                   "Democratic Republic of the Congo",
    "DR Congo":                             "Democratic Republic of the Congo",
    "Dem. Rep. of Congo":                   "Democratic Republic of the Congo",
    "Dem. Rep. of Congo (Zaire)":           "Democratic Republic of the Congo",
    "Zaire":                                "Democratic Republic of the Congo",

    # Cook Islands
    "Cook Island":                          "Cook Islands",

    # Cuba
    "Cuba-Guantanamo":                      "Cuba",

    # Dominican Republic (NOT Dominica)
    "Dominica Republic":                    "Dominican Republic",
    "Domincan Republic":                    "Dominican Republic",

    # Dominica (the island nation)
    "Dominica Island":                      "Dominica",

    # Faroe Islands
    "Faeroe Islands":                       "Faroe Islands",
    "Faroe islands":                        "Faroe Islands",

    # Fiji
    "Fiji Islands":                         "Fiji",

    # French Guiana
    "French Guiana (NR)":                   "French Guiana",
    "French Guyana":                        "French Guiana",

    # French Polynesia
    "French Polynesia (Tahiti)":            "French Polynesia",

    # Guernsey
    "Guernsey (United Kingdom)":            "Guernsey",

    # Guinea
    "Guinea +224)":                         "Guinea",
    "Guinea Republic":                      "Guinea",

    # Guinea-Bissau
    "Guinea - Bussau":                      "Guinea-Bissau",
    "Guinea Bissau":                        "Guinea-Bissau",

    # Hawaii / Alaska / Guam (US territories, separate dialing)
    "Haiwaii":                              "Hawaii",
    "USA - Hawaii":                         "Hawaii",
    "USA Hawaii":                           "Hawaii",
    "USA - Alaska":                         "Alaska",
    "USA Alaska":                           "Alaska",
    "USA - Guam":                           "Guam",
    "USA Guam":                             "Guam",
    "USA - Call 1800, 1855, 1866, 1877, 1883, 1888": "United States",

    # Haiti
    "Haiti Republic":                       "Haiti",

    # India
    "India (Aircel)":                       "India",

    # Indonesia (regional/operator variants)
    "Indonesia (Axis)":                     "Indonesia",
    "Indonesia_Batam":                      "Indonesia",
    "Indonesia_M-Excelcom":                 "Indonesia",
    "Indonesia_Telkomsel":                  "Indonesia",

    # Ireland
    "Ireland - Special Service":            "Ireland",

    # Isle of Man
    "Isle Of Man":                          "Isle of Man",
    "Isle of Man (United Kingdom)":         "Isle of Man",

    # Jersey
    "Jersey (United Kingdom)":              "Jersey",

    # Kiribati
    "Kiribati Republic":                    "Kiribati",

    # Korea
    "Korea North":                          "North Korea",
    "Korea South":                          "South Korea",

    # Kyrgyzstan
    "Kyrgyz Republic":                      "Kyrgyzstan",

    # Luxembourg
    "Luxembourg (+)":                       "Luxembourg",

    # Macau
    "Macau S.A.R":                          "Macau",

    # Marshall Islands
    "Marshall Island":                      "Marshall Islands",

    # Northern Mariana Islands
    "Mariana Islands":                      "Northern Mariana Islands",
    "Marianas Islands":                     "Northern Mariana Islands",
    "Northen Mariana Island":               "Northern Mariana Islands",
    "Saipan":                               "Northern Mariana Islands",

    # Mauritius
    "Mauritius Island":                     "Mauritius",

    # Moldova
    "Republic Of Moldova":                  "Moldova",

    # Morocco
    "Morroco":                              "Morocco",

    # Myanmar
    "Myanmar (Burma)":                      "Myanmar",

    # Nepal (operator variants)
    "Nepal_NTC":                            "Nepal",
    "Nepal_Ncell":                          "Nepal",

    # Niue
    "Niue Island":                          "Niue",

    # Norfolk Island
    "Norfolk Islands":                      "Norfolk Island",

    # Norway
    "Norway - Special Service":             "Norway",

    # Puerto Rico
    "Puerto Rico (+1-787/1-939)":           "Puerto Rico",

    # Reunion
    "Reunion Islands":                      "Reunion",
    "Reunion Mayotte":                      "Reunion",

    # Russia
    "Russian Federation":                   "Russia",
    "Tatarstan":                            "Russia",

    # Saint Helena
    "St Helena":                            "Saint Helena",
    "St. Helena":                           "Saint Helena",

    # Saint Kitts and Nevis
    "Saint Kitts & Nevis":                  "Saint Kitts and Nevis",
    "St. Kitts & Nevis":                    "Saint Kitts and Nevis",
    "St. Kitts And Nevis":                  "Saint Kitts and Nevis",
    "St. Kitts and Nevis":                  "Saint Kitts and Nevis",

    # Saint Lucia
    "Saint Lucia":                          "Saint Lucia",
    "St. Lucia":                            "Saint Lucia",

    # Saint Maarten
    "St Maarten":                           "Saint Maarten",
    "St. Maarten":                          "Saint Maarten",

    # Saint Pierre and Miquelon
    "St Pierre & Miquelon":                 "Saint Pierre and Miquelon",
    "St. Pierre & Miquelon":                "Saint Pierre and Miquelon",

    # Saint Vincent and the Grenadines
    "St VIncent & the Grenadines":          "Saint Vincent and the Grenadines",
    "St. Vincent & Grenadines":             "Saint Vincent and the Grenadines",
    "St. Vincent & the Grenadines":         "Saint Vincent and the Grenadines",
    "St. Vincent and The Grenadines":       "Saint Vincent and the Grenadines",

    # Samoa
    "Samoa (USA)":                          "American Samoa",
    "Samoa (Western)":                      "Samoa",
    "Samoa West":                           "Samoa",
    "Western Samoa":                        "Samoa",

    # Sao Tome and Principe
    "Sao Tome & Principe":                  "Sao Tome and Principe",

    # Slovakia
    "Slovak Republic":                      "Slovakia",
    "Slovakia Republic":                    "Slovakia",

    # Solomon Islands
    "Solomon Island":                       "Solomon Islands",

    # South Sudan
    "Sudan South":                          "South Sudan",

    # Suriname
    "Surinam":                              "Suriname",

    # Tokelau
    "Tokelau Island":                       "Tokelau",

    # Tonga
    "Tonga Island":                         "Tonga",

    # Trinidad and Tobago
    "Trinidad & Tobago":                    "Trinidad and Tobago",
    "Trinidad And Tobago":                  "Trinidad and Tobago",

    # Turkey (encoding corruption)
    "T\x00efrkiye":                         "Turkey",
    "T�rkiye":                         "Turkey",
    "T\xc3\xbcrkiye":                       "Turkey",

    # Turks and Caicos Islands
    "Turks & Caicos":                       "Turks and Caicos Islands",
    "Turks & Caicos Island":                "Turks and Caicos Islands",
    "Turks & Caicos Islands":               "Turks and Caicos Islands",
    "Turks And Caicos Islands":             "Turks and Caicos Islands",
    "Turks and Caicos":                     "Turks and Caicos Islands",

    # United Arab Emirates
    "UAE":                                  "United Arab Emirates",

    # United Kingdom
    "UK":                                   "United Kingdom",
    "United Kingdom - Premium Number":      "United Kingdom",
    "United Kingdom Premium Number":        "United Kingdom",

    # United States
    "USA":                                  "United States",
    "USA - Mainland":                       "United States",
    "United States of America":             "United States",
    "United States of America (USA)":       "United States",

    # US Virgin Islands
    "U.S Virgin Islands":                   "US Virgin Islands",
    "USA US Virgin Islands":                "US Virgin Islands",
    "Virgin Island (US)":                   "US Virgin Islands",

    # Vanuatu
    "Vanuatu/New Hebrides":                 "Vanuatu",

    # Vatican
    "Vatican city":                         "Vatican",

    # Venezuela
    "Venezula":                             "Venezuela",

    # Vietnam
    "Vietnam Domestic Premium Service":     "Vietnam",

    # Wallis and Futuna
    "Wallis & Futuna":                      "Wallis and Futuna",
    "Wallis & Futuna Islands":              "Wallis and Futuna",

    # Yemen
    "Yemen (+)":                            "Yemen",
    "Yemen (Arab Republic)":                "Yemen",
    "Yemen Republic":                       "Yemen",
    "Yemen South":                          "Yemen",

    # Yugoslavia → Serbia (successor state)
    "Yugoslavia":                           "Serbia",

    # Bonaire
    "Bonaire and Saint Eustatius":          "Bonaire",

    # Libya
    "Libyan Arab Jamahiri":                 "Libya",

    # Timor-Leste
    "East Timor":                           "Timor-Leste",
    "Timor Leste":                          "Timor-Leste",

    # Azores / Madeira (normalise the Portugal - prefix variants)
    "Portugal - Azores":                    "Azores",
    "Portugal - Madeira":                   "Madeira",

    # Satellites (standardise format)
    "Ellipso Satellite":                    "Satellite (Ellipso)",
    "Inmarsat":                             "Satellite (Inmarsat)",
    "Satellite - Emsat":                    "Satellite (Emsat)",
    "Satellite - Iridium":                  "Satellite (Iridium)",
    "Satellite - Thuraya":                  "Satellite (Thuraya)",
    "Satellite - UPTN":                     "Satellite (UPTN)",
    "Satellite 881":                        "Satellite (881)",
    "Satellite 882":                        "Satellite (882)",
    "Satellite 883":                        "Satellite (883)",
}

# ── Also handle Turkey's corrupted encoding via startswith ────────────────
def normalize_country(name):
    if pd.isna(name):
        return name
    s = str(name).strip()
    if s in NORM:
        return NORM[s]
    # Catch any remaining Türkiye encoding variants
    if s.startswith("T") and "rkiye" in s:
        return "Turkey"
    return s


# Brand order matches consolidate_idd.py
BRAND_ORDER = ["Yes", "Hotlink", "Maxis", "Tune Talk", "redONE", "U Mobile", "CelcomDigi", "Unifi"]


def main():
    path = BASE / "data" / "idd.csv"
    df = pd.read_csv(path)
    original_count = len(df)
    original_countries = df["country"].nunique()

    # Apply normalization
    df["country"] = df["country"].apply(normalize_country)

    normalized_countries = df["country"].nunique()
    changed = original_countries - normalized_countries
    print(f"Country names: {original_countries} → {normalized_countries} unique ({changed} collapsed)")

    # Deduplicate (brand, country, plan_type):
    # Sort so the row with fewest nulls comes first within each group, then drop dupes.
    key_cols = ["brand", "country", "plan_type"]
    dupes_before = df.duplicated(subset=key_cols).sum()

    df["_brand_order"] = df["brand"].map({b: i for i, b in enumerate(BRAND_ORDER)})
    df["_nulls"] = df.isna().sum(axis=1)
    df = df.sort_values(["_brand_order", "country", "plan_type", "_nulls"])
    df = df.drop_duplicates(subset=key_cols, keep="first")
    df = df.drop(columns=["_brand_order", "_nulls"])

    # Final sort: brand in original order, then country A→Z, prepaid before postpaid
    df["_brand_order"] = df["brand"].map({b: i for i, b in enumerate(BRAND_ORDER)})
    df = df.sort_values(["_brand_order", "country", "plan_type"])
    df = df.drop(columns=["_brand_order"])
    df = df.reset_index(drop=True)
    df["record_id"] = range(1, len(df) + 1)

    print(f"Rows: {original_count} → {len(df)} (removed {original_count - len(df)} duplicate rows)")
    print(f"Duplicate (brand,country,plan_type) removed: {dupes_before}")

    df.to_csv(path, index=False)
    print(f"Saved {path.name}")

    print()
    print("Final unique countries:", df["country"].nunique())
    final_countries = sorted(df["country"].unique())
    for c in final_countries:
        print(f"  {c}")

    print()
    print("Rows by brand (in order):")
    for brand in BRAND_ORDER:
        grp = df[df["brand"] == brand]
        print(f"  {brand:15s}: {len(grp)} rows ({grp['country'].nunique()} countries)")


if __name__ == "__main__":
    main()
