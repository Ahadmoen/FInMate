# Notification Workflow — Frontend Integration Guide

How notifications flow from n8n → Supabase → your app, what each row
carries, and what to render where. Read alongside [alert.md](alert.md)
(setup guide) and the SQL schema below.

---

## 1. The end-to-end flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            n8n WORKFLOWS                                │
│                                                                         │
│  Workflow A (general)               Workflow B (portfolio)              │
│  ───────────────────                ───────────────────                 │
│  • Top Pick (1 STRONG_BUY)          • Position alert (SELL/STRONG_SELL  │
│    Gemini → detailed card             on holdings)                      │
│  • Digest (rest of STRONG_BUYs)     • Per-holder personalisation        │
│    Gemini batch → table view          (qty, avg buy, P&L)               │
│                                                                         │
│              Fires 3× daily Mon–Fri: 09:00 / 12:00 / 18:40 PKT          │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │  POST × 4 per send
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       SUPABASE (your app reads here)                    │
│                                                                         │
│   ┌──────────┐   ┌────────────────┐   ┌──────────────┐   ┌───────────┐  │
│   │  alert   │──▶│  alert_detail  │   │ notification │──▶│ alert_log │  │
│   │          │   │                │   │              │   │           │  │
│   │ user_id  │   │ alert_id   FK  │   │ user_id   FK │   │ alert_id  │  │
│   │ ticker   │   │ payload  JSONB │   │ alert_id  FK │   │ channel   │  │
│   │ signal   │   │ (close, RSI,   │   │ type         │   │ status    │  │
│   │ reason   │   │  news, summary,│   │ category     │   │ sent_at   │  │
│   │ window   │   │  P&L, …)       │   │ read_at      │   │ error_msg │  │
│   └──────────┘   └────────────────┘   └──────────────┘   └───────────┘  │
│        ▲                                     ▲                          │
│        │                                     │                          │
│        │ tap a notification                  │ frontend's primary       │
│        │ to load detail                      │ query: SELECT * FROM     │
│        │                                     │ notification WHERE       │
│        │                                     │ user_id = $me            │
│        └─────────────────────────────────────┘                          │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │  query
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND APP                               │
│                                                                         │
│   Feed screen                          Detail screen (on tap)           │
│   ─────────                            ──────────────────────            │
│   • One row per notification           • Pulls alert_detail by          │
│     - icon by type                       alert_id                       │
│     - title + summary                  • Renders full HTML/JSX          │
│     - timestamp                          (chart card, P&L block,        │
│     - unread badge                       news, summary)                 │
│   • Tap → mark read + show detail                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Schema of the 4 tables (frontend cheatsheet)

### `notification` — feed entry (PRIMARY query target)

| Column | Type | Frontend use |
|---|---|---|
| `id` | uuid PK | row key |
| `user_id` | uuid FK → user | filter — *always* `WHERE user_id = me` |
| `alert_id` | uuid FK → alert | join key to load detail |
| `type` | enum `TOP_PICK` / `DIGEST` / `POSITION_ALERT` | drives icon + heading |
| `category` | enum `stock` / `digest` | drives card layout (single ticker vs. table) |
| `read_at` | timestamptz nullable | NULL = unread; set on tap |
| `created_at` | timestamptz | "2 min ago" formatting |

### `alert` — the trigger

| Column | Type | Frontend use |
|---|---|---|
| `id` | uuid PK | |
| `user_id` | uuid FK | |
| `ticker` | varchar(10) | display in title — `'DIGEST'` means many tickers (use `alert_detail.payload.tickers` instead) |
| `signal` | enum `BUY` / `HOLD` / `SELL` | colour the badge |
| `reason` | text | one-paragraph plain-English summary (LLM-generated) |
| `alert_window` | enum `PRE_MARKET` / `MID_SESSION` / `POST_MARKET` | subheading: "Pre-Market Outlook" etc. |
| `created_at` | timestamptz | |

### `alert_detail` — rich payload (load on tap)

| Column | Type | Frontend use |
|---|---|---|
| `id` | uuid PK | |
| `alert_id` | uuid FK → alert | the join |
| `payload` | jsonb | the entire detail view's data — shape varies by type, see Section 3 |

### `alert_log` — delivery audit (admin / support only)

| Column | Type | Frontend use |
|---|---|---|
| `alert_id` | uuid FK | |
| `channel` | enum `EMAIL` / `SLACK` / `WHATSAPP` | |
| `status` | enum `SENT` / `FAILED` / `PENDING` | |
| `sent_at` | timestamptz | |
| `error_message` | text | shown to support if a delivery failed |

Frontend usually doesn't read `alert_log` — it's for an internal "did the email actually send?" dashboard.

---

## 3. `alert_detail.payload` shapes — per type

### Type = `TOP_PICK` (Workflow A — top pick)

