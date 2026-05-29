"""Known Indian district population data for validation and fallback.

Data sources: Census of India 2001, 2011; projections via state-level growth rates.
Population values are approximate.
"""

from __future__ import annotations

# Key: "state_lower|district_lower"
# Value: dict of {year: population}
INDIA_DISTRICT_POPULATION: dict[str, dict[int, float]] = {
    "uttar pradesh|ayodhya": {
        2001: 2_071_985,
        2011: 2_470_996,
        2021: 2_780_000,
    },
    "jammu and kashmir|srinagar": {
        2001: 898_440,
        2011: 1_269_751,
        2021: 1_450_000,
    },
    "ladakh|leh": {
        2001: 117_232,
        2011: 133_487,
        2021: 155_000,
    },
    "himachal pradesh|kullu": {  # Manali is in Kullu district
        2001: 381_571,
        2011: 437_903,
        2021: 495_000,
    },
    "maharashtra|pune": {
        2001: 7_232_555,
        2011: 9_426_959,
        2021: 11_500_000,
    },
    "karnataka|bangalore urban": {
        2001: 6_537_124,
        2011: 9_621_551,
        2021: 13_000_000,
    },
    "tamil nadu|chennai": {
        2001: 6_560_242,
        2011: 7_088_000,
        2021: 7_600_000,
    },
    "west bengal|kolkata": {
        2001: 4_572_876,
        2011: 4_496_694,
        2021: 4_700_000,
    },
    "gujarat|ahmedabad": {
        2001: 5_171_608,
        2011: 7_214_225,
        2021: 9_000_000,
    },
    "rajasthan|jaipur": {
        2001: 5_251_071,
        2011: 6_626_178,
        2021: 8_000_000,
    },
    "uttar pradesh|lucknow": {
        2001: 3_647_834,
        2011: 4_588_455,
        2021: 5_600_000,
    },
    "uttarakhand|haridwar": {
        2001: 1_447_187,
        2011: 1_890_422,
        2021: 2_200_000,
    },
}

# Known GDP data for cross-validation (nominal INR crores, approximate)
INDIA_DISTRICT_GDP: dict[str, dict[int, float]] = {
    "maharashtra|pune": {
        2015: 174_000,
        2018: 225_000,
        2020: 210_000,
        2022: 260_000,
    },
    "karnataka|bangalore urban": {
        2015: 390_000,
        2018: 520_000,
        2020: 490_000,
        2022: 610_000,
    },
}
