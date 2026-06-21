# Instagram Comment-to-DM Automation

Watches specific Instagram posts for keyword comments, auto-replies publicly, and
sends the commenter a private DM — built entirely on the **official Instagram
Graph API** (no Selenium, no unofficial libraries).

---

## 1. Tech Stack

- **Backend:** Python + FastAPI
- **Database:** SQLite via SQLAlchemy (swap `DATABASE_URL` for Postgres anytime)
- **Frontend:** Vanilla HTML/JS/CSS, Jinja2 templates, no build step
- **Deploy:** Docker, `railway.toml`, `render.yaml`

---

## 2. Instagram API Setup (do this first)

### Step 1 — Convert your Instagram account
Your account must be a **Business** or **Creator** account, connected to a
Facebook Page.
Instagram app → Settings → Account type → switch to Professional → Business.

### Step 2 — Create a Facebook Developer App
1. Go to https://developers.facebook.com/apps
2. Click **Create App** → choose **Business** type.
3. Name it (e.g. "IG Comment Automation").

### Step 3 — Add the Instagram Graph API product
1. In your app dashboard, click **Add Product**.
2. Find **Instagram Graph API** and click **Set Up**.
3. Link the Facebook Page connected to your Instagram Business account.

### Step 4 — Add permissions
In **App Review → Permissions and Features**, request:
- `instagram_manage_comments`
- `instagram_manage_messages`
- `pages_show_list`
- `instagram_basic`

While in development mode, these work for accounts added as **Testers/Admins**
under **App Roles**. For production use with real customers, you'll need to
submit for **App Review** (see Step 7).

### Step 5 — Generate a long-lived Access Token
1. Go to **Graph API Explorer** (developers.facebook.com/tools/explorer).
2. Select your app, select your Page, and request the permissions above.
3. Generate a **User Access Token** (short-lived, ~1 hour).
4. Exchange it for a long-lived token (60 days) by calling:

```
GET https://graph.facebook.com/v19.0/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id={app-id}
  &client_secret={app-secret}
  &fb_exchange_token={short-lived-token}
```

5. **Refreshing:** Long-lived tokens last 60 days. Before they expire, call
   the same exchange endpoint again with your current (still-valid) long-lived
   token as `fb_exchange_token` to get a fresh 60-day token. Automate this
   with a cron job calling that endpoint every ~50 days.

### Step 6 — Configure the Webhook
1. In your app dashboard → **Webhooks** → **Instagram** → Subscribe.
2. Callback URL: `https://YOUR_DOMAIN/webhook/instagram`
3. Verify Token: any string you choose — put the same value in `.env` as
   `WEBHOOK_VERIFY_TOKEN`.
4. Subscribe to the **comments** field.

### Step 7 — Apply for `instagram_manage_messages` (for DMs)
Sending a DM to someone who hasn't messaged you first requires Meta's
approval of the **"Comment to DM"** / Human Agent use case under
**instagram_manage_messages**. Submit your app for review with a screen
recording showing: a user comments a keyword → your app replies → your app
DMs them. Until approved, DMs only work for users who messaged your
business within the last 24 hours (Meta's standard messaging window).

### Step 8 — Get a Post ID
1. Open **Graph API Explorer**.
2. Query: `GET /{ig-business-account-id}/media`
3. Copy the `id` field of the post you want to target — this is your **Post ID**,
   used in the dashboard's Campaign form.

---

## 3. Environment Variables

Copy `.env.example` to `.env` and fill in:

```
INSTAGRAM_ACCESS_TOKEN=
INSTAGRAM_BUSINESS_ACCOUNT_ID=
FACEBOOK_APP_SECRET=
WEBHOOK_VERIFY_TOKEN=
DATABASE_URL=sqlite:///./app.db
```

> Note: the Access Token and Business Account ID can also be entered/updated
> later from the **Settings** page in the dashboard — they're stored in the
> database, not hardcoded.

---

## 4. Running locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your values
uvicorn main:app --reload
```

Visit `http://localhost:8000/dashboard`.

For local webhook testing, expose your server with a tunnel
(e.g. `ngrok http 8000`) and use that HTTPS URL in Step 6 above.

---

## 5. Deploying

**Docker:**
```bash
docker build -t ig-automation .
docker run -p 8000:8000 --env-file .env ig-automation
```

**Railway:** push to a repo connected to Railway — `railway.toml` handles
build/deploy/health checks automatically. Set env vars in the Railway dashboard.

**Render:** connect the repo — `render.yaml` defines the service as a Docker
web service. Set the secret env vars in the Render dashboard (`sync: false`
fields).

---

## 6. How it works

1. Someone comments on a tracked post.
2. Meta sends a webhook `POST /webhook/instagram` with the comment payload.
3. The signature is verified using `X-Hub-Signature-256` + `FACEBOOK_APP_SECRET`.
4. The app checks: is this comment on a tracked **Campaign**'s post, and does
   it contain one of that campaign's keywords (case-insensitive, partial match)?
5. If yes and the comment hasn't been processed before (deduplication via the
   `ProcessedComment` table):
   - `instagram.reply_to_comment()` posts a public reply.
   - `instagram.send_dm()` sends the commenter a private message.
6. All Graph API calls retry with exponential backoff on rate limits (429) or
   transient 5xx errors.

---

## 7. Important constraints

- DMs require either a prior message from the user within 24h, or Meta's
  approval of the comment-triggered messaging use case (see Step 7 above).
- Only the official Instagram Graph API is used — no Selenium, no
  `instagrapi`, no unofficial scraping libraries.
- `/health` returns `{"status": "ok"}` for platform health checks.

---

## 8. Project structure

```
/
├── main.py
├── instagram.py
├── models.py
├── database.py
├── routes/
│   ├── webhook.py
│   ├── dashboard.py
│   └── api.py
├── static/
│   ├── style.css
│   └── app.js
├── templates/
│   ├── base.html
│   ├── settings.html
│   └── campaigns.html
├── .env.example
├── Dockerfile
├── railway.toml
├── render.yaml
└── requirements.txt
```