```json
{
  "ticker": "HBL",
  "signal": "STRONG_BUY",
  "confidence": "HIGH",
  "close": 282.87,
  "change_pct": 0.36,
  "rsi14": 56.4,
  "ma50": 275.12,
  "ma200": 260.45,
  "volatility20d": 0.021,
  "news": [
    { "headline": "HBL profit jumps 24%…", "link": "https://…", "source": "Dawn", "sentiment": "GOOD" },
    { "headline": "Banking sector outlook…", "link": "https://…", "source": "BR", "sentiment": "NEUTRAL" }
  ],
  "summary": "HBL is showing strong upward momentum today — our models suggest…",
  "window_label": "Pre-Market Outlook",
  "type": "TOP_PICK"
}
```

### Type = `DIGEST` (Workflow A — digest)

```json
{
  "tickers": [
    { "ticker": "OGDC", "close": 306.75, "change_pct": 1.18, "rsi14": 65.1, "summary": "Energy sector picking up after recent dip." },
    { "ticker": "ZTL",  "close": 19.39,  "change_pct": 8.20, "rsi14": 71.8, "summary": "Strong volume breakout above MA200." },
    ...
  ],
  "count": 12,
  "window_label": "Mid-Session Update",
  "type": "DIGEST"
}
```

### Type = `POSITION_ALERT` (Workflow B)

```json
{
  "ticker": "ENGRO",
  "signal": "STRONG_SELL",
  "confidence": "HIGH",
  "qty": 50,
  "avg_buy": 510.00,
  "current": 485.38,
  "pnl_pct": -4.83,
  "pnl_pkr": -1231.00,
  "close": 485.38,
  "change_pct": -1.12,
  "rsi14": 32.4,
  "ma50": 495.20,
  "ma200": 530.10,
  "volatility20d": 0.035,
  "news": [ ... ],
  "summary": "ENGRO has shifted into a negative-momentum zone…",
  "window_label": "Post-Market Recap",
  "type": "POSITION_ALERT"
}
```

---

## 4. Frontend queries

### Notification feed (main screen)

```sql
SELECT n.id, n.type, n.category, n.read_at, n.created_at,
       a.ticker, a.signal, a.reason, a.alert_window
FROM notification n
JOIN alert a ON a.id = n.alert_id
WHERE n.user_id = $auth.user.id
ORDER BY n.created_at DESC
LIMIT 50;
```

Via Postgrest:
```
GET /notification?user_id=eq.<uuid>
   &select=id,type,category,read_at,created_at,alert:alert_id(ticker,signal,reason,alert_window)
   &order=created_at.desc
   &limit=50
```

### Unread badge count

```
GET /notification?user_id=eq.<uuid>&read_at=is.null&select=id
   (count from response length, or use Prefer: count=exact)
```

### Detail view (on tap)

```
GET /alert_detail?alert_id=eq.<alert.id>&select=payload
```

Returns one row with the JSONB `payload` — render based on `payload.type`.

### Mark as read

```
PATCH /notification?id=eq.<notification.id>
Headers: Prefer: return=minimal
Body: { "read_at": "<now ISO>" }
```

---

## 5. Visual mockups

### Notification feed (mobile / web list)

```
┌────────────────────────────────────────────────────┐
│ 🔔  Notifications                          ● 3 new │
├────────────────────────────────────────────────────┤
│                                                    │
│  ▲   Top Pick · HBL                          2m  ● │
│      Strong Buy — banking sector momentum…         │
│      Pre-Market Outlook                            │
│                                                    │
├────────────────────────────────────────────────────┤
│                                                    │
│  ▼   Position Alert · ENGRO                 2m  ●  │
│      Strong Sell — you hold this @ avg 510         │
│      Pre-Market Outlook                            │
│                                                    │
├────────────────────────────────────────────────────┤
│                                                    │
│  ≡   Today's Movers (12 stocks)             4m  ●  │
│      OGDC +1.2%, ZTL +8.2%, LUCK +0.8%, +9 more    │
│      Pre-Market Outlook                            │
│                                                    │
├────────────────────────────────────────────────────┤
│                                                    │
│  ▲   Top Pick · OGDC                      Yesterday│
│      Strong Buy — read                             │
│      Post-Market Recap                             │
│                                                    │
└────────────────────────────────────────────────────┘
```

Icon legend:
- `▲` green — STRONG_BUY (type=TOP_PICK or POSITION_ALERT with positive direction)
- `▼` red — STRONG_SELL / SELL (type=POSITION_ALERT)
- `≡` blue — multi-stock (type=DIGEST)

Unread state: bold text + filled dot at right. On tap → call **mark as read** API → navigate to detail.

### Detail view — TOP_PICK / POSITION_ALERT

