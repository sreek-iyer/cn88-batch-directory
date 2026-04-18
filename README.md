# CN88 Batch Directory

A members-only web directory for the Christ Nagar School Class of 1988, backed by the existing Google Form + Google Sheet, gated by Google Sign-In, deployed free on Streamlit Community Cloud.

> For implementation setup with Claude Code, see [`CLAUDE_CODE_BRIEF.md`](./CLAUDE_CODE_BRIEF.md).

---

## 1. Architecture at a glance

```
 ┌──────────────┐       auto-append        ┌───────────────────┐
 │ Google Form  │  ───────────────────▶    │   Google Sheet    │  ← source of truth
 └──────────────┘                          └─────────┬─────────┘
                                                     │ read-only, service account
                                                     ▼
 ┌────────────────────────────────────────────────────────────────┐
 │                     Streamlit app (Python)                     │
 │                                                                │
 │   ┌──────────┐   ┌──────────┐   ┌────────────────────┐         │
 │   │  AuthN   │──▶│  AuthZ   │──▶│   Directory UI     │         │
 │   │ Google   │   │ email ∈  │   │ (cards + search)   │         │
 │   │  OIDC    │   │  sheet   │   │                    │         │
 │   └──────────┘   └──────────┘   └────────────────────┘         │
 └────────────────────────────┬───────────────────────────────────┘
                              │ HTTPS
                              ▼
                   ┌──────────────────────┐
                   │ Streamlit Community  │
                   │  Cloud (free tier)   │
                   └──────────────────────┘
```

### Why these choices

| Concern | Decision | Why |
|---|---|---|
| Source of truth | Google Sheet (unchanged) | Form flow works; zero migration |
| Data access | Service account, read-only | Sheet stays private; no "publish to web" |
| Hosting | Streamlit Community Cloud | Free, Python-native, GitHub-linked |
| AuthN | `st.login()` native OIDC (Streamlit ≥ 1.42) | No passwords to manage; everyone has a Google account already |
| AuthZ | Email allowlist from the sheet | Add/remove = sheet CRUD, no admin UI needed |
| Photos | Drive thumbnail URL transform | Only server-free way to render Drive images inline |
| Freshness | 5-min cache + manual Refresh | Keeps under Sheets API quotas; feels live |

### Two-layer auth model

Authentication and authorization are intentionally separated:

- **Authentication** (who are you?) — Google OIDC, handled by Streamlit's native `st.login()`. User signs in with the Google account whose email they used on the form.
- **Authorization** (are you allowed in?) — after authentication, the app checks whether `st.user.email` exists in the sheet's email column. If not, the user sees a "please fill the form first" screen.

To admit a new member → they fill the form → their email lands in the sheet → they can sign in. Zero admin overhead.

---

## 2. Components

### 2.1 Data layer (`load_directory`, `allowed_emails`)
- `gspread` with a service account, read-only.
- Reads the worksheet into a pandas DataFrame.
- Caches for 5 minutes (`@st.cache_data(ttl=300)`).
- Emails are lowercased + stripped for reliable comparison.
- Separate cached `allowed_emails()` set for O(1) allowlist lookups.
- Sidebar "Refresh" button clears both caches.

### 2.2 Auth layer (`main`, `login_view`, `not_in_directory_view`)
- Three routing states:
  1. `st.user.is_logged_in` is false → show `login_view`.
  2. Logged in but email not in allowlist → show `not_in_directory_view` (form link + sign-out).
  3. Logged in and email in allowlist → show `directory_view`.
- No session-state bookkeeping — Streamlit handles the cookie.

### 2.3 Drive photo transform (`extract_drive_id`, `drive_thumbnail`)
- Parses the three common Drive share URL shapes (`/file/d/ID`, `?id=ID`, `/d/ID`).
- Returns `https://drive.google.com/thumbnail?id={ID}&sz=w400`.
- Requires each photo file to be shared "Anyone with the link — Viewer" (default for Form uploads).

### 2.4 Presentation (`person_card`, `directory_view`)
- Two-up responsive card grid.
- Search across name, city, company, profession, industry.
- Country multi-select filter.
- Initial-letter avatar fallback when no photo.
- Collapsible "Open to" section for networking preferences.

### 2.5 Column mapping (`COLS` in `app.py`)
- Maps logical keys to the sheet's exact header row.
- Networking data has a fallback mechanism — see [`CLAUDE_CODE_BRIEF.md`](./CLAUDE_CODE_BRIEF.md#3-data-model--the-sheet) for the M/N/O quirk explanation.

---

## 3. Setup

See [`CLAUDE_CODE_BRIEF.md` → Section 5](./CLAUDE_CODE_BRIEF.md#5-setup--step-by-step-target-one-evening) for the full step-by-step. Summary:

1. Sheet already exists — just verify headers.
2. Verify form-upload photos are "Anyone with link — Viewer" (one incognito check).
3. GCP: create project → enable Sheets + Drive APIs.
4. Service account + JSON key → share sheet with its email as Viewer.
5. OAuth 2.0 client (Web app) → grab client ID + secret.
6. Populate `.streamlit/secrets.toml` locally.
7. `streamlit run app.py` — smoke test.
8. Push to GitHub → deploy on `share.streamlit.io` → paste secrets.
9. Add production `redirect_uri` to the OAuth client in GCP.

---

## 4. Operational notes

- **Freshness:** new form submissions are visible after ≤ 5 min, or instantly via the sidebar Refresh.
- **Quotas:** Sheets API free tier is 300 reads/min/project — far above anything this app does.
- **Cold start:** Streamlit Cloud free-tier apps sleep after ~7 days of no traffic; first visitor wakes it (5–15s).
- **Logs:** `share.streamlit.io` → your app → Manage app → Logs.
- **Sign-in loop debugging:** if sign-in redirects back to the login page forever, the `redirect_uri` in `secrets.toml` doesn't match the one in the GCP OAuth client. They must be byte-identical.

---

## 5. Security posture

- No passwords stored anywhere. Google handles authentication.
- Allowlist is a single source (the sheet). To revoke access → delete a row.
- Sheet itself is never exposed — only the app's rendered view.
- Photos go through `drive.google.com/thumbnail` — someone inspecting HTML can grab that URL. Treat photos as semi-public.
- Cookie secret should be a strong random string; rotating it logs everyone out.
- OAuth consent screen should be **Published**, not Testing, so batch members can sign in without being added as "test users".

---

## 6. File layout

```
batch-directory/
├── app.py                              # Streamlit app
├── requirements.txt                    # pinned deps
├── README.md                           # this file
├── CLAUDE_CODE_BRIEF.md                # feed this to Claude Code CLI
├── .gitignore
└── .streamlit/
    ├── secrets.toml.example            # template — committed
    └── secrets.toml                    # real secrets — NEVER committed
```

---

## 7. Future enhancements (parked)

Map view (Plotly `scatter_geo`) · PDF export · WhatsApp click-to-chat · Last-login tracking (requires write scope) · Role-based admin view · Weekly "batchmates you may not have met" digest via Resend.
