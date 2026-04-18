# Claude Code brief — CN88 Batch Directory

> Paste this whole file into Claude Code as the initial brief. It contains everything needed: context, data model, auth model, files, setup steps, and acceptance criteria. Treat it as the source of truth for this project.

---

## 0. TL;DR for Claude Code

**Task:** Build a members-only web directory for the Christ Nagar School Class of 1988 batch (~81 members). Backed by an existing Google Form → Google Sheet. Deployed on Streamlit Community Cloud (free tier). Gated by **Google Sign-In** — only people whose email is in the sheet can see the directory.

**Stack:** Python 3.11+, Streamlit ≥ 1.42 (native OIDC), gspread, pandas, Authlib.

**Priority:** Ship fast. Prefer stdlib + battle-tested libs over clever. Clean, minimal code. One `app.py` is fine — don't over-engineer.

**Starter code:** `app.py`, `requirements.txt`, `.streamlit/secrets.toml.example`, `.gitignore`, `README.md` are already provided in the repo root. Your job is to (a) verify the schema matches the live sheet, (b) help Sreek walk through GCP setup, (c) test locally, (d) deploy to Streamlit Cloud.

---

## 1. Context — WHAT & WHY

### What we're building
A private online directory for the **CN88 batch** (Christ Nagar School, Trivandrum, Class of 1988). Members have filled a Google Form capturing their details (name, photo, current city, profession, family, networking interests). Responses flow into a Google Sheet. We need to surface this as a searchable web app, accessible only to members.

### Why this architecture
- **Sheet stays source of truth.** The form keeps working unchanged; batch admins edit in Sheets. Zero migration.
- **Streamlit free tier.** Python-native, ties to a GitHub repo, zero infra management, zero cost. Cold-start delay (~10s) is acceptable for this use case.
- **Google Sign-In (OIDC).** Eliminates password management entirely. Everyone in the batch already has a Google account (they filled a Google Form). Streamlit 1.42+ provides native OIDC via `st.login()` — no third-party auth libraries needed.
- **Sheet-based allowlist.** Authorization is a set membership check against emails in the sheet. Adding a new member = they fill the form = they can log in. No admin workflow.

### Non-goals
- Per-user profile editing inside the app (they use the form; Google Forms has "edit your response" built-in).
- Admin dashboard (the Google Sheet *is* the admin dashboard).
- Mobile app, offline mode, i18n.
- Anything requiring a database.

---

## 2. Architecture — HOW

```
┌──────────────┐       auto-append        ┌───────────────────┐
│ Google Form  │  ───────────────────▶    │   Google Sheet    │  ← source of truth
└──────────────┘                          └─────────┬─────────┘
                                                    │ read-only, service account
                                                    ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Streamlit app (Python)                      │
│                                                                  │
│   ┌────────────────┐   ┌──────────┐   ┌────────────────────┐     │
│   │  AuthN         │──▶│  AuthZ   │──▶│   Directory UI     │     │
│   │  st.login()    │   │  email ∈ │   │  (cards + search)  │     │
│   │  Google OIDC   │   │  sheet   │   │                    │     │
│   └────────────────┘   └──────────┘   └────────────────────┘     │
│                                                                  │
│   Drive photo URL → thumbnail URL transform                      │
│   5-min TTL cache + manual refresh                               │
└────────────────────────────┬─────────────────────────────────────┘
                             │ HTTPS
                             ▼
                  ┌──────────────────────────┐
                  │ Streamlit Community Cloud│
                  │ (free tier, GitHub repo) │
                  └──────────────────────────┘
```

### Auth model — two distinct layers

| Layer | What it answers | Mechanism |
|---|---|---|
| Authentication | "Who is this person?" | `st.login()` → Google OIDC → email, name, picture in `st.user` |
| Authorization | "Are they allowed in?" | `st.user.email.lower() in allowed_emails_from_sheet` |

Decoupling these is the whole point. Google handles auth; the sheet is the ACL. To revoke someone, delete their row. To add someone, they fill the form.

