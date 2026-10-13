import logging
import time
import uuid

import streamlit as st

from utils import storage
from utils.images import ImageError, process_image
from utils.locations import (
    OTHER_COUNTRY,
    get_countries,
    get_districts,
    get_divisions,
    get_upazilas,
)

st.set_page_config(
    page_title="Upload | Through the Lens of Sharadiya 2026",
    page_icon="🪔",
    layout="centered",
)

MAX_FILES = 10
RATE_LIMIT = 20      # photos per session per window
RATE_WINDOW = 3600   # seconds

n = st.session_state.setdefault("form_n", 0)

flash = st.session_state.pop("flash", None)
if flash:
    st.success(flash)

st.title("Upload your Puja photos")
st.caption(
    "Up to 10 photos at a time · JPG, PNG or WebP · max 5 MB each · "
    "no account needed. Photos appear on the site after a quick review."
)

# ---------- Photos ----------
files = st.file_uploader(
    "Photos",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
    key=f"files_{n}",
)
if files and len(files) > MAX_FILES:
    st.error(f"You selected {len(files)} photos. Please keep it to {MAX_FILES} or fewer.")

name = st.text_input("Your name (optional)", max_chars=60, key=f"name_{n}")

# ---------- Location (outside any st.form so dropdowns update live) ----------
st.subheader("Where were these photos taken?")

country_choice = st.selectbox(
    "Country",
    get_countries(),
    index=None,
    placeholder="Select a country",
    key=f"country_{n}",
)

country = division = district = upazila = ""
needs_upazila = False

if country_choice == OTHER_COUNTRY:
    country = st.text_input("Country name", max_chars=80, key=f"ocountry_{n}").strip()
    division = st.text_input("State / region (optional)", max_chars=80, key=f"odiv_{n}").strip()
    district = st.text_input("District / city (optional)", max_chars=80, key=f"odist_{n}").strip()
    upazila = st.text_input("Sub-district / area (optional)", max_chars=80, key=f"oupa_{n}").strip()

elif country_choice:
    country = country_choice
    division = st.selectbox(
        "Division",
        get_divisions(country),
        index=None,
        placeholder="Select a division",
        key=f"div_{n}_{country}",
    ) or ""

    if division:
        district = st.selectbox(
            "District",
            get_districts(country, division),
            index=None,
            placeholder="Select a district",
            key=f"dist_{n}_{country}_{division}",
        ) or ""

    if district:
        upazila_options = get_upazilas(country, division, district)
        needs_upazila = bool(upazila_options)
        if needs_upazila:
            upazila = st.selectbox(
                "Upazila",
                upazila_options,
                index=None,
                placeholder="Select an upazila",
                key=f"upa_{n}_{country}_{division}_{district}",
            ) or ""

place = st.text_input(
    "Place name (e.g. pandal or locality name)",
    max_chars=120,
    key=f"place_{n}",
)
caption = st.text_area(
    "Caption (optional, applies to all photos in this upload)",
    max_chars=300,
    height=80,
    key=f"caption_{n}",
)
consent = st.checkbox(
    "I own these photos and agree to share them publicly.",
    key=f"consent_{n}",
)

# ---------- Submit ----------
if st.button("Upload", type="primary"):
    now = time.time()
    recent = [t for t in st.session_state.get("upload_times", []) if now - t < RATE_WINDOW]
    st.session_state["upload_times"] = recent

    errors = []
    if not files:
        errors.append("Please choose at least one photo.")
    elif len(files) > MAX_FILES:
        errors.append(f"Please select no more than {MAX_FILES} photos.")
    elif len(recent) + len(files) > RATE_LIMIT:
        errors.append("You have uploaded a lot of photos recently. Please try again later.")

    if not country:
        errors.append("Please select a country.")
    elif country_choice != OTHER_COUNTRY:
        if not division:
            errors.append("Please select a division.")
        elif not district:
            errors.append("Please select a district.")
        elif needs_upazila and not upazila:
            errors.append("Please select an upazila.")

    if not place.strip():
        errors.append("Please enter the place name.")
    if not consent:
        errors.append("Please confirm that you own these photos.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        meta = {
            "uploader_name": name,
            "country": country,
            "division": division,
            "district": district,
            "upazila": upazila,
            "place_name": place,
            "caption": caption,
            "batch_id": str(uuid.uuid4()),
        }
        ok = dup = 0
        failed = []
        progress = st.progress(0.0, text="Uploading...")

        for i, f in enumerate(files, 1):
            try:
                processed = process_image(f.getvalue())
                result = storage.add_photo(processed, meta)
                if result == "ok":
                    ok += 1
                else:
                    dup += 1
            except ImageError as e:
                failed.append(f"{f.name}: {e}")
            except Exception:
                logging.exception("Upload failed")
                failed.append("A server problem occurred. Please try again later.")
                break
            progress.progress(i / len(files), text=f"Uploading {i} of {len(files)}...")

        progress.empty()

        if ok:
            st.session_state["upload_times"] = recent + [now] * ok

        if ok and not failed:
            msg = f"Thank you! {ok} photo(s) uploaded. They will appear after review."
            if dup:
                msg += f" {dup} photo(s) had already been uploaded and were skipped."
            st.session_state["flash"] = msg
            st.session_state["form_n"] = n + 1
            st.rerun()
        else:
            if ok:
                st.success(f"{ok} photo(s) uploaded and waiting for review.")
            if dup:
                st.info(f"{dup} photo(s) had already been uploaded and were skipped.")
            for msg in failed:
                st.error(msg)