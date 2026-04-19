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
import plotly.express as px
import streamlit as st
from google.oauth2.service_account import Credentials

# --------------------------------------------------------------------------- #
# CONFIG                                                                      #
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="CN88 Men of Excellence",
    page_icon="🎓",
    layout="wide",
)

st.markdown(
    """
    <meta property="og:title" content="CN88 Men of Excellence" />
    <meta property="og:description" content="Christ Nagar School, Batch of 1988 — Batch Directory" />
    <meta property="og:type" content="website" />
    <meta name="twitter:title" content="CN88 Men of Excellence" />
    <meta name="twitter:description" content="Christ Nagar School, Batch of 1988 — Batch Directory" />
    """,
    unsafe_allow_html=True,
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

EC_MEMBERS = [
    "Akilan Karthikeyan", "Francis Sujith",
    "Abhayakumar NS", "Ajay Antony", "Anand Victor", "Arun Divakar",
    "Joseph John", "Litty", "Satish Karunkaran", "Shivan G. Nair",
    "Sreekanth Iyer", "Adv. Jayakrishnan", "Rajesh Sukumaran Nair", "Vinu Thomas Kuzhuveli", "Abdul Kader",
    "Adv. Praveen", "Ajith Ram", "Benoy A Pazhoor", "Binu Baby Vaidian", "Jacob Joseph",
    "Mahesh R", "Sam Kurien", "Sanju Joy", "Shyam Viju", "Symon Thelappillil"
]

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
    st.image("https://raw.githubusercontent.com/sreek-iyer/cn88-batch-directory/main/images/cover.jpeg", use_container_width=True)

    st.markdown("<div style='padding: 30px 20px; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);'><h1 style='margin: 0; color: #fff; font-size: 2.5em;'>🎓 CN88</h1><p style='margin: 10px 0 0 0; color: #f0f0f0; font-size: 0.95em; letter-spacing: 1px;'>Batch Directory</p></div>", unsafe_allow_html=True)

    st.markdown("<div style='padding: 25px 20px; background: #f8f9fa; text-align: center;'><p style='margin: 0 0 8px 0; font-size: 1.2em; font-weight: 600; color: #1a1a1a;'>Christ Nagar 1988</p><p style='margin: 0; font-size: 0.95em; color: #d4af37; font-weight: 500;'>Men of Excellence 😊</p><p style='margin: 15px 0 0 0; color: #666; font-size: 0.9em; line-height: 1.5;'>Connect with your batchmates. Share experiences. Build lifelong bonds.</p></div>", unsafe_allow_html=True)

    st.markdown("")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.button("Sign in with Google", type="primary", on_click=st.login, use_container_width=True)

    if FORM_URL:
        st.markdown("")
        st.markdown(f"""
        <a href="{FORM_URL}" target="_blank" style="
            display: block;
            padding: 14px 20px;
            margin: 0 auto;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: center;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
            font-size: 1em;
            transition: transform 0.2s, box-shadow 0.2s;
            box-shadow: 0 4px 6px rgba(102, 126, 234, 0.4);
            width: 80%;
            margin-left: auto;
            margin-right: auto;
        ">📝 Join the Community</a>
        """, unsafe_allow_html=True)

    st.markdown("")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #1877f2 0%, #0a66c2 100%); color: white; text-align: center; border-radius: 8px; padding: 18px 16px; min-height: 80px; box-sizing: border-box; box-shadow: 0 4px 6px rgba(24, 119, 242, 0.3);">
            <div style="font-size: 0.9em; font-weight: 500; margin-bottom: 6px;">Connect with batchmates</div>
            <a href="https://www.facebook.com/groups/596744407056517" target="_blank" style="color: white; text-decoration: none; font-weight: 700; font-size: 1em;">📘 Join Facebook Group</a>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%); color: white; text-align: center; border-radius: 8px; padding: 18px 16px; min-height: 80px; box-sizing: border-box; box-shadow: 0 4px 6px rgba(255, 107, 107, 0.3);">
            <div style="font-size: 0.9em; font-weight: 500; margin-bottom: 6px;">For details or to contribute</div>
            <a href="mailto:cn88moe@gmail.com" style="color: white; text-decoration: none; font-weight: 700; font-size: 1em;">📧 cn88moe@gmail.com</a>
        </div>
        """, unsafe_allow_html=True)



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


def insights_view(df: pd.DataFrame) -> None:
    country_col = COLS["country"]
    city_col = COLS["city"]
    industry_col = COLS["industry"]

    df_clean = df.copy()
    if country_col in df_clean.columns:
        df_clean[country_col] = df_clean[country_col].astype(str).str.strip()
        df_clean = df_clean[df_clean[country_col] != ""]
    if city_col in df_clean.columns:
        df_clean[city_col] = df_clean[city_col].astype(str).str.strip()

    total = len(df)
    n_countries = df_clean[country_col].nunique() if country_col in df_clean.columns else 0
    n_cities = df_clean[city_col].nunique() if city_col in df_clean.columns else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Members", total)
    c2.metric("Countries", n_countries)
    c3.metric("Cities", n_cities)

    if country_col in df_clean.columns and len(df_clean) > 0:
        st.markdown("### 🌍 Members by Country")
        country_counts = (
            df_clean[country_col].value_counts().reset_index()
        )
        country_counts.columns = ["Country", "Members"]

        fig_map = px.choropleth(
            country_counts,
            locations="Country",
            locationmode="country names",
            color="Members",
            hover_name="Country",
            color_continuous_scale="Blues",
        )
        fig_map.update_layout(
            margin=dict(l=0, r=0, t=10, b=0),
            geo=dict(showframe=False, showcoastlines=True, projection_type="natural earth"),
            height=420,
        )
        st.plotly_chart(fig_map, use_container_width=True)

        fig_bar = px.bar(
            country_counts,
            x="Country",
            y="Members",
            color="Members",
            color_continuous_scale="Blues",
            text="Members",
        )
        fig_bar.update_traces(textposition="outside")
        fig_bar.update_layout(margin=dict(l=0, r=0, t=10, b=0), showlegend=False, height=350)
        st.plotly_chart(fig_bar, use_container_width=True)

    if city_col in df_clean.columns and len(df_clean) > 0:
        st.markdown("### 🏙️ Top Cities")
        city_counts = (
            df_clean[df_clean[city_col] != ""][city_col]
            .value_counts()
            .head(15)
            .reset_index()
        )
        city_counts.columns = ["City", "Members"]
        if len(city_counts) > 0:
            fig_city = px.bar(
                city_counts,
                x="Members",
                y="City",
                orientation="h",
                color="Members",
                color_continuous_scale="Purples",
                text="Members",
            )
            fig_city.update_traces(textposition="outside")
            fig_city.update_layout(
                margin=dict(l=0, r=0, t=10, b=0),
                showlegend=False,
                yaxis=dict(autorange="reversed"),
                height=max(300, 30 * len(city_counts)),
            )
            st.plotly_chart(fig_city, use_container_width=True)

    if industry_col in df_clean.columns:
        ind = df_clean[industry_col].astype(str).str.strip()
        ind = ind[ind != ""]
        if len(ind) > 0:
            st.markdown("### 💼 Industry Mix")
            ind_counts = ind.value_counts().reset_index()
            ind_counts.columns = ["Industry", "Members"]
            fig_ind = px.pie(
                ind_counts,
                names="Industry",
                values="Members",
                hole=0.45,
            )
            fig_ind.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=400)
            st.plotly_chart(fig_ind, use_container_width=True)


def directory_list_view(df: pd.DataFrame) -> None:
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
        st.caption(f"{len(df)} batchmates in directory")
        st.divider()
        st.markdown("### 🎯 Executive Committee")
        ec_text = "<br>".join(EC_MEMBERS)
        with st.container(border=True):
            st.markdown(ec_text, unsafe_allow_html=True)

    st.title("🎓 CN88 — Batch Directory")
    st.caption("Christ Nagar School, Batch of 1988")

    tab_dir, tab_insights = st.tabs(["📇 Directory", "📊 Insights & Map"])
    with tab_dir:
        directory_list_view(df)
    with tab_insights:
        insights_view(df)


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
