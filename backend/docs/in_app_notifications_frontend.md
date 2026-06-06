# In-App Notifications — Frontend Integration Guide

This doc tells the frontend dev exactly which endpoints to hit, how
to poll, what shapes come back, and how to render notifications in
the mobile app's bell-icon feed.

## What gets a notification

Every alert dispatch run (09:00 / 12:00 / 18:40 PKT) writes one
`Notification` row per eligible user. Three types:

| `type`           | When fired                                  | What the user sees |
| ---------------- | ------------------------------------------- | ------------------ |
| `TOP_PICK`       | once per window — single best `STRONG_BUY`  | Detailed card with AI-written prose, RSI / MA / vol, recent news |
| `DIGEST`         | once per window, ~2 min after `TOP_PICK`    | Table of the next 20 strong-buys with one-line summaries |
| `POSITION_ALERT` | once per holding with a `SELL`/`STRONG_SELL` signal | Personalised card with the user's qty, avg buy, current P&L |

`category` is either `"stock"` (TOP_PICK + POSITION_ALERT) or
`"digest"` (DIGEST) — use it for tab filtering if the UI splits
notifications into "Picks" vs "Digests".

### How to tell which notification is which

Use the `type` field FIRST. The `ticker` field is only meaningful
for TOP_PICK and POSITION_ALERT — for a DIGEST it's the literal
string `"DIGEST"` because the notification covers many stocks. The
actual list of tickers is in `alert.symbols` (array) for the digest
row.

```javascript
if (notif.type === 'DIGEST') {
  // alert.ticker === 'DIGEST'
  // alert.symbols === ['HBL', 'OGDC', 'MCB', ...]
  // payload.tickers === [{ticker, close, change_pct, ...}, ...]  ← rich shape
  renderDigestCard(notif);
} else if (notif.type === 'TOP_PICK') {
  // alert.ticker === 'HBL'
  // payload === { ticker, close, news, summary, ... }
  renderTopPickCard(notif);
} else if (notif.type === 'POSITION_ALERT') {
  // alert.ticker === 'HBL'  (the stock the user holds)
  // payload === { qty, avg_buy, pnl_pct, ... }
  renderPositionCard(notif);
}
```

## Endpoints

All endpoints are under `/api/alerts/` and require the user's JWT
in `Authorization: Bearer <token>`.

### 1. Unread-count badge

```
GET  /api/alerts/notifications/unread-count/
→ 200 { "count": 3 }
```

Poll this every **30 seconds** while the app is in the foreground,
and **on tab/window focus**, to drive the red dot on the bell icon.
It's a single `COUNT(*) WHERE read_at IS NULL` — cheap.

### 2. Notification feed (list)

```
GET  /api/alerts/notifications/                      → all notifications
GET  /api/alerts/notifications/?unread=true          → unread only
→ 200 [
    {
      "id": "f9a3d4e8-1b21-4cf6-aeac-9d6f7c0b1e23",
      "type": "TOP_PICK",
      "category": "stock",
      "read_at": null,
      "created_at": "2026-05-26T04:00:12Z",
      "ticker": "HBL",
      "signal": "BUY",
      "alert_window": "PRE_MARKET",
      "reason": "HBL is showing a STRONG BUY at PKR 312.50..."
    },
    ...
  ]
```

The row carries enough for a feed snippet: ticker, signal, the first
line of `reason`, and `created_at`. Don't show the full `reason` here;
it's truncated to ~150 chars in your UI then "Tap to read more".

Sort comes pre-applied (newest first).

### 3. Notification detail (rich card)

```
GET  /api/alerts/notifications/<uuid>/detail/
→ 200 {
    "id": "f9a3d4e8-1b21-4cf6-aeac-9d6f7c0b1e23",
    "type": "TOP_PICK",
    "category": "stock",
    "read_at": null,
    "alert": {
      "id": "...",
      "ticker": "HBL",
      "symbols": ["HBL"],
      "signal": "BUY",
      "alert_window": "PRE_MARKET",
      "reason": "...",
      "created_at": "2026-05-26T04:00:12Z"
    },
    "payload": {
      "ticker": "HBL",
      "signal": "STRONG_BUY",
      "confidence": "HIGH",
      "close": 312.5,
      "change_pct": 1.42,
      "rsi14": 58.7,
      "ma50": 305.2,
      "ma200": 289.0,
      "volatility20d": 0.022,
      "news": [
        {
          "headline": "HBL posts record Q1 profit",
          "link": "https://...",
          "source": "Dawn",
          "sentiment": "EXCELLENT"
        }
      ],
      "summary": "HBL is showing a STRONG BUY at PKR 312.50...",
      "window_label": "Pre-Market Outlook",
      "type": "TOP_PICK"
    }
  }
```