### Component responsibilities

1. **Data layer** (`load_directory`, `allowed_emails`) — reads sheet via gspread with a service account, returns a pandas DataFrame, caches for 5 min, exposes an email set for fast allowlist lookup.
2. **Auth layer** (`main()` routing) — three states: not-logged-in → logged-in-but-not-authorized → authorized.
3. **Drive transform** (`extract_drive_id`, `drive_thumbnail`) — parses Drive share URLs (`/file/d/{ID}/view`, `?id={ID}`, etc.) and returns `https://drive.google.com/thumbnail?id={ID}&sz=w400`.
4. **Presentation** (`person_card`, `directory_view`) — responsive 2-up card grid, search box, country filter, refresh button.

---

## 3. Data model — THE SHEET

**Sheet URL:** `https://docs.google.com/spreadsheets/d/1k-rMUMV_DYhuQxT5AhKUBr5tjaQICxhPN_4Lyt-TZQI/edit`
**Worksheet tab:** `Form responses 1` (lowercase `r`)
**Row count as of 18-Apr-2026:** 81 member rows (row 2–82)

### Column map (captured from live sheet)

| Col | Header (exact) | Notes |
|---|---|---|
| A | `Timestamp` | Auto from form |
| B | `First Name` | |
| C | `Last Name` | |
| D | `Photo` | Drive URL, `https://drive.google.com/open?id=...` format |
| E | `Primary Email ID` | **The allowlist key** — normalize to lowercase |
| F | `Mobile` | Mixed formats; treat as string |
| G | `Current City of Residence` | |
| H | `State` | |
| I | `Country` | Includes "India", "USA", "United States", "UAE", "Canada", "UK", "Sweden", "Singapore", "Kuwait", "Bahrain", "KSA", "Australia" — expect inconsistent spellings |
| J | `Work / Profession` | Free text |
| K | `Company` | Free text |
| L | `Industry Sector` | Semi-controlled (has "Other" option) |
| M | `Family & Life Highlights Legacy / Single/Married, Spouse: [Name]` | Combined family text |
| N | `Children: [Name/Age/Current Study or Job]. This helps us facilitate internship matching and organize family-inclusive batch meets.` | ⚠️ **Header says "Children" but actual data is networking preferences.** Sheet header glitch from long form description text. |
| O | `Networking and Contribution` | Currently empty in all rows; may populate later |

**Column N/O quirk:** The app handles this by using `networking_primary = column O` with fallback to `networking_fallback = column N`. Do not rename headers in the sheet (it would break the form→sheet linkage).

### Data hygiene the code handles
- Trailing empty row (row 82 in current sheet is partial).
- Lowercase + strip emails before allowlist comparison.
- Missing photo → initial-letter avatar fallback.
- Missing any field → silently omit from card, don't show "None".

---

## 4. Files in the repo

```
batch-directory/
├── app.py                              # Streamlit app — full implementation
├── requirements.txt                    # streamlit[auth], gspread, google-auth, pandas, Authlib
├── README.md                           # setup + architecture for future reference
├── CLAUDE_CODE_BRIEF.md                # this file
├── .gitignore
└── .streamlit/
    ├── secrets.toml.example            # committed template
    └── secrets.toml                    # real secrets — NEVER committed
```

---

## 5. Setup — STEP-BY-STEP (target: one evening)

### 5.1 Prep the Google Sheet
1. Open the sheet. Confirm the worksheet tab is named exactly `Form responses 1`.
2. Verify row 1 headers match the column map in Section 3. If they've drifted, update the `COLS` dict in `app.py` to match.
3. Copy the full sheet URL.

### 5.2 Verify photo permissions (critical — easily missed)
When someone uploads via a Google Form file-upload question, Google puts the file in a folder on the form owner's Drive, usually with "Anyone with link — Viewer" by default.
1. Pick any photo URL from column D.
2. Open it in an **incognito window**. If it renders → permissions are good.
3. If not → open the Drive folder the form uses → select all uploaded photos → Share → "Anyone with the link — Viewer".

