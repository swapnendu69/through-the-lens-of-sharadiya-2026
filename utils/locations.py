import json
from pathlib import Path

import streamlit as st

OTHER_COUNTRY = "Other country"
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "locations.json"


@st.cache_data
def load_locations():
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def get_countries():
    return list(load_locations().keys()) + [OTHER_COUNTRY]


def get_divisions(country):
    return list(load_locations().get(country, {}).keys())


def get_districts(country, division):
    return list(load_locations().get(country, {}).get(division, {}).keys())


def get_upazilas(country, division, district):
    return load_locations().get(country, {}).get(division, {}).get(district, [])
