import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.exceptions import AlreadyExists
from google.cloud.firestore_v1.base_query import FieldFilter

PHOTOS = "photos"        # metadata + thumbnail
FULL = "photo_full"      # large image (loaded only when opened)

PENDING, APPROVED, REJECTED = "pending", "approved", "rejected"
DESC = firestore.Query.DESCENDING


@st.cache_resource
def get_db():
    if not firebase_admin._apps:
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)
    return firestore.client()


def _clean(text, max_len):
    return " ".join((text or "").split())[:max_len]


def _to_dict(doc):
    d = doc.to_dict()
    d["id"] = doc.id
    return d


# ---------- Upload ----------

def add_photo(processed, meta):
    """Save one processed image as 'pending'. Returns 'ok' or 'duplicate'."""
    db = get_db()
    photo_id = processed["sha256"][:40]
    photo_ref = db.collection(PHOTOS).document(photo_id)
    full_ref = db.collection(FULL).document(photo_id)

    country = _clean(meta["country"], 80)
    division = _clean(meta.get("division"), 80)
    district = _clean(meta.get("district"), 80)
    upazila = _clean(meta.get("upazila"), 80)

    data = {
        "uploader_name": _clean(meta.get("uploader_name"), 60) or "Anonymous",
        "country": country,
        "division": division,
        "district": district,
        "upazila": upazila,
        "place_name": _clean(meta["place_name"], 120),
        "caption": _clean(meta.get("caption"), 300),
        "loc_country": country,
        "batch_id": meta["batch_id"],
        "status": PENDING,
        "report_count": 0,
        "created_at": firestore.SERVER_TIMESTAMP,
        "thumb_b64": processed["thumb_b64"],
    }
    if division:
        data["loc_division"] = f"{country}|{division}"
    if division and district:
        data["loc_district"] = f"{country}|{division}|{district}"
    if division and district and upazila:
        data["loc_upazila"] = f"{country}|{division}|{district}|{upazila}"

    try:
        photo_ref.create(data)
    except AlreadyExists:
        return "duplicate"

    try:
        full_ref.set({"full_b64": processed["full_b64"]})
    except Exception:
        photo_ref.delete()  # keep data consistent
        raise
    return "ok"


# ---------- Public gallery ----------

@st.cache_data(ttl=120, show_spinner=False)
def list_approved(level=None, path=None, after=None, limit=24):
    """Approved photos, newest first.

    level: 'loc_country' | 'loc_division' | 'loc_district' | 'loc_upazila' | None
    path:  matching path string, e.g. 'Bangladesh|Khulna|Jashore'
    after: created_at of the last photo already shown (for 'Load more')
    """
    q = get_db().collection(PHOTOS).where(
        filter=FieldFilter("status", "==", APPROVED)
    )
    if level and path:
        q = q.where(filter=FieldFilter(level, "==", path))
    q = q.order_by("created_at", direction=DESC)
    if after is not None:
        q = q.start_after({"created_at": after})
    return [_to_dict(d) for d in q.limit(limit).stream()]


@st.cache_data(ttl=600, max_entries=50, show_spinner=False)
def get_full_b64(photo_id):
    snap = get_db().collection(FULL).document(photo_id).get()
    return snap.to_dict().get("full_b64") if snap.exists else None


def report_photo(photo_id):
    get_db().collection(PHOTOS).document(photo_id).update(
        {"report_count": firestore.Increment(1)}
    )


# ---------- Admin ----------

def list_by_status(status, limit=50):
    q = (
        get_db().collection(PHOTOS)
        .where(filter=FieldFilter("status", "==", status))
        .order_by("created_at", direction=DESC)
        .limit(limit)
    )
    return [_to_dict(d) for d in q.stream()]


def list_reported(limit=50):
    q = (
        get_db().collection(PHOTOS)
        .where(filter=FieldFilter("report_count", ">", 0))
        .order_by("report_count", direction=DESC)
        .limit(limit)
    )
    return [_to_dict(d) for d in q.stream()]


def set_status(photo_id, status):
    get_db().collection(PHOTOS).document(photo_id).update(
        {"status": status, "report_count": 0}
    )
    st.cache_data.clear()


def delete_photo(photo_id):
    db = get_db()
    db.collection(FULL).document(photo_id).delete()
    db.collection(PHOTOS).document(photo_id).delete()
    st.cache_data.clear()