### 5.3 Create Google Cloud project + enable APIs (≈5 min)
1. Go to `console.cloud.google.com` → create project `cn88-directory`.
2. **APIs & Services → Library** → enable:
   - Google Sheets API
   - Google Drive API

### 5.4 Service account for sheet reads (≈3 min)
1. **IAM & Admin → Service Accounts → Create Service Account** → name `directory-reader` → no role assignment needed → Done.
2. Open the account → **Keys → Add key → JSON** → download the `.json` file. Keep it secure.
3. Back in the sheet → **Share** → paste the service-account email (looks like `directory-reader@cn88-directory.iam.gserviceaccount.com`) → role **Viewer** → uncheck "Notify people" → Share.

### 5.5 OAuth 2.0 client for Google Sign-In (≈10 min)
This is the bit that powers `st.login()`.

1. **APIs & Services → OAuth consent screen**
   - User Type: **External** (so anyone with a Google account can sign in — authorization is our job, not Google's).
   - App name: `CN88 Batch Directory`.
   - User support email: Sreek's email.
   - Developer contact: Sreek's email.
   - Scopes: default `openid`, `email`, `profile` (Streamlit adds these automatically — nothing to configure).
   - Test users: **not needed** once you publish. While in Testing mode, add Sreek's email as a test user so you can log in during development.
   - Publish app when ready (it's low-sensitivity since we only read email/name/picture — no Google verification required for these scopes).

2. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   - Application type: **Web application**.
   - Name: `CN88 Streamlit`.
   - Authorized JavaScript origins:
     - `http://localhost:8501`
     - `https://<your-future-app>.streamlit.app` (you can add this after first deploy)
   - Authorized redirect URIs:
     - `http://localhost:8501/oauth2callback`
     - `https://<your-future-app>.streamlit.app/oauth2callback`
   - Click Create → copy the **Client ID** and **Client Secret**.

### 5.6 Local configuration
1. Clone the repo locally.
2. `cp .streamlit/secrets.toml.example .streamlit/secrets.toml`.
3. Generate cookie secret:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
4. Populate `secrets.toml`:
   - `[auth]` block: `redirect_uri`, `cookie_secret`, `client_id`, `client_secret`.
   - `[gsheet]` block: sheet URL.
   - `[form]` block: form share link.
   - `[gcp_service_account]` block: paste every key from the downloaded JSON.

### 5.7 Local test
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
Visit `http://localhost:8501`.
- See login screen → click "Sign in with Google" → Google OAuth flow → redirects back.
- Sign in with Sreek's batch email → should see the directory with all 81 members.
- Sign in with a different Google account (not in the sheet) → should see the "not in directory" screen.
- Test sign out → back to login screen.

### 5.8 Deploy to Streamlit Community Cloud
1. Push the repo to GitHub (private recommended). **Do not commit `secrets.toml`.**
2. Go to `share.streamlit.io` → sign in with GitHub → **New app** → pick repo, branch `main`, file `app.py`.
3. Give it a custom subdomain, e.g. `cn88-directory` → so the URL is `https://cn88-directory.streamlit.app`.
4. **Advanced settings → Secrets** → paste the contents of your local `secrets.toml`, but **change `redirect_uri`** to `https://cn88-directory.streamlit.app/oauth2callback`.
5. Deploy.

### 5.9 Add the production redirect URI to Google Cloud
Back in GCP → **Credentials → CN88 Streamlit client**:
- Authorized JavaScript origins → add `https://cn88-directory.streamlit.app`.
- Authorized redirect URIs → add `https://cn88-directory.streamlit.app/oauth2callback`.
- Save. (Takes ~1 minute to propagate.)

### 5.10 Share with the batch
Post the URL on the batch WhatsApp. No password needed — just Google Sign-In. Include the form link for people who haven't filled it yet.

---

## 6. Acceptance criteria — how "done" looks

- [ ] Visiting the app URL while signed out shows the login screen with a single "Sign in with Google" button.
- [ ] Clicking it redirects to Google, authenticates, returns to the app.
- [ ] Users whose Google email matches a row in the sheet see the full directory.
- [ ] Users whose Google email is *not* in the sheet see the "not yet in directory" screen with a link to the form and a sign-out button.
- [ ] Directory shows all ~81 members with photos (where available), name, location, role, family, networking prefs.
- [ ] Search filters across name, city, company, profession, industry.
- [ ] Country filter works.
- [ ] Refresh button re-fetches the sheet.
- [ ] New form submission appears in the app within ≤ 5 min (or immediately after clicking Refresh).
- [ ] Signing out returns to the login screen and clears the session.
- [ ] `secrets.toml` is in `.gitignore` and not committed.

---

## 7. Known gotchas — save yourself debugging time

1. **`redirect_uri` must match exactly** between `secrets.toml` and the GCP OAuth client — scheme, host, port, path. `http://localhost:8501/oauth2callback` ≠ `http://localhost:8502/oauth2callback` ≠ `https://…`.
2. **Cookie secret must be strong and stable.** Regenerating it logs everyone out. Store it like a password.
3. **`Authlib>=1.3.2` is required.** Streamlit's auth depends on it; `streamlit[auth]` installs it automatically.
4. **OAuth consent screen in "Testing" mode** limits sign-ins to listed test users. Publish it (no verification needed for basic scopes) before sharing the URL with the batch.
5. **Drive thumbnails 404 silently** if the file isn't "Anyone with link — Viewer". Always sanity-check one photo in incognito.
6. **Streamlit Cloud apps sleep** after ~7 days of no traffic. First visitor wakes it (5–15s). Fine, just warn the batch on WhatsApp.
7. **Email case & whitespace** — always `.strip().lower()` on both sides of the allowlist comparison. Some form entries have trailing spaces.
8. **Sheet header drift** — if someone edits the header row in Sheets, the `COLS` map in `app.py` breaks. Keep headers immutable; they're tied to the form.

---

## 8. Future enhancements (not in scope for v1)

- **Map view** — Plotly scatter_geo or pydeck showing where batchmates live.
- **Directory export** — "Download as PDF" button (WeasyPrint or reportlab).
- **Message-a-batchmate** — mailto: links are already there; could add WhatsApp click-to-chat for mobile numbers.
- **Last-login tracking** — write back to a separate sheet on login (would need write scope).
- **Role-based admin view** — an `is_admin` flag in a small config sheet to give certain members CRUD buttons.
- **Email digest** — "5 batchmates you might not know" weekly email via Resend/SendGrid.

---

## 9. What Claude Code should do, in order

1. Read `app.py`, `requirements.txt`, `.streamlit/secrets.toml.example`, `README.md` — understand the starter.
2. Ask Sreek to run a one-liner to print the exact sheet headers — confirm they match `COLS`.
3. Walk Sreek through Section 5.3–5.5 interactively (GCP project → service account → OAuth client). Keep it to the minimum number of clicks.
4. Help him populate `secrets.toml` locally. Verify format (especially the `private_key` multi-line).
5. Run `streamlit run app.py` locally. Debug any issues.
6. Help him push to GitHub (private repo) and deploy on Streamlit Cloud.
7. Add the production redirect URI to the OAuth client.
8. Smoke-test end-to-end: sign in as him (should work), sign in as someone not in sheet (should see denial screen).
9. Update `README.md` with the final live URL and anything that needed changing during setup.

---

## 10. Style / quality bar

- Python 3.11+, type hints where they add clarity.
- No `print`; use `st.toast` or `st.error` for user-facing messages.
- No globals beyond the `COLS` config map and secrets-derived constants.
- Keep `app.py` under ~300 lines. If it grows, split into `auth.py`, `data.py`, `ui.py` — but only if necessary.
- No third-party auth libraries. Stick with native `st.login()`. Avoid `streamlit-authenticator` and `streamlit-oauth` — they're now legacy for this use case.
- No database. If state needs to persist beyond a session, write a separate sheet — don't introduce SQLite.