This is the source of truth for the rich detail card. The `payload`
shape varies by `type`:

#### TOP_PICK payload
```
{ ticker, signal, confidence, close, change_pct, rsi14, ma50, ma200,
  volatility20d, news: [...], summary, window_label, type: "TOP_PICK" }
```

#### DIGEST payload
```
{
  tickers: [
    { ticker, close, change_pct, rsi14, summary },
    ...up to 20 entries
  ],
  count: 14,
  window_label: "Pre-Market Outlook",
  type: "DIGEST"
}
```

#### POSITION_ALERT payload
```
{ ticker, signal, confidence,
  qty,                   // user's holding
  avg_buy,               // user's average buy price
  current,               // current close
  pnl_pct, pnl_pkr,      // unrealised P&L
  close, change_pct, rsi14, ma50, ma200, volatility20d,
  news: [...], summary, window_label, type: "POSITION_ALERT" }
```

### 4. Mark one notification read

```
PATCH /api/alerts/notifications/<uuid>/read/
→ 200 (the updated notification row, with `read_at` set)
```

Call this when:
- The user **opens the detail card** (so it's no longer "new"), or
- They swipe to dismiss it from the feed.

Idempotent — calling it twice doesn't toggle, it just sets `read_at`
once on the first call.

### 5. Mark all read

```
POST  /api/alerts/notifications/mark-all-read/
→ 200 { "marked": 3 }
```

Wire this to a "Clear all" button on the notification feed screen.
Returns how many rows got flipped.

### 6. Bonus — Notification preferences

```
GET    /api/alerts/preferences/        → current prefs
PATCH  /api/alerts/preferences/        → update (body matches GET shape)
→ {
    "id": "...",
    "in_app_enabled": true,
    "email_enabled": true,
    "whatsapp_enabled": false,
    "slack_enabled": false,
    "pre_market": true,
    "mid_session": true,
    "post_market": true
  }
```

The settings screen edits these. **`in_app_enabled = false` does not
silence the bell** — we always write the Notification row so it shows
up in the feed even if the user opted out of pushes. (If you want
true muting, gate Notification creation server-side too; ask the
backend team.)

## Recommended polling cadence (mobile app)

```
on app foreground / tab focus:
    GET /unread-count

every 30 s while foregrounded:
    GET /unread-count

when user opens the notification panel:
    GET /notifications/?unread=true

when user taps a notification row:
    GET /notifications/<id>/detail/
    (and concurrently) PATCH /notifications/<id>/read/
```

That's ~120 requests/user/hour while active, each ~5ms — well within
Supabase free-tier and the Django Cloud Run footprint.

## Notes & gotchas

- **All ids are UUIDs** (e.g. `f9a3d4e8-...`). Pass them verbatim in
  the URL; don't try to parse them as integers.
- **`alert_window`** is one of `"PRE_MARKET" | "MID_SESSION" | "POST_MARKET"` —
  useful for grouping notifications by time-of-day in the feed UI.
- **`signal`** in the Alert row is the 3-class label `BUY | HOLD | SELL`.
  The full label (`STRONG_BUY` etc) lives inside `payload.signal`.
- **DIGEST notifications** are intentionally created once per user per
  window. If you see 1 DIGEST + 14 TOP_PICK-like rows in the feed, the
  digest is the *combined* one, and the 14 are separate per-ticker
  notifications you should expect from Workflow B if the user holds
  any of them.
- **`read_at`** is the timestamp the row was last marked read. Use
  `read_at IS NULL` as "unread" — the field is null until the user
  opens or dismisses.

## Quick UX summary

| User action | Frontend call(s) |
| ----------- | ---------------- |
| App opened  | `GET /unread-count` |
| Background poll (30 s) | `GET /unread-count` |
| Tap bell icon | `GET /notifications/` |
| Tap a notification row | `GET /notifications/<id>/detail/` + `PATCH /<id>/read/` |
| Tap "Clear all" | `POST /mark-all-read/` |
| Change which alerts you get | `PATCH /preferences/` |
