import logging
import re
from datetime import timedelta, timezone

import streamlit as st

from utils import storage
from utils.images import b64_to_bytes
from utils.locations import get_districts, get_divisions, get_upazilas, load_locations
from utils.theme import apply_theme, banner

st.set_page_config(
    page_title="Through the Lens of Sharadiya 2026",
    page_icon="🪔",
    layout="wide",
)
apply_theme()

PAGE_SIZE = 24
SEARCH_LIMIT = 150
COLS = 4
BST = timezone(timedelta(hours=6))  # Bangladesh time


def esc(text):
    """Escape markdown so visitor-written text is shown as plain text."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|>~<&$:])", r"\\\1", str(text or ""))


def short_location(p):
    parts = [p.get("upazila"), p.get("district") or p.get("division"), p.get("country")]
    return ", ".join(x for x in parts if x)


def full_location(p):
    parts = [p.get("upazila"), p.get("district"), p.get("division"), p.get("country")]
    return " › ".join(x for x in parts if x)


# ---------- Sidebar filters ----------
def clear_filters():
    for k in [k for k in st.session_state if k.startswith("f_")]:
        del st.session_state[k]


st.sidebar.header("Find photos")
country = st.sidebar.selectbox(
    "Country", list(load_locations().keys()),
    index=None, placeholder="All countries", key="f_country",
)
division = district = upazila = None
if country:
    division = st.sidebar.selectbox(
        "Division", get_divisions(country),
        index=None, placeholder="All divisions", key=f"f_div_{country}",
    )
if division:
    district = st.sidebar.selectbox(
        "District", get_districts(country, division),
        index=None, placeholder="All districts", key=f"f_dist_{country}_{division}",
    )
if district:
    upazila = st.sidebar.selectbox(
        "Upazila", get_upazilas(country, division, district),
        index=None, placeholder="All upazilas",
        key=f"f_upa_{country}_{division}_{district}",
    )

query = st.sidebar.text_input(
    "Search by place name", max_chars=80,
    placeholder="e.g. pandal or locality", key="f_query",
).strip().lower()
st.sidebar.button("Clear filters", on_click=clear_filters)

if upazila:
    level, path = "loc_upazila", f"{country}|{division}|{district}|{upazila}"
elif district:
    level, path = "loc_district", f"{country}|{division}|{district}"
elif division:
    level, path = "loc_division", f"{country}|{division}"
elif country:
    level, path = "loc_country", country
else:
    level, path = None, None

# ---------- Gallery state ----------
sig = (level, path, query)
if st.session_state.get("gallery_sig") != sig:
    st.session_state.update(
        gallery_sig=sig, gallery=[], cursor=None, exhausted=False, truncated=False
    )


def matches(p, q):
    hay = " ".join(
        str(p.get(k, "")) for k in ("place_name", "upazila", "district", "division", "country")
    ).lower()
    return all(word in hay for word in q.split())


def load_more():
    ss = st.session_state
    if query:  # search mode: one bigger fetch, filtered here
        batch = storage.list_approved(level, path, None, SEARCH_LIMIT)
        ss.gallery = [p for p in batch if matches(p, query)]
        ss.truncated = len(batch) >= SEARCH_LIMIT
        ss.exhausted = True
    else:
        batch = storage.list_approved(level, path, ss.cursor, PAGE_SIZE)
        ss.gallery = ss.gallery + batch
        if batch:
            ss.cursor = batch[-1]["created_at"]
        ss.exhausted = len(batch) < PAGE_SIZE


# ---------- Photo dialog ----------
@st.dialog("Photo", width="large")
def show_photo(p):
    full = storage.get_full_b64(p["id"])
    st.image(b64_to_bytes(full or p["thumb_b64"]), width="stretch")
    st.markdown(f"### {esc(p.get('place_name'))}")
    st.markdown(esc(full_location(p)))
    st.caption(f"Shared by {esc(p.get('uploader_name') or 'Anonymous')}")
    if p.get("caption"):
        st.markdown(esc(p["caption"]))
    created = p.get("created_at")
    if created:
        st.caption(created.astimezone(BST).strftime("Uploaded %d %b %Y"))

    reported = st.session_state.setdefault("reported_ids", set())
    if p["id"] in reported:
        st.caption("Thank you. This photo has been reported for review.")
    elif st.button("Report this photo", key=f"report_{p['id']}"):
        try:
            storage.report_photo(p["id"])
            reported.add(p["id"])
            st.success("Thank you. We will review this photo.")
        except Exception:
            logging.exception("Report failed")
            st.error("Sorry, the report could not be sent. Please try again later.")


def render_card(p):
    with st.container(border=True):
        st.image(b64_to_bytes(p["thumb_b64"]), width="stretch")
        st.markdown(f"**{esc(p.get('place_name'))}**")
        st.caption(esc(short_location(p)))
        if st.button("View", key=f"view_{p['id']}", width="stretch"):
            show_photo(p)


# ---------- Page ----------
banner(
    "Through the Lens of Sharadiya 2026",
    "Durga Puja moments, shared by everyone. Use the panel on the left to find photos by place.",
)
st.page_link("pages/1_Upload.py", label="Upload your photos", icon="📸")

if not st.session_state.gallery and not st.session_state.exhausted:
    try:
        load_more()
    except Exception:
        logging.exception("Gallery load failed")
        st.error("The gallery is temporarily unavailable. Please try again in a little while.")
        st.stop()

photos = st.session_state.gallery

if not photos:
    if query or level:
        st.info("No photos found for these filters yet. Try clearing some filters.")
    else:
        st.info("No photos yet. Be the first to share one!")
else:
    for i in range(0, len(photos), COLS):
        row = st.columns(COLS)
        for col, p in zip(row, photos[i:i + COLS]):
            with col:
                render_card(p)

    if query and st.session_state.truncated:
        st.caption(
            f"Searched the newest {SEARCH_LIMIT} photos in this area. "
            "Choose a district or upazila to narrow it down."
        )

    if not st.session_state.exhausted:
        if st.button("Load more photos", type="primary"):
            try:
                load_more()
                st.rerun()
            except Exception:
                logging.exception("Load more failed")
                st.error("Could not load more photos right now.")

st.divider()
st.caption("Photos are shared by visitors. See something wrong? Open the photo and tap Report.")