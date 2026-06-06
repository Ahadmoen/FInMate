# FinMate Alerts — n8n setup & user guide

Two scheduled n8n workflows that read FinMate's daily ML output from Supabase
and send personalised email + Slack notifications to users three times a day
during the trading week.

```
n8n/
├── workflow_a_strong_signals.json    ← Generic broadcast (top pick + digest)
├── workflow_b_portfolio_alerts.json  ← Portfolio-aware (per holding)
├── local_workflow_a_strong_signals.json    ← Local-only, key pre-filled
├── local_workflow_b_portfolio_alerts.json  ← Local-only, key pre-filled
└── alert.md                          ← this doc
```

---

## 1. What the two workflows do

### Workflow A — Generic Strong-Buy Broadcast

Fires at the cron time. Filters `stock_signal` rows to `signal = STRONG_BUY` with `suggestion_confidence = HIGH`. Sorts descending by `blended_score`. The top entry becomes the **Top Pick**; the rest go into a **Digest**.

- **Audience:** every user opted into the current time window (and at least one channel).
- **Two messages per user per cron:**
  1. **Top Pick** — a detailed card for the single highest-scoring STRONG_BUY. Full Claude explanation, technicals table, news headlines.
  2. **Digest** (2 min later) — a compact table of all *other* STRONG_BUYs. One row per ticker: price · change% · RSI · one-line Claude summary.
- Each message goes out on every enabled channel (email + slack) per user, so 4 messages max per user per cron if both channels are on.

### Workflow B — Portfolio Alert

Fires **5 min after the cron time** (so the user sees the market view first).

- **Audience:** only users who own the affected ticker in `holding`.
- **Trigger:** `stock_signal.signal IN (SELL, STRONG_SELL)` for any ticker the user holds.
- **Personalisation:** each notification includes the user's quantity, average buy price, and current unrealised P&L.
- One notification per (user × held ticker × channel).

### Per-cron timeline

| t (PKT) | Event |
|---|---|
| 09:00 | Workflow A cron fires |
| 09:00 | Top Pick message sent |
| 09:02 | Digest message sent |
| 09:05 | Workflow B cron fires (after its 5-min wait) → per-holding sells |

Same shape repeats at 12:00 and 18:40.

---

## 2. Schedule

| Window | Cron (PKT) | Cron (UTC) | Preference flag |
|---|---|---|---|
| Pre-market | 09:00 | `0 4 * * 1-5` | `pre_market` |
| Mid-session | 12:00 | `0 7 * * 1-5` | `mid_session` |
| Post-market | 18:40 | `40 13 * * 1-5` | `post_market` |

Mon–Fri only. All three windows read the same `stock_signal` rows (updated nightly by `finmate-warm-4-ingest` at 18:35 PKT).

---

## 3. Credentials & env vars

The JSONs reference two secrets via n8n env-var expressions (no real keys committed to git):

| Reference | What | How to set |
|---|---|---|
| `{{ $env.SUPABASE_KEY }}` | Supabase API key — used in both `apikey` header and `Authorization: Bearer` header | see below |
| `{{ $env.GEMINI_API_KEY }}` | Google Gemini API key — used in every `Claude — *` HTTP node (named that for clarity; under the hood the calls go to `generativelanguage.googleapis.com`) | see below |

The Supabase REST endpoint (`https://jfljvmprzmcridtlmnif.supabase.co/rest/v1`) is hardcoded — not secret, swap with find-replace if you migrate.

### Setting the env vars in n8n

**Self-hosted Docker / npm:**

Pass them into the n8n process. For Docker:
```bash
docker run -e SUPABASE_KEY="eyJhbGc…" -e GEMINI_API_KEY="AIzaSy…" -e N8N_BLOCK_ENV_ACCESS_IN_NODE=false n8nio/n8n
```

`N8N_BLOCK_ENV_ACCESS_IN_NODE=false` is the critical part — without it, n8n returns "access to env vars denied" when nodes try to read `$env.*`.

For `docker-compose.yml`:
```yaml
services:
  n8n:
    environment:
      - SUPABASE_KEY=eyJhbGc…
      - GEMINI_API_KEY=AIzaSy…
      - N8N_BLOCK_ENV_ACCESS_IN_NODE=false
```

Get a free Gemini key at **https://aistudio.google.com/app/apikey** — no credit card required. Free tier: 1,500 requests/day, well above our ~45/day max.

**n8n.cloud:** env vars aren't exposed to Code nodes. Either:
- find-replace `={{ $env.SUPABASE_KEY }}` → real key directly in the JSON before import, or
- create n8n Variables (Settings → Variables) and switch the expressions from `$env.*` to `$vars.*` in every HTTP node.

### Recommended key scope

The Supabase service-role key is admin-level — bypasses Row-Level Security. Better to create a scoped role with only:
- `SELECT` on `stock_signal`, `live_market_data`, `news_sentiment`, `notification_preference`, `user`, `portfolio`, `holding`
- `INSERT` on `alert`, `alert_log`

Generate a new key at Supabase → Settings → API and use that in `SUPABASE_KEY` instead of the service-role.

