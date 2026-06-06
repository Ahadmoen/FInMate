# Manual Testing — Alert Dispatch on Cloud Run

How the frontend dev (or anyone) can manually trigger the alert
dispatcher running on Cloud Run, then verify it landed in Supabase
and in the in-app endpoints.

> **GCP credentials:** ask Ahad on the team chat for
> `gcloud auth login` access + project access. Not in this doc on
> purpose.

---

## 0. One-time setup

Install the `gcloud` CLI: https://cloud.google.com/sdk/docs/install

Then authenticate (Ahad shares the steps privately):

```bash
gcloud auth login                # opens browser to log in
gcloud config set project venom-scent-476112
gcloud config set run/region us-central1
```

Verify access:

```bash
gcloud run jobs list --region=us-central1 | grep alerts
# → finmate-alerts-dispatch     ...    YES
```

---

## 1. Manually fire one alert window

```bash
# Pre-market (09:00 PKT in prod)
gcloud run jobs execute finmate-alerts-dispatch \
  --region=us-central1 \
  --args=PRE_MARKET \
  --wait

# Mid-session (12:00 PKT in prod)
gcloud run jobs execute finmate-alerts-dispatch \
  --region=us-central1 \
  --args=MID_SESSION \
  --wait

# Post-market (18:40 PKT in prod)
gcloud run jobs execute finmate-alerts-dispatch \
  --region=us-central1 \
  --args=POST_MARKET \
  --wait
```

`--wait` blocks your terminal until the job finishes (5-6 min because
of the 2-min + 3-min sleeps between Top Pick → Digest → Position
Alerts). To skip the waits when testing:

```bash
# --no-delay runs all 3 sub-tasks back-to-back (~30 seconds total)
gcloud run jobs execute finmate-alerts-dispatch \
  --region=us-central1 \
  --args=PRE_MARKET,--no-delay \
  --wait
```

To skip Workflow B (position alerts on holdings):

```bash
gcloud run jobs execute finmate-alerts-dispatch \
  --region=us-central1 \
  --args=PRE_MARKET,--no-delay,--skip-position \
  --wait
```

## 2. Watch the logs

```bash
# Most recent execution ID
EXEC=$(gcloud run jobs executions list \
  --job=finmate-alerts-dispatch \
  --region=us-central1 \
  --limit=1 --format="value(name)")
echo "Latest execution: $EXEC"

# Tail the logs of that execution
gcloud logging read \
  "resource.type=\"cloud_run_job\" labels.\"run.googleapis.com/execution_name\"=\"$EXEC\"" \
  --limit=40 --format="value(textPayload)" --order=asc
```

Expected log shape on a successful run:

```
[20:01:00Z] alerts.dispatch_alerts PRE_MARKET
[PRE_MARKET] dispatch_top_pick
  top_pick: {'sent': 1, 'ticker': 'HBL'}
[PRE_MARKET] dispatch_digest
  digest: {'sent': 1, 'digest_size': 14}
[PRE_MARKET] dispatch_position_alerts
  position_alerts: {'sent': 0}
[PRE_MARKET] DONE
```

`sent` is the number of users that received the alert. `0` means
nobody matched the criteria for that sub-task (e.g. no user opted
into that window, or no STRONG_BUY signals in the DB).

## 3. Make sure your user gets notifications

The dispatcher only emails users who:
- Have `NotificationPreference.<window> = true` for the current window
- Have `in_app_enabled = true`
- For email: have `@gmail.com` address (allow-list)
- For Workflow B: have a `PortfolioHolding` row matching a
  SELL/STRONG_SELL signal

Set yourself up by running this SQL in Supabase SQL Editor:

```sql
-- 1. Find your user id
SELECT id, email FROM "user" WHERE email = 'YOUREMAIL@gmail.com';

-- 2. Ensure preferences exist for all windows + in-app + email
INSERT INTO notification_preference (
  id, user_id,
  in_app_enabled, email_enabled,
  whatsapp_enabled, slack_enabled,
  pre_market, mid_session, post_market
)
SELECT
  gen_random_uuid(), u.id,
  true, true,
  false, false,
  true, true, true
FROM "user" u
WHERE u.email = 'YOUREMAIL@gmail.com'
ON CONFLICT (user_id) DO UPDATE
SET in_app_enabled = true,
    email_enabled = true,
    pre_market = true,
    mid_session = true,
    post_market = true;

-- 3. (Optional, for Workflow B) Add a holding so you receive
--    SELL/STRONG_SELL position alerts
INSERT INTO portfolio_holdings (user_id, symbol_id, quantity, avg_buy_price)
SELECT
  u.id,
  s.id,
  100,         -- quantity
  300.00       -- average buy price
FROM "user" u, stock_symbol s
WHERE u.email = 'YOUREMAIL@gmail.com'
  AND s.ticker = 'HBL'
ON CONFLICT (user_id, symbol_id) DO NOTHING;
```

## 4. Verify the result landed in Supabase

