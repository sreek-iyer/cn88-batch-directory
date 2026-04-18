"""
CN88 — Official Batch Directory (Krishnagar 1988)
-------------------------------------------------
Auth model:
  1. Authentication: Streamlit native OIDC via st.login() → Google Identity.
  2. Authorization : email (from Google token) must exist in the directory sheet.
                     If not → polite "not yet in directory" screen with form link.

Source of truth: Google Sheet backed by a Google Form.
Deployment    : Streamlit Community Cloud (free tier).
"""
from __future__ import annotations

import re

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

# --------------------------------------------------------------------------- #
# CONFIG                                                                      #
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="CN88 Batch Directory",
    page_icon="🎓",
    layout="wide",
)

SHEET_URL = st.secrets["gsheet"]["sheet_url"]
WORKSHEET_NAME = st.secrets["gsheet"].get("worksheet_name", "Form responses 1")
FORM_URL = st.secrets.get("form", {}).get("url", "")
CACHE_TTL_SECONDS = 300  # 5 min

# Map the sheet's actual header row → logical keys used in the UI.
# Headers captured from the live sheet on 18-Apr-2026.
# NOTE on M/N/O: in the current sheet, family info is in column M,
# networking preferences are in N (the header label on N is misleading),
# and O is blank. The app handles this by preferring a "Networking and
# Contribution" column if present, and falling back to the mislabeled one.
COLS = {
    "first_name":  "First Name",
    "last_name":   "Last Name",
    "photo":       "Photo",
    "email":       "Primary Email ID",
    "mobile":      "Mobile",
    "city":        "Current City of Residence",
    "state":       "State",
    "country":     "Country",
    "profession":  "Work / Profession",
    "company":     "Company",
    "industry":    "Industry Sector",
    "family":      "Family & Life Highlights Legacy / Single/Married, Spouse: [Name]",
    "networking_primary":   "Networking and Contribution",
    "networking_fallback":  "Children: [Name/Age/Current Study or Job]. This helps us facilitate internship matching and organize family-inclusive batch meets.",
}

# --------------------------------------------------------------------------- #
# DATA LAYER                                                                  #
# --------------------------------------------------------------------------- #
@st.cache_resource
def _gspread_client() -> gspread.Client:
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    )
    return gspread.authorize(creds)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Loading directory…")
def load_directory() -> pd.DataFrame:
    client = _gspread_client()
    ws = client.open_by_url(SHEET_URL).worksheet(WORKSHEET_NAME)
    df = pd.DataFrame(ws.get_all_records())
    if COLS["first_name"] in df.columns:
        df = df[df[COLS["first_name"]].astype(str).str.strip() != ""].reset_index(drop=True)
    if COLS["email"] in df.columns:
        df[COLS["email"]] = df[COLS["email"]].astype(str).str.strip().str.lower()
    return df


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def allowed_emails() -> set[str]:
    df = load_directory()
    if COLS["email"] not in df.columns:
        return set()
    return {e for e in df[COLS["email"]].dropna() if e}


# --------------------------------------------------------------------------- #
# DRIVE PHOTO HELPERS                                                         #
# --------------------------------------------------------------------------- #
_DRIVE_ID_PATTERNS = [
    r"/file/d/([a-zA-Z0-9_-]+)",
    r"[?&]id=([a-zA-Z0-9_-]+)",
    r"/d/([a-zA-Z0-9_-]+)",
]


def extract_drive_id(url: str) -> str | None:
    if not url or not isinstance(url, str):
        return None
    for pattern in _DRIVE_ID_PATTERNS:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


def drive_thumbnail(url: str, size: int = 400) -> str | None:
    """Convert a Drive share URL to an embeddable thumbnail URL.
    Requires the file to be shared 'Anyone with the link — Viewer'.
    """
    fid = extract_drive_id(url)
    return f"https://drive.google.com/thumbnail?id={fid}&sz=w{size}" if fid else None


# --------------------------------------------------------------------------- #
# AUTH VIEWS                                                                  #
# --------------------------------------------------------------------------- #
def login_view() -> None:
    st.title("🎓 CN88 — Batch Directory")
    st.caption("Christ Nagar School, Batch of 1988")
    st.markdown(
        "Members-only. Please sign in with the Google account whose email you "
        "used on the batch form."
    )
    st.button("Sign in with Google", type="primary", on_click=st.login)
    if FORM_URL:
        st.divider()
        st.markdown("**Haven't filled the form yet?**")
        st.link_button("Open the CN88 form ↗", FORM_URL)


def not_in_directory_view(email: str) -> None:
    st.title("🎓 CN88 — Batch Directory")
    st.warning(
        f"**{email}** isn't in the directory yet.\n\n"
        "If this is the Google account you used on the form, give it a few "
        "minutes (directory refreshes every 5 min) and try again. Otherwise, "
        "please fill the form first with this email — you'll be able to sign "
        "in right after."
    )
    c1, c2 = st.columns(2)
    with c1:
        if FORM_URL:
            st.link_button("Open the CN88 form ↗", FORM_URL, use_container_width=True)
    with c2:
        st.button("Sign out", on_click=st.logout, use_container_width=True)


