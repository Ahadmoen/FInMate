# Notification Examples — what users actually see

Sample messages each Gemini call produces with the v1.1 prompts.
Real PSX tickers, realistic data ranges. Shows the **input** the LLM
gets and the **output** that lands in `alert.reason` /
`alert_detail.payload.summary`.

---

## 1. Top Pick (Workflow A — first message of the cron)

**Type**: `TOP_PICK`  ·  **Category**: `stock`  ·  **Alert ticker**: `HBL`

### Data fed to Gemini

```
Stock: HBL
Signal: STRONG BUY (confidence: HIGH)
Health label: GOOD
Directional horizon: 5d
Blended score: 0.42
Signal strength: 0.42
Forecast signed score: 0.39
Reason: Primary driver: Forecast. Forecast weight 50%, Sentiment weight 30%, Technicals weight 20%.
Dominant news sentiment: GOOD
Contributions: {"Forecast": 64.2, "Sentiment": 22.1, "Technicals": 13.7}

Current: close = 282.87, change = 0.36%, RSI14 = 56.4, MA20 = 278.55,
MA50 = 275.12, MA200 = 260.45, volatility20d = 0.021,
volume_ratio = 1.4, EPS = 32.5.

Top news headlines:
- HBL profit jumps 24% on higher net interest income
- Banking sector outlook stable for Q2 FY26
```

### LLM output (the `summary` field)

> HBL is set up for a strong move higher today — our models are calling a high-confidence STRONG BUY at PKR 282.87, up 0.36% pre-market. The technicals back this up: RSI at 56 sits in healthy bullish territory without being overbought, and the price is trading 3% above its 50-day average and nearly 9% above the 200-day — the long-term trend is firmly up. Volume is running at 1.4× the 20-day average, which means real buying interest is showing up, not just price drift. The recent profit-jump headline aligns with this bullish read, and our news sentiment scoring lands on GOOD. Our forecast model carries about 64% of the signal weight with sentiment adding another 22%, and both point the same direction. This is one of the cleanest setups on PSX today.

### How it lands in the inbox (HTML email)

```
┌────────────────────────────────────────────────────────────────────┐
│  FinMate                              TOP PICK · PRE-MARKET OUTLOOK│
├────────────────────────────────────────────────────────────────────┤
│  ┌─ Today's top pick — our highest-confidence STRONG BUY across   │
│  │  the market.                                                   │
│  └─────────────────                                                │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  HBL                                       ▲ STRONG BUY     │  │
│  │  PKR 282.87 · +0.36% · confidence: HIGH                     │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  HBL is set up for a strong move higher today — our models are    │
│  calling a high-confidence STRONG BUY at PKR 282.87, up 0.36%     │
│  pre-market. The technicals back this up: RSI at 56 sits in       │
│  healthy bullish territory without being overbought, and the      │
│  price is trading 3% above its 50-day average and nearly 9%       │
│  above the 200-day — the long-term trend is firmly up. Volume     │
│  is running at 1.4× the 20-day average, which means real buying   │
│  interest is showing up, not just price drift. The recent profit- │
│  jump headline aligns with this bullish read, and our news        │
│  sentiment scoring lands on GOOD. Our forecast model carries      │
│  about 64% of the signal weight with sentiment adding another     │
│  22%, and both point the same direction. This is one of the       │
│  cleanest setups on PSX today.                                    │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ RSI 14    56.4    MA 50    275.12                            │  │
│  │ MA 200    260.45  Volatility 2.1%                            │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  RECENT NEWS                                                       │
│   ▸ HBL profit jumps 24% on higher net interest income            │
│       · Dawn · GOOD                                                │
│   ▸ Banking sector outlook stable for Q2 FY26                     │
│       · Business Recorder · NEUTRAL                                │
│                                                                    │
│  Don't understand a number? Read the guide →                      │
│  Sent by FinMate · 09:00 PKT · Pre-Market Outlook                 │
└────────────────────────────────────────────────────────────────────┘
```

### Slack rendering (Block Kit)

```
▌ HBL ▲ STRONG BUY
▌
▌ *PKR 282.87*  ·  +0.36%  ·  confidence: *HIGH*
▌
▌ HBL is set up for a strong move higher today — our models are
▌ calling a high-confidence STRONG BUY at PKR 282.87…
▌
▌ RSI 56.4 · MA50 275.12 · MA200 260.45 · Vol 2.1%
▌
▌ *Recent news*
▌ • HBL profit jumps 24% on higher net interest income  (Dawn)
▌ • Banking sector outlook stable for Q2 FY26  (Business Recorder)
▌
▌ Read the guide →  ·  FinMate Pre-Market Outlook
```

