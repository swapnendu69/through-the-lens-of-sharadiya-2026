import hmac
import time
from datetime import timedelta, timezone

import streamlit as st

from utils import storage
from utils.images import b64_to_bytes

st.set_page_config(
    page_title="Admin | Through the Lens of Sharadiya 2026",
    page_icon="🔒",
    layout="wide",
)

MAX_ATTEMPTS = 5
LOCK_SECONDS = 300
LIMIT = 30
COLS = 4
BST = timezone(timedelta(hours=6))  # Bangladesh time


# ---------- Login ----------
def check_login():
    if st.session_state.get("is_admin"):
        return True

    st.title("Admin login")

    now = time.time()
    locked_until = st.session_state.get("locked_until", 0)
    if now < locked_until:
        mins = int((locked_until - now) // 60) + 1
        st.error(f"Too many attempts. Please try again in about {mins} minute(s).")
        return False

    expected = st.secrets.get("admin_password", "")
    if not expected:
        st.error("Admin password is not configured.")
        return False

    with st.form("login"):
        pw = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")

    if submitted:
        if hmac.compare_digest(pw.encode("utf-8"), expected.encode("utf-8")):
            st.session_state["is_admin"] = True
            st.session_state["attempts"] = 0
            st.rerun()
        else:
            attempts = st.session_state.get("attempts", 0) + 1
            st.session_state["attempts"] = attempts
            time.sleep(1)
            if attempts >= MAX_ATTEMPTS:
                st.session_state["locked_until"] = time.time() + LOCK_SECONDS
                st.session_state["attempts"] = 0
            st.error("Incorrect password.")
    return False


if not check_login():
    st.stop()


# ---------- Header ----------
head = st.columns([6, 1])
head[0].title("Admin panel")
if head[1].button("Log out"):
    st.session_state["is_admin"] = False
    st.rerun()

VIEWS = ["Pending", "Reported", "Approved", "Rejected"]
view = st.radio("View", VIEWS, horizontal=True)

# (button label, new status) for each view; Delete is added to all
ACTIONS = {
    "Pending": [("Approve", storage.APPROVED), ("Reject", storage.REJECTED)],
    "Reported": [("Keep", storage.APPROVED), ("Reject", storage.REJECTED)],
    "Approved": [("Reject", storage.REJECTED)],
    "Rejected": [("Restore", storage.APPROVED)],
}


# ---------- Load ----------
def load(view_name):
    if view_name == "Pending":
        return storage.list_by_status(storage.PENDING, LIMIT)
    if view_name == "Approved":
        return storage.list_by_status(storage.APPROVED, LIMIT)
    if view_name == "Rejected":
        return storage.list_by_status(storage.REJECTED, LIMIT)
    return storage.list_reported(LIMIT)


try:
    photos = load(view)
except Exception as e:
    st.error(
        "Could not load photos. If this says the query requires an index, "
        "open the link in the message below and click 'Create index'."
    )
    st.code(str(e))
    st.stop()

st.caption(f"Showing up to {LIMIT} photos, newest first." if view != "Reported"
           else f"Showing up to {LIMIT} photos, most reported first.")

# ---------- Bulk approve ----------
if view == "Pending" and photos:
    reviewed = st.checkbox(f"I have reviewed all {len(photos)} photos shown below")
    if st.button(f"Approve all {len(photos)} shown", disabled=not reviewed):
        for p in photos:
            storage.set_status(p["id"], storage.APPROVED)
        st.rerun()


# ---------- Card ----------
def render_card(p):
    pid = p["id"]
    with st.container(border=True):
        st.image(b64_to_bytes(p["thumb_b64"]), width="stretch")

        st.text(p.get("place_name", ""))
        loc = " > ".join(
            x for x in [p.get("upazila"), p.get("district"),
                        p.get("division"), p.get("country")] if x
        )
        st.text(loc)
        st.text(f"By: {p.get('uploader_name', 'Anonymous')}")
        created = p.get("created_at")
        if created:
            st.text(created.astimezone(BST).strftime("%d %b %Y, %H:%M"))
        if p.get("caption"):
            st.text(p["caption"])
        if p.get("report_count"):
            st.warning(f"Reported {p['report_count']} time(s)")

        if st.checkbox("Show larger image", key=f"big_{pid}"):
            full = storage.get_full_b64(pid)
            if full:
                st.image(b64_to_bytes(full), width="stretch")
            else:
                st.warning("Full image not found.")

        confirm_key = f"confirm_{pid}"
        if st.session_state.get(confirm_key):
            st.error("Delete permanently?")
            c1, c2 = st.columns(2)
            if c1.button("Yes, delete", key=f"yes_{pid}", type="primary"):
                storage.delete_photo(pid)
                st.session_state.pop(confirm_key, None)
                st.rerun()
            if c2.button("Cancel", key=f"no_{pid}"):
                st.session_state.pop(confirm_key, None)
                st.rerun()
        else:
            actions = ACTIONS[view]
            cols = st.columns(len(actions) + 1)
            for col, (label, new_status) in zip(cols, actions):
                if col.button(label, key=f"{label}_{pid}"):
                    storage.set_status(pid, new_status)
                    st.rerun()
            if cols[-1].button("Delete", key=f"del_{pid}"):
                st.session_state[confirm_key] = True
                st.rerun()


# ---------- Grid ----------
if not photos:
    st.info("Nothing here right now.")
else:
    for i in range(0, len(photos), COLS):
        row = st.columns(COLS)
        for col, p in zip(row, photos[i:i + COLS]):
            with col:
                render_card(p)