# --------------------------------------------------------------------------- #
# UI — DIRECTORY                                                              #
# --------------------------------------------------------------------------- #
def _safe(row: pd.Series, key: str) -> str:
    col = COLS.get(key)
    if col and col in row.index:
        val = row[col]
        if pd.isna(val):
            return ""
        return str(val).strip()
    return ""


def _networking(row: pd.Series) -> str:
    primary = _safe(row, "networking_primary")
    return primary if primary else _safe(row, "networking_fallback")


def person_card(row: pd.Series) -> None:
    first = _safe(row, "first_name")
    last = _safe(row, "last_name")
    name = " ".join([x for x in (first, last) if x]) or "—"
    city = _safe(row, "city")
    state = _safe(row, "state")
    country = _safe(row, "country")
    where = ", ".join([x for x in (city, state, country) if x])
    profession = _safe(row, "profession")
    company = _safe(row, "company")
    role = " at ".join([x for x in (profession, company) if x])
    industry = _safe(row, "industry")
    family = _safe(row, "family")
    networking = _networking(row)
    email = _safe(row, "email")
    mobile = _safe(row, "mobile")
    photo = drive_thumbnail(_safe(row, "photo"))

    with st.container(border=True):
        c1, c2 = st.columns([1, 3])
        with c1:
            if photo:
                st.image(photo, use_container_width=True)
            else:
                initial = (name[:1] or "?").upper()
                st.markdown(
                    f"<div style='background:#eef;border-radius:8px;padding:40px 0;"
                    f"text-align:center;font-size:42px;font-weight:600;color:#556;'>"
                    f"{initial}</div>",
                    unsafe_allow_html=True,
                )
        with c2:
            st.markdown(f"### {name}")
            if role:
                st.markdown(f"**{role}**")
            if industry:
                st.caption(industry)
            if where:
                st.caption(f"📍 {where}")
            if family:
                st.write(f"**Family:** {family}")
            if networking:
                with st.expander("Open to"):
                    st.write(networking)
            meta_bits = []
            if email:
                meta_bits.append(f"✉️ {email}")
            if mobile:
                meta_bits.append(f"📱 {mobile}")
            if meta_bits:
                st.caption(" · ".join(meta_bits))


def directory_view() -> None:
    df = load_directory()
    me_email = (st.user.email or "").lower()
    me_name = st.user.name or me_email

    with st.sidebar:
        if getattr(st.user, "picture", None):
            st.image(st.user.picture, width=80)
        st.markdown(f"**{me_name}**\n\n{me_email}")
        st.button("Sign out", on_click=st.logout, use_container_width=True)
        if st.button("🔄 Refresh from sheet", use_container_width=True):
            load_directory.clear()
            allowed_emails.clear()
            st.rerun()
        st.divider()
        st.caption(f"{len(df)} batchmates listed")
        if FORM_URL:
            st.link_button("Edit your entry ↗", FORM_URL, use_container_width=True)

    st.title("🎓 CN88 — Batch Directory")
    st.caption("Christ Nagar School, Batch of 1988")

    query = st.text_input("Search name, city, company, profession…", "").strip()
    country_col = COLS["country"]
    countries = sorted(
        {c for c in df.get(country_col, pd.Series(dtype=str)).dropna() if c}
    ) if country_col in df.columns else []
    country_filter = st.multiselect("Filter by country", countries) if countries else []

    view = df.copy()
    if query:
        ql = query.lower()
        search_cols = [
            COLS[k] for k in ("first_name", "last_name", "city", "company", "profession", "industry")
            if COLS[k] in view.columns
        ]
        mask = pd.Series(False, index=view.index)
        for c in search_cols:
            mask |= view[c].astype(str).str.lower().str.contains(ql, na=False)
        view = view[mask]
    if country_filter and country_col in view.columns:
        view = view[view[country_col].isin(country_filter)]

    if COLS["first_name"] in view.columns:
        view = view.sort_values(
            COLS["first_name"], key=lambda s: s.astype(str).str.lower()
        )

    st.caption(f"Showing {len(view)} of {len(df)}")
    if len(view) == 0:
        st.info("No matches. Try a different search term.")
        return

    rows = view.to_dict("records")
    for i in range(0, len(rows), 2):
        col_a, col_b = st.columns(2)
        with col_a:
            person_card(pd.Series(rows[i]))
        if i + 1 < len(rows):
            with col_b:
                person_card(pd.Series(rows[i + 1]))


# --------------------------------------------------------------------------- #
# MAIN                                                                        #
# --------------------------------------------------------------------------- #
def main() -> None:
    # 1. Not logged in → Google sign-in
    if not st.user.is_logged_in:
        login_view()
        return

    # 2. Logged in → must be on the allowlist (sheet of emails)
    user_email = (st.user.email or "").lower().strip()
    if user_email not in allowed_emails():
        not_in_directory_view(user_email)
        return

    # 3. Authorized → directory
    directory_view()


if __name__ == "__main__":
    main()