### Quick-start: import without setting env vars

Two `local_*.json` files exist in this directory (gitignored — they have the Supabase key baked in for direct import):

| File | What |
|---|---|
| `n8n/local_workflow_a_strong_signals.json` | Workflow A with Supabase key hardcoded |
| `n8n/local_workflow_b_portfolio_alerts.json` | Workflow B with Supabase key hardcoded |

Use these for testing — the `apikey`, `Authorization: Bearer`, and Gemini `x-goog-api-key` headers are all pre-filled. Import directly into n8n with no further setup.

The committed `workflow_*.json` files keep env-var refs and remain the canonical version.

### Email node (still parked)

The `Send Email` nodes ship with `disabled: true`. Enable them after wiring SMTP in n8n → Credentials → Email. Slack works out of the box — each user's webhook URL is read from `user.slack_webhook`.

---

## 4. Alert + AlertLog logging — per-user per-stock audit trail

Every notification fires the following two-step write:

1. **Create `Alert` row** with `user_id`, `ticker`, `signal` (BUY/HOLD/SELL — 3-class mapped from stock_signal's 5-class), `reason` (the Claude plain-English summary), `alert_window`. Returns the new alert's `id`.
2. **Create `alert_log` row** with `alert_id` (FK from step 1), `channel` (EMAIL / SLACK), `status` = SENT, `sent_at` = now.

So you can query "every alert sent to user X" via:
```sql
SELECT a.ticker, a.signal, a.reason, a.alert_window, a.created_at, al.channel
FROM alert a
LEFT JOIN alert_log al ON al.alert_id = a.id
WHERE a.user_id = '<uuid>'
ORDER BY a.created_at DESC;
```

| Workflow | What `Alert.ticker` is | What `Alert.signal` is |
|---|---|---|
| A — Top Pick | actual ticker (HBL, OGDC, …) | `BUY` |
| A — Digest | `DIGEST` (covers many tickers in one message) | `BUY` |
| B — Portfolio | actual ticker the user holds | `SELL` (3-class mapped from STRONG_SELL/SELL) |

For the Digest message, `Alert.ticker = 'DIGEST'` and `Alert.reason` says "Digest of N STRONG_BUY signals". The individual tickers inside the digest live in the HTML body but not in the audit trail — if you want per-ticker logging for the digest too, switch to Workflow A's "create one Alert per digest ticker" pattern (one more HTTP call per cron).

---

## 5. Importing the workflows

In n8n:

1. **Workflows → Import from File → `workflow_a_strong_signals.json`** (or the local_* variant for direct import)
2. **Workflows → Import from File → `workflow_b_portfolio_alerts.json`** (or the local_* variant)
3. Open each, toggle **Inactive → Active**.

n8n picks up the three Schedule Triggers per workflow and fires them automatically per the cron expressions.

### Testing

- Click **Test workflow** on a workflow — n8n runs it once immediately with whichever Schedule Trigger you click on.
- The Wait nodes (2 min for digest, 5 min for B) WILL fire during test runs — be patient.
- Common issue: the user's `notification_preference` row doesn't exist yet → no audience → workflow exits early with no items. That's correct behaviour.

---

## 6. The user-facing notification preferences UI

`notification_preference` already has the right columns — your frontend just needs to expose them as toggles:

```
Channels (which apps to ping me on)
  [x] Email          — alerts@yourdomain to your inbox
  [ ] Slack          — paste a webhook URL below

Time windows (when to ping me)
  [x] Pre-market   (09:00 PKT)
  [x] Mid-session  (12:00 PKT)
  [x] Post-market  (18:40 PKT)

Slack webhook URL:  [_______________________________________________]
```

Defaults from the Django model: all three time-windows ON, email ON, slack OFF.

---

## 7. The website's "Notifications Help" page

The link `https://finmate.app/docs/notifications` is referenced at the bottom of every alert. Mirror this content there so users know what each number means:

### What FinMate notifications are

You'll get a stock-market alert from FinMate up to three times each weekday:

- **Pre-market (09:00 PKT)** — a heads-up before trading opens
- **Mid-session (12:00 PKT)** — what's playing out during the day
- **Post-market (18:40 PKT)** — what happened today and what tomorrow may look like

You decide which of those three you want. You also decide whether they come by email, Slack, or both.

### Three types of alert per time window

- **Top Pick** — fires first. A detailed card for the single best STRONG_BUY of the day across PSX. Even users with no holdings get this.
- **Other Top Performers** (digest) — fires 2 minutes after Top Pick. A compact table of every *other* STRONG_BUY of the day. One-line plain-English summary per stock.
- **Position alert** — fires 5 minutes after the cron. Only sent to users holding a stock that our model recommends SELL or STRONG_SELL on. Includes your quantity, buy price, and current P&L.

### What the numbers mean

Each alert shows a few technical numbers in a small table. Here's what they mean in plain English:

| Number | What it tells you | Rule of thumb |
|---|---|---|
| **RSI 14** | How "stretched" the price is over the last 14 days. 0–100 scale. | Above 70 = possibly overbought, below 30 = possibly oversold |
| **MA 50** | Average closing price of the last 50 days | If today's price is well above MA50, the stock is in an uptrend |
| **MA 200** | Average of the last 200 days — the "long-term trend" line | Price above MA200 = the long-term trend is up |
| **Volatility** | How wildly the price has swung over the last 20 days, as a percent | Higher = bigger daily moves, both up and down |
| **Confidence** | How sure FinMate is — HIGH / MEDIUM / LOW | HIGH means multiple signals agree |
| **Change %** | Today's percentage change | Negative = price went down today |

You don't have to understand the math to use the alert. The plain-English explanation below the numbers is written by an AI assistant that translates them.

### Why are some signals "STRONG"?

The recommendation is one of five levels:

| Signal | Meaning |
|---|---|
| **STRONG BUY** | Multiple signals strongly agree this is a good time to buy |
| **BUY** | A buy opportunity, but with some caveats |
| **HOLD** | Mixed signals — don't act yet |
| **SELL** | Negative signals are forming |
| **STRONG SELL** | Multiple signals strongly agree to exit the position |

**General market alerts** (Top Pick + Digest) only fire for **STRONG_BUY** at HIGH confidence — to avoid notifying everyone about borderline calls.

**Position alerts** fire for **SELL** and **STRONG_SELL** on stocks you actually hold — because "your model is recommending sell on something you own" is action-worthy regardless of confidence level.

### Want fewer alerts?

Turn off the time windows you don't care about in **Settings → Notifications**. Or turn off a channel entirely — your preferences are honoured immediately, no re-deploy needed.

### Why didn't I get an alert today?

Common reasons:
- No stock hit STRONG_BUY at HIGH confidence today (most calm trading days)
- You don't hold any stock that got a SELL/STRONG_SELL signal
- All three of your time-window toggles are off
- Your channel toggle is off
- (Email only) Your inbox provider classified the message as spam — check there first

---

## 8. v1.2 roadmap — reply flow

Currently the workflows are one-way. v1.2 will let users reply.

### Email reply (lower lift)

1. Configure n8n's IMAP Trigger node to poll the alerts inbox every 5 min.
2. When a reply arrives, parse Subject for the ticker (or thread it via `In-Reply-To` → look up the original `alert` in `alert_log`).
3. Add an `alert_log.payload JSONB` column (one small migration) to store the full message context.
4. New workflow `workflow_c_email_reply.json`:
   ```
   [IMAP Trigger]
       ↓
   [Code: parse sender, ticker, message body]
       ↓
   [HTTP: lookup the recent alert for this user × ticker]
       ↓
   [HTTP: Claude — system prompt = original context, user message = reply]
       ↓
   [SMTP Send — reply in-thread]
   ```

### Slack reply (higher lift)

Slack webhooks are outbound-only. Need to upgrade to a Slack App with a bot token that each user installs into their workspace.

1. Register a FinMate Slack App at `api.slack.com/apps`.
2. OAuth scopes: `chat:write`, `app_mentions:read`, `im:history`, `im:write`.
3. Event Subscriptions → n8n webhook URL.
4. Per-user `team_id` + `bot_token` columns on the `user` table.
5. New workflow `workflow_d_slack_reply.json` that triggers on `app_mention`, looks up recent alert context, calls Claude, posts threaded reply.

---

## 9. Troubleshooting

| Symptom | Likely cause |
|---|---|
| "access to env vars denied" in any HTTP node | Set `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` and restart n8n, OR use the `local_*.json` variants |
| "Node X hasn't been executed" inside a Code node | Upstream emitted 0 items so downstream branch never ran. Code nodes early-return [] when this happens (already handled in the JSONs) |
| Workflow A: "Split top + rest" emits 0 items | No `STRONG_BUY` at HIGH confidence in `stock_signal` right now — most calm days |
| Workflow A: top pick fires but digest doesn't | Only 1 strong-buy signal today (digest needs ≥1 *additional*) — expected |
| Workflow B: "Join + fan out" emits 0 items | No overlap between users' holdings and today's SELL/STRONG_SELL signals — expected on quiet days |
| "Create Alert row" returns 4xx | Check `user_id` exists in `user` table; FK violation |
| "Log to alert_log" returns 4xx | Check `alert_id` was captured by "Thread alert_id" — inspect that node's output |
| Slack POST returns 404 / no_service | User's `slack_webhook` URL is expired/revoked — clear it from their record |
| Slack POST returns 400 | Block Kit JSON malformed — check Code node output |
| Email node "no credentials" | Enable the email node after wiring SMTP in n8n → Credentials |
| Gemini returns 429 | Free-tier rate limit (15 req/min). Add a short delay between top + digest, or upgrade |
| Gemini returns 400 with `INVALID_ARGUMENT` | Body schema mismatch — Gemini expects `systemInstruction` + `contents`, not Anthropic's `messages` |
| Gemini returns 403 | `GEMINI_API_KEY` env var wrong, revoked, or restricted by IP/referer |
| Supabase returns 401 | `SUPABASE_KEY` wrong, or anon key without the right RLS policies |