---

## 2. Position Alert (Workflow B)

**Type**: `POSITION_ALERT`  ·  **Category**: `stock`  ·  **Alert ticker**: `ENGRO`
The user holds **50 shares of ENGRO at avg PKR 510**.

### Data fed to Gemini

```
User HOLDS: ENGRO
Signal: STRONG_SELL (confidence: HIGH)
Health: BAD
Horizon: 5d
Reason: Primary driver: Forecast. Forecast weight 60%, Sentiment weight 20%, Technicals weight 20%.
Dominant news sentiment: BAD
Contributions: {"Forecast": 71.4, "Sentiment": 15.2, "Technicals": 13.4}

Current: close = 485.38, change = -1.12%, RSI14 = 32.4, MA20 = 502.10,
MA50 = 495.20, MA200 = 530.10, volatility20d = 0.035,
volume_ratio = 1.8, EPS = 28.9.

Top news:
- ENGRO faces pricing pressure as gas tariff hike impacts fertilizer margin
- Chemical sector under stress amid weak demand outlook
```

The holder's position (computed in the workflow, not in the prompt):
- Quantity: 50
- Avg buy: PKR 510.00
- Current: PKR 485.38
- Unrealised P&L: −4.83% (−PKR 1,231)

### LLM output

> ENGRO has shifted into a clear sell zone for your position — our models recommend STRONG SELL at HIGH confidence, with the stock at PKR 485.38, down 1.12% today and your position now sitting on a 4.83% unrealised loss (about PKR 1,231 against your 510 average buy). RSI at 32 is firmly in oversold-but-still-falling territory, and the price has broken below both its 50-day (495.20) and 200-day (530.10) averages — the trend has flipped negative across both timeframes. Volume is elevated at 1.8× the 20-day average, meaning the move down has real conviction behind it, not just drift. Recent news flow is aligned: pricing pressure on the fertilizer side from the gas tariff hike, plus a weak chemical sector demand outlook. Forecast is carrying 71% of the bearish weight with news sentiment confirming. Exit the position now to lock in the current price before further downside; reconsider re-entering if the price stabilizes back above MA50.

### How it lands in the inbox

```
┌────────────────────────────────────────────────────────────────────┐
│  FinMate                         YOUR PORTFOLIO · PRE-MARKET OUTLOOK│
├────────────────────────────────────────────────────────────────────┤
│  ┌─ Position alert — you hold this stock and our models           │
│  │  recommend strong sell.                                        │
│  └─────────────────                                                │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  ENGRO                                     ▼ STRONG SELL   │  │
│  │  PKR 485.38 · −1.12% today · confidence: HIGH              │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │             ── YOUR POSITION ──                              │  │
│  │  Quantity  50           Avg buy price  PKR 510.00            │  │
│  │  Unrealised P&L  −4.83%  P&L in PKR    −1,231.00             │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ENGRO has shifted into a clear sell zone for your position —     │
│  our models recommend STRONG SELL at HIGH confidence, with the    │
│  stock at PKR 485.38, down 1.12% today and your position now      │
│  sitting on a 4.83% unrealised loss (about PKR 1,231 against      │
│  your 510 average buy). RSI at 32 is firmly in oversold-but-      │
│  still-falling territory, and the price has broken below both     │
│  its 50-day (495.20) and 200-day (530.10) averages — the trend    │
│  has flipped negative across both timeframes. Volume is elevated  │
│  at 1.8× the 20-day average, meaning the move down has real       │
│  conviction behind it, not just drift. Recent news flow is        │
│  aligned: pricing pressure on the fertilizer side from the gas    │
│  tariff hike, plus a weak chemical sector demand outlook.         │
│  Forecast is carrying 71% of the bearish weight with news         │
│  sentiment confirming. Exit the position now to lock in the       │
│  current price before further downside; reconsider re-entering    │
│  if the price stabilizes back above MA50.                         │
│                                                                    │
│  RSI 14   32.4    MA 50     495.20                                │
│  MA 200   530.10  Volatility 3.5%                                 │
│                                                                    │
│  RECENT NEWS                                                       │
│   ▸ ENGRO faces pricing pressure as gas tariff hike impacts…       │
│       · Dawn · BAD                                                 │
│   ▸ Chemical sector under stress amid weak demand outlook         │
│       · Business Recorder · BAD                                    │
│                                                                    │
│  Don't understand a number? Read the guide →                      │
│  Sent by FinMate · 09:00 PKT · Pre-Market Outlook                 │
└────────────────────────────────────────────────────────────────────┘
```