```
┌────────────────────────────────────────────────────┐
│ ← FinMate · Pre-Market Outlook                     │
├────────────────────────────────────────────────────┤
│                                                    │
│         HBL                          ▲ STRONG BUY  │
│         PKR 282.87   +0.36%   confidence: HIGH     │
│                                                    │
│  ┌──── Your position (POSITION_ALERT only) ────┐   │
│  │ Quantity      Avg buy       P&L              │   │
│  │ 50            PKR 510.00   −4.83%            │   │
│  └─────────────────────────────────────────────┘   │
│                                                    │
│  ┌──── Why this signal ────────────────────────┐   │
│  │  HBL is showing strong upward momentum…     │   │
│  │  (4-5 sentence Gemini-generated summary)    │   │
│  └─────────────────────────────────────────────┘   │
│                                                    │
│  ┌──── Technicals ──────────────────────────────┐  │
│  │  RSI 14   56.4    MA 50    275.12            │  │
│  │  MA 200  260.45   Volatility   2.1%          │  │
│  └─────────────────────────────────────────────┘   │
│                                                    │
│  ┌──── Recent news ───────────────────────────┐    │
│  │  ▸ HBL profit jumps 24% …    Dawn   GOOD    │   │
│  │  ▸ Banking sector outlook…   BR   NEUTRAL   │   │
│  └────────────────────────────────────────────┘    │
│                                                    │
│  Don't understand a number? Read the guide →       │
└────────────────────────────────────────────────────┘
```

Render order:
1. Header: `ticker` + signal badge (colour from `signal`)
2. Price strip: `close`, `change_pct`, `confidence`
3. **Position card** (only if `type=POSITION_ALERT`) — qty / avg / P&L
4. Summary paragraph (`summary`)
5. Technicals 4-cell grid
6. News list (clickable links)
7. Footer with docs link

### Detail view — DIGEST

```
┌────────────────────────────────────────────────────┐
│ ← FinMate · Today's Top Performers · 12 stocks     │
├────────────────────────────────────────────────────┤
│                                                    │
│   Ticker   Price    Change    RSI    Note          │
│   ─────────────────────────────────────────────    │
│   OGDC     306.75   +1.18%    65.1   Energy sector │
│                                       picking up…  │
│                                                    │
│   ZTL       19.39   +8.20%    71.8   Strong volume │
│                                       breakout…    │
│                                                    │
│   LUCK     408.20   +0.78%    58.4   Cement uptick │
│                                       continues    │
│                                                    │
│   …                                                │
│                                                    │
│  (Each row tappable → opens detail for that stock) │
└────────────────────────────────────────────────────┘
```

Render: iterate `payload.tickers[]`, one row each. Optionally each row tappable to open the detail view for that ticker.

---

## 6. Edge cases & gotchas

### Duplicate notifications per channel

Current workflows create **one full chain** (alert + alert_detail + notification + alert_log) **per channel send**. So a user with both email and Slack enabled gets:
- 2 `alert` rows (different ids)
- 2 `alert_detail` rows
- 2 `notification` rows
- 2 `alert_log` rows

The frontend feed will show **2 entries** for the same event. To dedupe, group by `(ticker, alert_window, date_trunc('hour', created_at))`:

```sql
SELECT DISTINCT ON (a.ticker, a.alert_window, date_trunc('hour', n.created_at))
       n.*, a.ticker, a.signal, a.reason
FROM notification n
JOIN alert a ON a.id = n.alert_id
WHERE n.user_id = $me
ORDER BY a.ticker, a.alert_window, date_trunc('hour', n.created_at), n.created_at DESC;
```

v1.1 plan: refactor n8n to create one `alert` per user×ticker×window, then fan out channels — fixes this at the source.

### Unread count

```sql
SELECT COUNT(*) FROM notification WHERE user_id = $me AND read_at IS NULL;
```

Postgrest: `GET /notification?user_id=eq.X&read_at=is.null&select=id` + `Prefer: count=exact` header.

### Real-time updates

Supabase has Realtime — subscribe to `notification` table:

```js
supabase
  .channel('notifications-' + userId)
  .on('postgres_changes', {
    event: 'INSERT',
    schema: 'public',
    table: 'notification',
    filter: `user_id=eq.${userId}`,
  }, payload => {
    // new row arrived → animate badge, toast, etc.
  })
  .subscribe();
```

Saves polling — when n8n inserts a new notification, the app gets it within ~1 sec.

### Pagination

Use cursor on `created_at`:

```
GET /notification?user_id=eq.<me>&created_at=lt.<oldest_seen>&order=created_at.desc&limit=20
```

### Old notifications

No retention policy on `notification` yet. Add at the app level: "show last 30 days" filter, or run a SQL cron in Supabase to delete `WHERE created_at < now() - interval '90 days'` periodically.

---

## 7. Cross-references

- [alert.md](alert.md) — workflow setup, env vars, troubleshooting matrix
- [workflow_a_strong_signals.json](workflow_a_strong_signals.json) — Top Pick + Digest n8n workflow
- [workflow_b_portfolio_alerts.json](workflow_b_portfolio_alerts.json) — Portfolio alerts n8n workflow
- [`alerts/models.py`](../alerts/models.py) — Django source of truth for the schema
- [`alerts/migrations/0003_notification_alertdetail.py`](../alerts/migrations/0003_notification_alertdetail.py) — the migration that creates these tables