```sql
-- a) Latest notifications for your user (bell-icon feed)
SELECT n.id, n.type, n.category, n.read_at, n.created_at,
       a.ticker, a.signal, a.alert_window
FROM notification n
JOIN alert a ON a.id = n.alert_id
JOIN "user" u ON u.id = n.user_id
WHERE u.email = 'YOUREMAIL@gmail.com'
ORDER BY n.created_at DESC
LIMIT 10;

-- b) Email delivery status
SELECT al.channel, al.status, al.error_message, al.sent_at, a.ticker
FROM alert_log al
JOIN alert a ON a.id = al.alert_id
JOIN "user" u ON u.id = a.user_id
WHERE u.email = 'YOUREMAIL@gmail.com'
ORDER BY al.created_at DESC
LIMIT 10;
```

`alert_log.status` values:
- `SENT`    → email actually went out — check your inbox
- `PENDING` → email skipped (recipient domain not in allowlist)
- `FAILED`  → SMTP error; see `error_message`

## 5. Hit the in-app API on Cloud Run

Once notifications are in the DB, exercise the API endpoints the
mobile app will call. Get an auth token first:

```bash
# Use the LIVE Cloud Run URL (ask Ahad — looks like
# https://finmate-backend-xxxxx-uc.a.run.app or
# https://api.finmate.app)
API_BASE="https://api.finmate.app"

# Login → grab JWT
TOKEN=$(curl -sX POST "$API_BASE/api/users/login/" \
  -H 'content-type: application/json' \
  -d '{"username":"YOURUSERNAME","password":"YOURPASSWORD"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access'])")
echo "$TOKEN"
```

Then exercise each endpoint:

```bash
# Bell-icon unread count
curl "$API_BASE/api/alerts/notifications/unread-count/" \
  -H "Authorization: Bearer $TOKEN"
# → { "count": 2 }

# Full feed
curl "$API_BASE/api/alerts/notifications/" \
  -H "Authorization: Bearer $TOKEN"

# Single notification's rich payload (paste any id from list)
NOTIF_ID=...
curl "$API_BASE/api/alerts/notifications/$NOTIF_ID/detail/" \
  -H "Authorization: Bearer $TOKEN"

# Mark it read
curl -X PATCH "$API_BASE/api/alerts/notifications/$NOTIF_ID/read/" \
  -H "Authorization: Bearer $TOKEN"

# Clear all unread
curl -X POST "$API_BASE/api/alerts/notifications/mark-all-read/" \
  -H "Authorization: Bearer $TOKEN"
```

Full endpoint spec + payload shapes per notification type:
[in_app_notifications_frontend.md](in_app_notifications_frontend.md)

## 6. Check email inbox

If the AlertLog shows `SENT` and your `@gmail.com` address was on
the recipient list, you should see two emails (per fired window):

- `Top Pick: XYZ ▲ STRONG BUY — Pre-Market Outlook`
- `14 more strong-buy moves — Pre-Market Outlook`

If you also hold a stock that flipped to SELL/STRONG_SELL, you'll
also get:

- `Position alert — XYZ ▼ STRONG SELL`

Sender shows as `FinMate <ahadsgmail@gmail.com>`.

## 7. Common issues

| Symptom | Fix |
| ------- | --- |
| `top_pick: {'sent': 0, 'reason': 'no signals'}` | No `STRONG_BUY` + `HIGH` rows in `stock_signal` right now. Wait for the next warm-3/warm-4 cycle or load fixture data. |
| `position_alerts: {'sent': 0}` | Either no `SELL/STRONG_SELL` signals exist, or your test user has no `portfolio_holdings` row matching one. |
| Got the notification row in DB but no email | Check `alert_log.status`. `PENDING` = domain allowlist skipped it. `FAILED` = look at `error_message`. |
| `AUTH 535 5.7.8` in error_message | Backend's `GMAIL_APP_PASSWORD` is wrong / not the 16-char App Password. Ping Ahad. |
| Email subject says "STRONG BUY" but my Gemini text is generic | Gemini API was down — fell back to template. Notification still landed correctly. |
| `gcloud run jobs execute` says permission denied | You need IAM access. Ahad adds you on `roles/run.developer`. |

## 8. Scheduled runs (production)

Once it's all working manually, the **Cloud Scheduler** crons fire
automatically Mon-Fri:

| Window         | PKT cron | UTC cron     |
| -------------- | -------- | ------------ |
| `PRE_MARKET`   | 09:00    | `0 4 * * 1-5` |
| `MID_SESSION`  | 12:00    | `0 7 * * 1-5` |
| `POST_MARKET`  | 18:40    | `40 13 * * 1-5` |

Each window fires Top Pick immediately, Digest +2 min, Position
Alerts +5 min from the start. So a 09:00 fire produces three waves
of notifications between 09:00–09:05.

To pause auto-firing during testing:

```bash
gcloud scheduler jobs pause finmate-alerts-pre-market --location=us-central1
gcloud scheduler jobs pause finmate-alerts-mid-session --location=us-central1
gcloud scheduler jobs pause finmate-alerts-post-market --location=us-central1
```

Resume with `gcloud scheduler jobs resume <name>`.

## 9. What's NOT in this doc

- **Local Django dev server testing** — possible but ask Ahad for the
  shared `.env` first
- **WhatsApp / Slack channels** — stubs only, pending schema migration
- **Push notifications (APNs / FCM)** — not implemented yet
- **Frontend integration spec** — see
  [in_app_notifications_frontend.md](in_app_notifications_frontend.md)