---

## 3. Digest (Workflow A — second message, 2 min after Top Pick)

**Type**: `DIGEST`  ·  **Category**: `digest`  ·  **Alert ticker**: `'DIGEST'`

Single message with a table of every other STRONG_BUY (top pick excluded).

### Data fed to Gemini (batch one-liner call)

```
OGDC: rsi=68.1, ma50=298.40, ma200=275.50, close=306.75, change_pct=1.18, health=GOOD
ZTL:  rsi=71.8, ma50=17.92,  ma200=15.45,  close=19.39,  change_pct=8.20, health=EXCELLENT
LUCK: rsi=58.4, ma50=392.10, ma200=378.20, close=408.20, change_pct=0.78, health=GOOD
TRG:  rsi=55.2, ma50=51.40,  ma200=48.90,  close=53.23,  change_pct=1.80, health=GOOD
MCB:  rsi=62.8, ma50=388.00, ma200=370.50, close=401.78, change_pct=1.89, health=GOOD
… (10+ more tickers)
```

### LLM output (JSON map)

```json
{
  "OGDC": "Energy sector breaking out with RSI strong at 68 and volume support.",
  "ZTL":  "Sharp volume breakout above 200-day average with RSI building room.",
  "LUCK": "Cement uptrend continuing with price 4% above MA50 and momentum healthy.",
  "TRG":  "Tech recovering above key averages with RSI in healthy bullish zone.",
  "MCB":  "Banking strength continues, price 3% above MA50 with steady volume."
}
```

### How it lands in the inbox

```
┌────────────────────────────────────────────────────────────────────┐
│  FinMate                  OTHER TOP PERFORMERS · PRE-MARKET OUTLOOK│
├────────────────────────────────────────────────────────────────────┤
│  12 more strong-buy moves on PSX today:                           │
│                                                                    │
│  ┌────────┬──────────┬──────────┬─────┬─────────────────────────┐  │
│  │ Ticker │  Price   │  Change  │ RSI │  Note                   │  │
│  ├────────┼──────────┼──────────┼─────┼─────────────────────────┤  │
│  │ OGDC   │  306.75  │  +1.18%  │ 68  │ Energy sector breaking  │  │
│  │        │          │          │     │ out with RSI strong…    │  │
│  │ ZTL    │   19.39  │  +8.20%  │ 72  │ Sharp volume breakout   │  │
│  │        │          │          │     │ above 200-day average…  │  │
│  │ LUCK   │  408.20  │  +0.78%  │ 58  │ Cement uptrend          │  │
│  │        │          │          │     │ continuing with price…  │  │
│  │ TRG    │   53.23  │  +1.80%  │ 55  │ Tech recovering above   │  │
│  │        │          │          │     │ key averages…           │  │
│  │ MCB    │  401.78  │  +1.89%  │ 63  │ Banking strength        │  │
│  │        │          │          │     │ continues, price 3%…    │  │
│  │ … (7 more rows) ………………………………………………………………………………………………………… │  │
│  └────────┴──────────┴──────────┴─────┴─────────────────────────┘  │
│                                                                    │
│  Don't understand a number? Read the guide →                      │
│  Sent by FinMate · 09:02 PKT · Pre-Market Outlook                 │
└────────────────────────────────────────────────────────────────────┘
```

---

## What changed from the v1.0 prompts

Compare an older v1.0 Top Pick output with the v1.1 example above:

**v1.0 (old)** — hedge-heavy, vague:
> Hey there! We've issued a STRONG BUY signal for HBL today. The stock looks well-positioned with positive sentiment and good technicals. *The main risk to watch is broader market volatility and any negative news from the banking sector.*

**v1.1 (new)** — confident, specific, no hedging:
> HBL is set up for a strong move higher today — our models are calling a high-confidence STRONG BUY at PKR 282.87, up 0.36% pre-market. The technicals back this up: RSI at 56 sits in healthy bullish territory without being overbought, and the price is trading 3% above its 50-day average and nearly 9% above the 200-day — the long-term trend is firmly up…

Specifics weave in (RSI level, MA distances, volume ratio, EPS, contribution %s) and the closing line is a confident summary, not a risk disclaimer.

---

## How the prompt enforces it

System prompt now explicitly forbids:

- ❌ "consult an advisor"
- ❌ "this is not financial advice"
- ❌ "the main risk to watch"
- ❌ Any hedging or risk-warning closing lines

And it requires:

- ✅ Specific numbers from the data woven into the prose
- ✅ Confident, direct tone
- ✅ 5–7 sentences
- ✅ A practical closing statement (not a disclaimer)
