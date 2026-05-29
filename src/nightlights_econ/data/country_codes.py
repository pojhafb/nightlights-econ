"""ISO 3166-1 alpha-3 to alpha-2 country code mappings."""

# Subset covering countries most likely used in this toolkit
ALPHA3_TO_ALPHA2: dict[str, str] = {
    "AFG": "AF", "ALB": "AL", "DZA": "DZ", "AGO": "AO", "ARG": "AR",
    "ARM": "AM", "AUS": "AU", "AUT": "AT", "AZE": "AZ", "BGD": "BD",
    "BLR": "BY", "BEL": "BE", "BEN": "BJ", "BTN": "BT", "BOL": "BO",
    "BRA": "BR", "BGR": "BG", "BFA": "BF", "BDI": "BI", "KHM": "KH",
    "CMR": "CM", "CAN": "CA", "CAF": "CF", "TCD": "TD", "CHL": "CL",
    "CHN": "CN", "COL": "CO", "COD": "CD", "COG": "CG", "CRI": "CR",
    "CIV": "CI", "HRV": "HR", "CUB": "CU", "CYP": "CY", "CZE": "CZ",
    "DNK": "DK", "DOM": "DO", "ECU": "EC", "EGY": "EG", "ETH": "ET",
    "FIN": "FI", "FRA": "FR", "GAB": "GA", "DEU": "DE", "GHA": "GH",
    "GRC": "GR", "GTM": "GT", "GIN": "GN", "HTI": "HT", "HND": "HN",
    "HUN": "HU", "IND": "IN", "IDN": "ID", "IRN": "IR", "IRQ": "IQ",
    "IRL": "IE", "ISR": "IL", "ITA": "IT", "JAM": "JM", "JPN": "JP",
    "JOR": "JO", "KAZ": "KZ", "KEN": "KE", "PRK": "KP", "KOR": "KR",
    "KWT": "KW", "KGZ": "KG", "LAO": "LA", "LVA": "LV", "LBN": "LB",
    "LBR": "LR", "LBY": "LY", "LTU": "LT", "MDG": "MG", "MWI": "MW",
    "MYS": "MY", "MDV": "MV", "MLI": "ML", "MRT": "MR", "MEX": "MX",
    "MDA": "MD", "MNG": "MN", "MAR": "MA", "MOZ": "MZ", "MMR": "MM",
    "NAM": "NA", "NPL": "NP", "NLD": "NL", "NZL": "NZ", "NIC": "NI",
    "NER": "NE", "NGA": "NG", "NOR": "NO", "PAK": "PK", "PAN": "PA",
    "PNG": "PG", "PRY": "PY", "PER": "PE", "PHL": "PH", "POL": "PL",
    "PRT": "PT", "PRI": "PR", "QAT": "QA", "ROU": "RO", "RUS": "RU",
    "RWA": "RW", "SAU": "SA", "SEN": "SN", "SLE": "SL", "SOM": "SO",
    "ZAF": "ZA", "SSD": "SS", "ESP": "ES", "LKA": "LK", "SDN": "SD",
    "SWE": "SE", "CHE": "CH", "SYR": "SY", "TWN": "TW", "TJK": "TJ",
    "TZA": "TZ", "THA": "TH", "TGO": "TG", "TUN": "TN", "TUR": "TR",
    "TKM": "TM", "UGA": "UG", "UKR": "UA", "ARE": "AE", "GBR": "GB",
    "USA": "US", "URY": "UY", "UZB": "UZ", "VEN": "VE", "VNM": "VN",
    "YEM": "YE", "ZMB": "ZM", "ZWE": "ZW",
}

ALPHA2_TO_ALPHA3: dict[str, str] = {v: k for k, v in ALPHA3_TO_ALPHA2.items()}

# Country display names (for charts and reports)
COUNTRY_NAMES: dict[str, str] = {
    "IND": "India", "CHN": "China", "USA": "United States",
    "UKR": "Ukraine", "KEN": "Kenya", "NGA": "Nigeria",
    "BRA": "Brazil", "ZAF": "South Africa", "PAK": "Pakistan",
    "BGD": "Bangladesh", "IDN": "Indonesia",
}
