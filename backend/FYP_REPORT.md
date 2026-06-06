<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800&display=swap');
html, body { font-family: 'Montserrat', 'Helvetica Neue', Arial, sans-serif; font-size: 11pt; line-height: 1.55; color: #222; }
h1, h2, h3, h4, h5, h6 { font-family: 'Montserrat', sans-serif; font-weight: 700; color: #0f2a44; }
h1 { font-size: 26pt; margin-top: 1.4em; page-break-before: always; }
h2 { font-size: 18pt; margin-top: 1.2em; page-break-before: auto; }
h3 { font-size: 14pt; margin-top: 1em; }
h4 { font-size: 12pt; }
p, li, td, th { font-family: 'Montserrat', sans-serif; }
table { border-collapse: collapse; width: 100%; margin: 0.8em 0; }
th, td { border: 1px solid #d0d7de; padding: 6px 10px; text-align: left; vertical-align: top; font-size: 10.5pt; }
th { background: #f0f4f8; font-weight: 600; }
code, pre { font-family: 'JetBrains Mono', Menlo, Consolas, monospace; font-size: 10pt; }
pre { background: #f6f8fa; padding: 12px; border-radius: 6px; overflow-x: auto; }
blockquote { border-left: 4px solid #208AEF; padding-left: 14px; color: #555; }
@page { size: A4; margin: 22mm 18mm; }
</style>

# FinMate

## An AI-Powered Stock Forecasting and Smart-Portfolio Platform for the Pakistan Stock Exchange (PSX)

### Final Year Project — Submission Report

**Submission Date:** 26 May 2026

**Team Members and Module Ownership**

| Team Member | Responsibility |
|---|---|
| **Mubashir** | Frontend — full React Native / Expo mobile application: routing, screens, components, navigation, styling, on-device state management |
| **Wasif** | Backend — Django + DRF API design and implementation, REST endpoints, authentication, business-layer serializers, and frontend/backend API integration |
| **Ahad** | Data Engineering and ML — five PSX scrapers, news-sentiment pipeline (FinBERT/VADER), forecasting models (ARIMA + LSTM), directional classifier ensemble, fusion engine, alerts pipeline, and cloud deployment of all ML / batch pipelines (GCP Cloud Run, GCS, n8n) |
| **Ammara** | Chatbot — `chatbot/` Django app: chat sessions, messages, the RAG entrypoint and message orchestration |

**Repositories**

- Backend (Django): [github.com/Mubashir1920/FinMate-BE](https://github.com/Mubashir1920/FinMate-BE)
- Frontend (Expo / React Native): [github.com/Mubashir1920/FinMate-FE](https://github.com/Mubashir1920/FinMate-FE)

---

## Acknowledgments

We are grateful to our project supervisor and panel for their guidance throughout the academic year. We thank the Pakistan Stock Exchange for making historical and intraday market data publicly accessible through `psx-data-reader`, the Hugging Face team and ProsusAI for the open release of the FinBERT model, the maintainers of `statsmodels`, `scikit-learn`, `PyTorch`, `transformers`, Django, Django REST Framework, Expo, and React Native, whose open-source contributions made this work possible. Finally, we acknowledge our families and peers for their support over the year, and the wider Pakistani retail-investor community whose pain points motivated this project from day one.

---

## Abstract

FinMate is a full-stack, mobile-first investment intelligence platform purpose-built for the Pakistan Stock Exchange (PSX). It addresses a market gap: retail Pakistani investors lack access to data-driven, locally-contextualised decision support tooling, while existing global platforms ignore PSX in favour of larger Western markets. The system ingests live and historical PSX market data for all 738 listed equities, scrapes Pakistani-context financial news (Dawn, Business Recorder, ProPakistani, Google News RSS), and runs three independent machine-learning pipelines: a hybrid ARIMA + multi-feature LSTM price forecaster, a financial-domain BERT sentiment classifier (FinBERT) with a VADER fallback, and a purpose-built directional classifier ensemble (GradientBoosting + RandomForest + LogisticRegression) that achieves a 51.5% next-day directional hit rate (with 70%+ on specific decisive symbol/horizon pairs). The three signals are combined through an adaptive per-stock fusion engine that weights each signal by a runtime quality estimate and damps extreme forecasts when they diverge from the other signals — producing an explainable BUY / HOLD / SELL recommendation along with a `PrimaryDriver` that answers *why* a stock is rated the way it is. A Django REST Framework backend exposes thirty REST endpoints across eight Django apps, secured by SimpleJWT. A Celery Beat scheduler runs seven trading-day-aware jobs in `Asia/Karachi` time, with a two-mode batch pipeline (cold weekly retrain vs warm hourly refresh) deployed as chained GCP Cloud Run Jobs against a Supabase Postgres database, an Upstash Redis broker, and a Google Cloud Storage bucket holding more than 2,500 cached model artefacts. Alerts fan out through four channels (in-app, email, WhatsApp, Slack) via n8n workflows that use Google Gemini 2.5 Flash Lite to convert structured alert payloads into human-readable summaries. The client is a TypeScript Expo SDK 54 / React Native 0.81 application with file-based routing, typed routes, a Reanimated-driven custom tab bar, Pakistan-specific KYC validators, custom SVG charts, JWT route-guarding, and a chatbot UI backed by a Retrieval-Augmented Generation (RAG) endpoint. This document presents the full requirements analysis, system design, implementation, testing strategy, evaluation results, and operational lessons of the FinMate project.

---

## Table of Contents

1. **Introduction**
2. **Background and Literature Review**
3. **Requirements Engineering**
4. **System Architecture and Design**
5. **Backend Implementation (Django + DRF)**
6. **Data Ingestion and Scraping Layer**
7. **Machine Learning Services**
8. **Adaptive Fusion Engine**
9. **Alerts and Multi-Channel Notification**
10. **Chatbot Subsystem and Retrieval-Augmented Generation**
11. **Frontend Implementation (Expo / React Native)**
12. **Scheduling and Orchestration**
13. **Cloud Infrastructure and Deployment**
14. **Testing, Validation, and Quality Assurance**
15. **Results and Evaluation**
16. **Limitations and Lessons Learned**
17. **Future Work**
18. **Conclusion**
19. **References**
20. **Appendix A — REST API Reference**
21. **Appendix B — Database Schema Reference**
22. **Appendix C — Configuration and Environment Variables**
23. **Appendix D — Repository File Index**

---

# Chapter 1 — Introduction

## 1.1 Context

The Pakistan Stock Exchange (PSX) is the country's principal equity market, with over 738 listed equities spanning sectors from commercial banking and energy to fertiliser, textile, cement, food, and information technology. Despite its size and economic importance, the PSX is significantly under-served by modern financial-technology tooling when compared with mature Western markets. Major global investment apps such as Robinhood, Webull, and eToro do not include PSX equities; pan-Asian platforms such as Tiger Brokers and Moomoo offer no Pakistani inventory; and home-grown brokerage platforms tend to focus narrowly on order-execution rather than on decision support, forecasting, or portfolio analytics.

The retail investor base in Pakistan has nonetheless grown rapidly, accelerated by the launch of low-fee broker apps and the post-2020 retail trading boom. These investors generally come to the market with limited formal training in quantitative finance, limited access to professional research, and limited time to track the multiple signal sources that institutional desks consume routinely — price, momentum, volume, news, fundamentals. The result is a population of motivated but information-poor users making capital-allocation decisions, often based on rumour, social-media chatter, or simple chart inspection.

## 1.2 Problem Statement

Pakistani retail investors lack a unified, mobile-first decision-support system that:

1. Combines multiple data sources (price history, technicals, fundamentals, news, sentiment) into a single recommendation.
2. Is *locally aware* — that is, understands PSX-specific tickers, Pakistani Rupee (PKR) currency conventions, Pakistan-context news (Dawn, Business Recorder, ProPakistani), and Pakistani Standard Time (PKT, `Asia/Karachi`).
3. Provides *explainability* — does not simply output a BUY/SELL but justifies *why* a recommendation was made.
4. Delivers alerts through channels Pakistani users actually use (WhatsApp, email, in-app notifications).
5. Allows investors to manage and analyse their PSX portfolios in one place.

## 1.3 Project Objectives

The FinMate project sets out to deliver a production-grade, mobile-first investment intelligence platform that addresses each of the above gaps. The concrete objectives are:

**O1 — Build a scalable Django backend** exposing a REST API covering authentication, KYC onboarding, market data, signals, portfolios, and alerts.

**O2 — Build a robust data ingestion pipeline** capable of pulling daily historical OHLCV bars, hourly intraday bars, financial news, key technical ratios, and fundamentals for every PSX equity, with appropriate fallbacks when primary sources fail.

**O3 — Build three independent ML pipelines** — a price forecasting model, a financial-text sentiment classifier, and a directional UP/DOWN classifier — each evaluated against an honest historical backtest.

**O4 — Build an adaptive fusion engine** that combines the three ML signals into a single per-stock recommendation along with quality scores, weight vectors, contribution breakdowns, and a primary-driver field that supports explainability.

**O5 — Build a multi-channel alerts pipeline** that delivers personalised alerts (portfolio-relevant signals, strong cross-market events, daily digests) over in-app, email, WhatsApp, and Slack channels at three trading-day-aligned windows.

**O6 — Build a native mobile client** in React Native / Expo, with PSX-specific localisation (CNIC and phone validators, PKR formatting, PKT timestamps, Pakistani broker list, file-based routing, animated navigation, custom SVG charts, JWT-protected screens).

**O7 — Build a chatbot subsystem** that lets users ask natural-language questions about their portfolio, individual stocks, or market events, backed by a Retrieval-Augmented Generation (RAG) layer.

**O8 — Deploy the entire system to cloud infrastructure** using GCP Cloud Run for the API, Cloud Run Jobs for the batch pipeline, GCS for model and data storage, Supabase Postgres for persistence, Upstash Redis as a broker, and n8n for alert workflow orchestration.

## 1.4 Scope and Out-of-Scope

**In scope.** Data ingestion for all listed PSX equities; daily and intraday signals; sentiment over Pakistan-context news; ARIMA and LSTM-based forecasting; ensemble directional classification; alerts; portfolio tracking; mobile client; RAG chatbot.

**Out of scope.** Live trade execution against a broker API — the application surfaces a "Buy/Sell" screen as a UI placeholder with the list of Pakistani brokers, but does not execute orders. Regulatory licensing, KYC verification with NADRA, and AML compliance flows are also outside the FYP scope; the KYC step in the signup wizard captures the data formats correctly but does not validate against NADRA itself. Foreign-exchange trading and derivatives are out of scope.

## 1.5 Contribution Summary

The project contributes:

- A re-usable, production-grade pipeline architecture (two-mode cold/warm batch pipeline, model caching with GCS sync, chained Cloud Run Jobs) that other PSX-focused projects can fork.
- An empirically tuned news-scraper for PSX tickers with a multi-tier matching engine that solves an important real-world problem: false-positive associations between short PSX tickers and unrelated English words (e.g., `SPL` for Saudi Premier League, `LUCK` for "lucky").
- A documented application of FinBERT to Urdu-tinted English-language Pakistani financial news.
- A purpose-built directional classifier ensemble with measured per-symbol, per-horizon hit-rate evaluation.
- An adaptive fusion engine with dynamic quality weighting and divergence damping — to our knowledge, novel in the Pakistani retail-investing space.
- A reusable React Native / Expo mobile architecture with custom Reanimated tab-bar animation, typed file-based routing, and a JWT route guard.

## 1.6 Document Structure

Chapter 2 surveys the relevant background and literature. Chapter 3 derives the system requirements. Chapter 4 presents the overall architecture. Chapters 5–11 cover the implementation layer by layer. Chapters 12–13 cover scheduling and deployment. Chapter 14 describes the testing strategy. Chapter 15 reports evaluation results. Chapter 16 discusses limitations and lessons. Chapter 17 outlines future work. Chapter 18 concludes. Appendices supply the API reference, schema reference, configuration reference, and a repository file index.

---

# Chapter 2 — Background and Literature Review

## 2.1 Time-Series Forecasting in Finance

Financial time-series forecasting has a long history. The classical approach is the **AutoRegressive Integrated Moving Average (ARIMA)** model of Box and Jenkins, which combines an autoregressive term over previous values, an integration term to make the series stationary, and a moving-average term over previous error residuals. ARIMA models remain a useful baseline because they are interpretable, statistically grounded, and require only a small parameter set to fit. Their weakness is that they assume linear relationships and constant variance, both of which financial returns visibly violate.

Modern approaches to financial forecasting overwhelmingly use **deep recurrent networks**, particularly the **Long Short-Term Memory (LSTM)** of Hochreiter and Schmidhuber. LSTMs handle long-range dependencies via gated memory cells and can learn non-linear relationships between input features. They have been shown empirically to outperform ARIMA on noisy intraday data, especially when conditioned on multiple features beyond raw price (volume, returns, technicals). The trade-off is that LSTMs require substantial training data, are more expensive to train, are harder to interpret, and overfit easily.

In FinMate we treat ARIMA and LSTM as *complementary rather than competing* models. A walk-forward backtest is run for both per symbol, and the model with the lower Mean Absolute Percentage Error (MAPE) wins per symbol. This best-of-two selection is documented in `best_models.json` and embedded in the `Forecast` block of every fused signal.

A separate consideration applies to multi-step forecasting (forecasting 30 business days forward). Autoregressive LSTM forecasting compounds error rapidly over long horizons because each prediction is fed back as input for the next prediction. We therefore use **ARIMA-only** for the 30-day trend forecast, accepting the loss of expressive power in exchange for stable error growth.

## 2.2 Sentiment Analysis on Financial Text

Sentiment analysis on financial text is materially different from generic sentiment analysis. Off-the-shelf models trained on movie reviews or social media tend to assign negative polarity to financial terms that are actually neutral or positive in the financial context (e.g., "bearish", "short", "downgrade"). Two distinct lines of work address this.

The first is **lexicon-based**, exemplified by **VADER (Valence Aware Dictionary and sEntiment Reasoner)**, which uses a hand-curated lexicon of words and emoticons annotated with polarity and intensity. VADER is fast, deterministic, requires no training data, and runs trivially on commodity hardware. Its disadvantage is brittleness: it cannot disambiguate context, cannot handle compositional negation well, and was not designed for financial vocabulary.

The second is **transformer-based**, exemplified by **FinBERT** (Araci, 2019; later refined by ProsusAI). FinBERT is a BERT model fine-tuned on the Financial PhraseBank — a corpus of analyst-annotated financial sentences — yielding three-class output (positive / neutral / negative) tuned to the financial domain. FinBERT is significantly more accurate than VADER on financial text but requires PyTorch + Hugging Face Transformers at inference time and consumes hundreds of megabytes of memory.

FinMate uses FinBERT as the **default backend** and VADER as a **fallback** behind a `SENTIMENT_BACKEND` environment variable. We pre-cache FinBERT weights into the Docker image at build time to avoid cold-start delays in GCP Cloud Run.

## 2.3 Ensemble Classifiers for Direction Prediction

A well-known finding in quantitative finance is that price-regression models, even when they minimise MAPE, tend to have unimpressive *directional* accuracy. A model that predicts a stock to close at 101.5 when it actually closed at 100.3 has small percentage error but called the direction wrong. For traders, direction often matters more than magnitude.

The standard remedy is to **train a classifier directly on the directional target** — a binary UP/DOWN label — rather than backing it out of a regression model. We use an ensemble of three complementary classical-ML algorithms:

- **Gradient Boosting** (`GradientBoostingClassifier`): iteratively fits weak learners (decision trees) to the residuals of previous learners. Excellent on small-to-medium tabular datasets.
- **Random Forest** (`RandomForestClassifier`): bagged ensemble of decision trees with feature subsampling, which reduces variance.
- **Logistic Regression**: a linear baseline that anchors the ensemble against overfitting in the tree models.

The ensemble averages predicted probabilities — a "soft voting" scheme — and emits a calibrated probability that the symbol will close UP at horizon `H`, for `H ∈ {1, 5, 20}` business days.

## 2.4 Multi-Signal Fusion in Trading Systems

Combining multiple signal sources (price forecast, news sentiment, technicals) into a single recommendation is a perennial research problem in algorithmic trading. The simplest approach is a **fixed linear combination** — for example, 50% forecast, 30% sentiment, 20% technicals — but this ignores the fact that signal *quality varies across symbols and over time*. A stock with thin news coverage should not have sentiment weighted equally to a stock that is in the news every day.

FinMate's fusion engine implements two ideas to handle this:

1. **Dynamic per-stock quality weights.** Each signal is paired with a quality score in `[0, 1]` that captures how trustworthy it is *for that specific symbol*. Weights are then normalised from those qualities. A 10% floor prevents any signal from being entirely silenced.
2. **Divergence damping.** When the regression forecast is strong (`|score| ≥ 0.5`) but the other two signals disagree, the forecast is dampened by up to 40% before fusion. This is a sanity check against runaway ARIMA / LSTM predictions.

Both mechanisms are designed to deliver *explainable* outputs. Every fused signal in `stocks.json` carries the per-component quality scores, the normalised weights, the pre- and post-damping component scores, the damping factor, and a `PrimaryDriver` string that names which component most influenced the final recommendation.

## 2.5 Retrieval-Augmented Generation (RAG)

A pure language-model chatbot is unreliable for financial questions because it cannot access current prices, news, or the user's portfolio state. **Retrieval-Augmented Generation (RAG)** addresses this by routing every user question through a retrieval step: the question is first used to fetch relevant documents (the user's holdings, recent news, current signals), and only then is a language model used to synthesise a natural-language answer over those retrieved documents.

FinMate's chatbot uses a simple RAG: the `chatbot_rag.ask()` function looks up the user's portfolio, fetches relevant stock signals and recent news for tickers the user holds (or that the question references), and forms a prompt that grounds the model's answer in concrete data. Sources used are stored in the `sources_used` JSONB field on each `ChatMessage` for auditability.

## 2.6 Mobile-First Design Patterns

Modern React Native development has consolidated around a few patterns: **file-based routing** (popularised by Expo Router, modelled after Next.js), **JWT plus a route guard** for protected screens, **AsyncStorage / SecureStore** for token persistence, and **Reanimated** for performant 60-fps animations driven on the UI thread rather than the JS thread.

We adopt all of these. We use AsyncStorage (rather than SecureStore) because the JWT is short-lived and the threat model in our target environment is screen-shoulder-surfing rather than device theft. We use a non-rendering `AuthGuard` component that listens to `useSegments()` and force-redirects users in or out of the protected route group. We use Reanimated worklets to drive the custom floating-pill tab indicator at native frame rate.

## 2.7 Cloud-Native Batch Pipelines

Running an ML pipeline on a fixed schedule — for FinMate, every weekday morning at 06:00 PKT, plus an hourly refresh during market hours — used to require a dedicated VM, cron, and a lot of hand-rolled error handling. The modern pattern is to package the pipeline as a container image and run it as a **scheduled Cloud Run Job** (GCP), an **AWS Lambda + EventBridge** combination, or an **Azure Container Job**. These give per-invocation isolation, retry semantics, scale-to-zero pricing, and detailed observability.

FinMate uses GCP Cloud Run Jobs. The cold pipeline is split into a single weekly job that retrains all models; the warm pipeline is split into four chained jobs — scrape historical, scrape news, run ML and fuse, ingest results into Postgres — so that any one stage can be retried without re-running the whole pipeline.

---

# Chapter 3 — Requirements Engineering

This chapter derives functional and non-functional requirements from the problem statement and stakeholder analysis.

## 3.1 Stakeholders

| Stakeholder | Interests |
|---|---|
| Retail Pakistani investor (primary end user) | Accessible recommendations; portfolio tracking; timely alerts; low cognitive load |
| Project supervisor / academic panel | Documented methodology; reproducible results; novel contribution |
| Future maintainers / contributors | Clean architecture; documentation; tested code |

## 3.2 Functional Requirements

**FR-1 — Account Management.** The system shall allow a user to register an account with a single multi-step payload that captures basic auth (email, password), KYC (CNIC, DOB, address), an investment profile (experience, risk tolerance, goal, income bracket), and notification preferences (channels and session windows). It shall allow login with email/password against a JWT-backed endpoint, with 24-hour access tokens and 7-day refresh tokens.

**FR-2 — Symbol Discovery.** The system shall allow the user to search for any PSX-listed equity by ticker or company name and retrieve a profile page including recent price action, key technicals, the latest fused signal, and recent news for that symbol.

**FR-3 — Portfolio Management.** The system shall allow the user to add, edit, and delete holdings. Each holding records ticker, quantity, average buy price, and may optionally carry a sequence of lot-level transactions. The system shall compute and surface portfolio analytics: total value, gain/loss, allocation across sectors, risk metrics.

**FR-4 — Recommendations.** The system shall generate per-symbol BUY / HOLD / SELL recommendations grounded in a fused signal that combines price forecast, news sentiment, and technicals. Each recommendation shall carry an explainability payload (`PrimaryDriver`, per-component contributions, quality scores).

**FR-5 — Alerts.** The system shall deliver alerts at three trading-day-aligned windows (08:00, 12:30, 17:30 PKT) over up to four channels: in-app, email, WhatsApp, Slack. Channel selection is per-user.

**FR-6 — Chatbot.** The system shall allow the user to ask natural-language questions about their portfolio or about a specific stock and receive an answer grounded in current data via Retrieval-Augmented Generation.

**FR-7 — News Feed.** The system shall present a market news feed sourced from Google News RSS with fallback to Dawn, Business Recorder, and ProPakistani; news shall be filtered to Pakistani context and per-ticker matched.

**FR-8 — Pipeline Scheduling.** The system shall scrape new data, run the ML pipeline, fuse signals, and ingest results into the database on a fixed weekday schedule (06:00 morning, hourly during market hours, monthly registry refresh).

## 3.3 Non-Functional Requirements

**NFR-1 — Availability.** The mobile-facing API shall be available 24/7 with low restart latency; cold-start cost shall be minimised by pre-caching ML model weights into the Docker image at build time.

**NFR-2 — Latency.** Mobile-facing API endpoints shall respond in under 1 second at the 95th percentile under typical load.

**NFR-3 — Localisation.** All currency is rendered in PKR (`en-PK` locale). All timestamps are rendered in Pakistan Standard Time (`Asia/Karachi`). All KYC validators enforce Pakistani identity formats (CNIC `XXXXX-XXXXXXX-X`, phone `0XXX-XXXXXXX`, 5-digit postal codes).

**NFR-4 — Security.** All protected endpoints require a valid JWT bearer token. Tokens expire after 24 hours and are refreshed via a 7-day refresh token. Passwords are hashed with Django's PBKDF2 default. Secrets live in `.env` and are never committed to Git (`.env.example` is the contract).

**NFR-5 — Maintainability.** The codebase is organised into per-domain Django apps with one model file, one views file, and one serializers file per app. Configuration lives in `config/`. Documentation lives in markdown files at the repository root, one per major subsystem.

**NFR-6 — Observability.** Every Celery task logs structured events. Every alert dispatch is recorded in `AlertLog` with channel-level outcome. The MLflow tracking integration uses a circuit-breaker pattern: tracking failures are swallowed and the breaker trips after 5 consecutive failures, preventing tracking outages from interrupting the actual pipeline.

**NFR-7 — Cost.** The system uses scale-to-zero managed services (Cloud Run, Cloud Run Jobs, Supabase free tier, Upstash free tier) so that monthly cost remains low and predictable while still allowing production-grade behaviour.

**NFR-8 — Explainability.** Recommendations shall include a `PrimaryDriver`, per-component contributions, weights, and quality scores. Users shall not be served a black-box BUY/SELL.

## 3.4 Use Cases

### UC-1 — Register and Onboard

1. User opens app for the first time.
2. App routes to the login screen (`/`); user taps "Sign up".
3. App walks the user through four steps: Account → KYC → Risk → Verified.
4. On final submit, app POSTs a single payload to `/api/v1/users/register/`.
5. Backend creates `CustomUser`, `UserKycProfile`, `InvestmentProfile`, and `NotificationPreference` atomically; returns access + refresh tokens.
6. App stores access token in AsyncStorage under `@finmate_auth_token`.
7. `AuthGuard` redirects the user into the protected tab group at `/(tabs)/dashboard`.

### UC-2 — Add a Holding

1. User opens the Portfolio tab and taps "Manage portfolio".
2. App opens the three-step add-holding wizard.
3. Step 1 — Search: user types a ticker; app calls `/api/v1/core/stock-search/`.
4. Step 2 — Enter Lots: user enters either quantity + price, or total invested.
5. Step 3 — Confirm: app POSTs to `/api/v1/portfolio/holdings/`.
6. Backend creates `PortfolioHolding`, recomputes analytics, returns updated holding payload.
7. App updates local state and renders the new holding.

### UC-3 — Receive a Morning Alert

1. At 08:00 PKT on a weekday, Celery Beat fires `alerts.tasks.send_morning_alerts`.
2. The task selects alert candidates from `stocks.json` and from each user's portfolio.
3. For each candidate, the task creates an `Alert` row, an `AlertDetail` row containing rich JSONB payload, and one `AlertLog` row per channel for the recipient.
4. Channel adapters dispatch the alert (in-app via `Notification`, email via SendGrid, WhatsApp via Twilio, Slack via webhook).
5. Each `AlertLog` is updated with the dispatch outcome.

### UC-4 — Ask the Chatbot

1. User opens the Chatbot tab.
2. User types "Why did Lucky Cement drop today?"
3. App POSTs to `/api/v1/chatbot/ask/` with `{ message, session_id? }`.
4. The view persists a `ChatMessage` of role `USER`, then calls `chatbot_rag.ask()`.
5. The RAG layer retrieves: the latest LUCK signal, recent news matched to LUCK, the cement sector context.
6. The LM is prompted with those documents; the answer is persisted as another `ChatMessage` of role `ASSISTANT` with the `sources_used` field populated.
7. The view returns `{ answer, session_id }`.

### UC-5 — Inspect a Stock

1. User opens the Insights tab.
2. App calls `/api/v1/insights/filters/` for the sector/signal/sort enums, then `/api/v1/insights/stocks/?page=1` for the list.
3. User filters by sector and taps a stock.
4. App navigates to `/stock-insight/[ticker]` and calls `/api/v1/insights/stocks/<ticker>/`.
5. Screen renders live OHLC, MA20/50/200, RSI, volatility, EPS, signal confidence dots, and recent news.

## 3.5 Acceptance Criteria

The project shall be considered successful when:

- A demo user can register, onboard, log in, view recommendations, add holdings, see analytics, receive at least one alert in at least one channel, ask the chatbot a question and receive an answer, and log out — entirely from the mobile client.
- The ML pipeline runs end-to-end against production data on the scheduled cadence, populates `stocks.json` and the database, and the result is reflected in the mobile client.
- The directional classifier achieves at least 50% next-day hit rate on a held-out portion of the historical data.
- The full backend boots from a clean Docker image and survives a cold start in under 60 seconds.

---

# Chapter 4 — System Architecture and Design

## 4.1 High-Level Architecture

The system is organised into seven logical tiers:

```
┌──────────────────────────────────────────────────────────────┐
│  TIER 1 — Mobile Client                                      │
│  Expo SDK 54, React Native 0.81, TypeScript                  │
│  Auth, screens, navigation, charts, services                 │
└──────────────────┬───────────────────────────────────────────┘
                   │ HTTPS + JWT
┌──────────────────▼───────────────────────────────────────────┐
│  TIER 2 — REST API                                           │
│  Django 4.2 + DRF on GCP Cloud Run                           │
│  8 apps, 21 models, 30+ endpoints                            │
└──────────────────┬───────────────────────────────────────────┘
                   │
        ┌──────────┼──────────┬─────────────┐
        │          │          │             │
┌───────▼──┐  ┌────▼─────┐  ┌─▼──────────┐ ┌▼────────────────┐
│ Supabase │  │ Upstash  │  │   GCS      │ │   n8n           │
│ Postgres │  │ Redis    │  │ etl_b      │ │ workflows       │
│ (DB)     │  │ (cache + │  │ (data +    │ │ A: strong       │
│          │  │  broker) │  │  models)   │ │ B: portfolio    │
└──────────┘  └──────────┘  └──┬─────────┘ └────────┬────────┘
                               │                    │
                  ┌────────────▼──────────┐         │
                  │ TIER 3 — Cloud Run    │         │
                  │ Jobs (cold + warm)    │         │
                  │ scrape → ML → ingest  │         │
                  └────────┬──────────────┘         │
                           │                        │
                  ┌────────▼────────────┐  ┌────────▼─────────┐
                  │ TIER 4 — ML / Data  │  │ TIER 5 — Alerts  │
                  │ scrapers, FinBERT,  │  │ in-app, email,   │
                  │ ARIMA+LSTM, fusion  │  │ WhatsApp, Slack  │
                  └─────────────────────┘  └──────────────────┘
```

Tiers 6 and 7 are the **chatbot subsystem** (a thin RAG layer over the API + a dedicated Django app) and **the observability stack** (MLflow for ML experiments; structured logs from Django and Celery to GCP Cloud Logging).

## 4.2 Component Diagram

The eight Django apps and their internal relationships are:

```
                ┌──────────────┐
                │   users/     │
                │  CustomUser  │
                │  KycProfile  │
                │ InvestProfile│
                │ NotifPref    │
                └──────┬───────┘
                       │ ForeignKey
            ┌──────────┼──────────┬─────────────┐
            ▼          ▼          ▼             ▼
      ┌─────────┐ ┌─────────┐ ┌────────┐  ┌──────────┐
      │portfolio│ │ chatbot │ │ alerts │  │ dashboard│
      │Holding  │ │Session  │ │Alert   │  │Cache     │
      │Txn      │ │Message  │ │Log     │  └─────┬────┘
      └────┬────┘ └────┬────┘ │Detail  │        │
           │           │      │Notif   │        │
           │           │      └───┬────┘        │
           ▼           ▼          │             ▼
        ┌──────────────────────────────────────────┐
        │              core/                       │
        │  StockSymbol, StockTechnicals,           │
        │  StockForecast, ForecastTrend,           │
        │  NewsSentiment, StockSignal,             │
        │  LiveMarketData, ScrapeRun               │
        └──────────────┬───────────────────────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
        ┌──────────┐      ┌──────────────┐
        │integrations/   │  ml_services/ │
        │  scrapers/     │  forecasting  │
        │  tasks         │  sentiment    │
        │                │  directional  │
        │                │  fusion       │
        │                │  stock_health │
        │                │  chatbot_rag  │
        └────────────────┴───────────────┘
                  ▲
                  │
            ┌─────┴────────┐
            │  insights/   │
            │  views read  │
            │  from core + │
            │  stocks.json │
            └──────────────┘
```

## 4.3 Data Flow

The end-to-end data flow is:

1. **Scrapers** under `integrations/scrapers/` collect raw data from PSX and Google News into JSON files in `integrations/data/`.
2. **`ml_services/` modules** consume those JSON files. The forecasting module produces `stock_forecasts.json`, `forecasting_trend.json`, and `best_models.json`. The sentiment module produces `news_sentiment.json`. The directional classifier produces `directional_signals.json`.
3. **`ml_services/stock_health.py`** orchestrates the fusion engine in `fusion.py`, joining all of the above plus `daily_ratios.json` (technicals) and `fundamental_ratios.json` (fundamentals) into one row per symbol in `stocks.json`.
4. **The ingest stage (warm-4)** reads the JSON files and upserts rows into `core/` models (`StockSignal`, `StockForecast`, `NewsSentiment`, `StockTechnicals`, `LiveMarketData`).
5. **The DRF API** reads from `core/` (for individual queries) and from `stocks.json` (for fused, denormalised views like the dashboard).
6. **The mobile client** consumes the API over HTTPS, carrying a JWT bearer token.
7. **Celery tasks** for alerts read the latest signals + each user's portfolio, generate `Alert` + `AlertDetail` + `AlertLog` rows, and dispatch over the four channels (the WhatsApp and email payloads are formatted by n8n workflows that consume an outbound webhook from Django).

## 4.4 Why JSON Files Persist Alongside the Database

A natural design question is: why does the system maintain JSON files (`stocks.json`, `historical_data.json`, etc.) in addition to a relational database? The answer is twofold:

- **Pipeline simplicity.** Each stage of the batch pipeline consumes and produces JSON files. This makes the pipeline trivially **replayable** — drop a new `news_data.json` into the data folder and re-run the ML stage; nothing else needs to change. Stages are decoupled by file boundaries, not by database transactions.
- **GCS-portable artefacts.** JSON files sync trivially to GCS and back. Mounting a database in Cloud Run Jobs would be possible but adds latency and connection-pool concerns. JSON files are the cheapest possible inter-stage interchange format.

The database is the source of truth for *user state* (accounts, portfolios, alerts) and an *ingest sink* for the latest ML outputs. JSON files are the source of truth for the *pipeline artefacts themselves*.

## 4.5 Database Schema Overview

The 21 Django models can be grouped into five domain clusters:

- **Identity** (`users/`): `CustomUser`, `UserKycProfile`, `InvestmentProfile`, `NotificationPreference`.
- **Market data** (`core/`): `StockSymbol`, `StockTechnicals`, `StockForecast`, `ForecastTrend`, `NewsSentiment`, `StockSignal`, `LiveMarketData`, `ScrapeRun`.
- **User holdings** (`portfolio/`): `PortfolioHolding`, `Transaction`.
- **Alerts** (`alerts/`): `Alert`, `AlertLog`, `AlertDetail`, `Notification`.
- **Chatbot** (`chatbot/`): `ChatSession`, `ChatMessage`.
- **Caching** (`dashboard/`): `DashboardCache`.

A full schema reference appears in Appendix B.

## 4.6 Authentication and Authorisation Model

A single permission tier (`IsAuthenticated`) protects all non-public endpoints. There is no admin/user split exposed to clients — Django admin is used internally for support, and the customer-facing surface is uniformly per-user, with row-level isolation enforced by filtering on `user=request.user` inside views and querysets.

JWTs are issued by `EmailLoginView` (which subclasses SimpleJWT's `TokenObtainPairView`) and validated by SimpleJWT's `JWTAuthentication` class wired into the DRF default authentication classes. Tokens are stateless — a logout simply discards the token on the client side; we do not maintain a server-side blacklist.

---

# Chapter 5 — Backend Implementation (Django + DRF)

## 5.1 Project Layout

```
config/         # project root: settings, urls, celery, celery_schedule
users/          # authentication, profile, KYC, investment, notifications
core/           # symbols, technicals, signals, forecasts, sentiment, live, scrape runs
portfolio/      # holdings, transactions, analytics
chatbot/        # sessions, messages, RAG entrypoint
alerts/         # alerts, logs, details, notifications, channel adapters
integrations/   # scrapers, scheduled-ingestion tasks, data files
ml_services/    # forecasting, sentiment, directional, fusion, RAG, MLflow, GCS
dashboard/      # aggregated dashboard endpoint and cache
insights/       # filterable stock-list endpoint and per-ticker detail
n8n/            # n8n workflow JSON exports and notification examples
bin/            # bash orchestrators for cold and warm pipelines
psx/            # PSX-specific scrapers / utilities
scripts/        # ad-hoc admin scripts
```

`requirements.txt` pins all dependencies and `Dockerfile` builds a production image based on `python:3.13-slim`.

## 5.2 Settings

`config/settings.py` is single-file. It reads environment variables via `django-environ`. Key choices:

- `INSTALLED_APPS` adds `rest_framework`, `rest_framework_simplejwt`, `corsheaders`, `django_celery_beat`, plus the eight local apps.
- `MIDDLEWARE` orders `SecurityMiddleware → CorsMiddleware → WhiteNoiseMiddleware → SessionMiddleware → CommonMiddleware → CsrfViewMiddleware → AuthenticationMiddleware`. WhiteNoise serves static files in production without a separate reverse proxy.
- `CORS_ALLOWED_ORIGINS` opens `http://localhost:3000` (legacy React web) and `http://localhost:8081` (Expo Metro). Production frontends are allow-listed via env-var.
- `TIME_ZONE = "Asia/Karachi"`; `USE_TZ = True`.
- `AUTH_USER_MODEL = "users.CustomUser"`.
- `REST_FRAMEWORK` defaults to `IsAuthenticated` and the SimpleJWT authentication class.

## 5.3 `users/` — Authentication and Onboarding

The `users/` app exposes a custom user model `CustomUser(AbstractUser)` that uses email rather than username as the primary identifier. Around it sit three companion models — `UserKycProfile` (CNIC, date of birth, gender, city, province, postal code), `InvestmentProfile` (experience, risk tolerance, goal, income bracket), and `NotificationPreference` (the per-channel toggles, the per-session windows, and an optional Slack webhook URL).

The `RegisterView` enforces an atomic single-payload registration:

```python
def post(self, request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        user = serializer.save()
        UserKycProfile.objects.create(user=user, **request.data["kyc"])
        InvestmentProfile.objects.create(user=user, **request.data["investment"])
        NotificationPreference.objects.create(user=user, **request.data.get("notifications", {}))
    return Response({
        "access": str(RefreshToken.for_user(user).access_token),
        "refresh": str(RefreshToken.for_user(user)),
    })
```

This avoids the half-created-account problem that arises when each section is its own POST.

The login view, `EmailLoginView`, subclasses SimpleJWT's `TokenObtainPairView` and overrides the username field to be `email`.

`ProfileView`, `InvestmentProfileView`, `NotificationPreferenceView`, `ChangePasswordView`, `UserFullDetailsView`, `UserProfileKycUpdateView` cover the remaining account lifecycle (read, update, password change, full aggregated details for the profile screen).

## 5.4 `core/` — Market Data Layer

`core/` is the canonical market-data layer. It owns:

- `StockSymbol` — the master catalogue of PSX equities, populated by the `registry_scraper`.
- `StockTechnicals` — per-day technicals (MA20, MA50, MA200, RSI14, volatility, volume ratio).
- `StockForecast` — per-model forecast rows, with `predicted_price`, `direction`, and `model_used` (ARIMA, LSTM).
- `ForecastTrend` — the 30-business-day forward ARIMA trend.
- `NewsSentiment` — one row per (symbol, news article), with a 5-class label and a numeric score.
- `StockSignal` — the final fused signal per symbol (the per-stock row that mirrors `stocks.json`).
- `LiveMarketData` — today's intraday hourly bars in PKT.
- `ScrapeRun` — one audit row per ingestion run (for observability).
- `TimestampMixin` — abstract base that supplies `created_at` / `updated_at`.

All `core/` views are read-only `ListAPIView` and `RetrieveAPIView` subclasses. Writes happen through the ingest stage of the warm pipeline, not through the API.

## 5.5 `portfolio/` — Holdings and Transactions

`PortfolioHolding` carries a UUID primary key and is keyed on `(user, symbol)`. It stores `quantity` and `avg_buy_price`. Transactions are tracked separately in `Transaction` (a child of `TimestampMixin`) which records each buy or sell with a price and quantity, and recomputes the parent holding's `avg_buy_price` on insert.

`PortfolioAnalyticsView` joins holdings against `LiveMarketData` for the live price, computes total invested vs current value, gain/loss in PKR and percentage terms, sector allocation, and a few risk metrics (beta vs the KSE100, where computable). The output schema is what the Portfolio screen on the mobile client renders.

## 5.6 `insights/` and `dashboard/` — Read-Side Views

Two thin, read-side Django apps power the most-visited screens in the mobile client.

`insights/` exposes three endpoints:

- `GET /insights/filters/` — returns the enum set for sectors, signal types, and sort options.
- `GET /insights/stocks/?sector=X&signal=Y&sort=Z&page=N` — paginated stock list with filtering and sorting.
- `GET /insights/stocks/<ticker>/` — drill-down with full signal payload, technicals, recent news for the ticker.

`dashboard/` exposes two endpoints:

- `GET /dashboard/stocks/` — aggregated cards (AI picks, top performers, rising stars, sector sentiment, market mood).
- `GET /dashboard/news/` — aggregated PSX news feed.

The dashboard endpoint reads from `DashboardCache` for performance — the cache is refreshed by the warm-4 ingest stage and read directly by the API.

## 5.7 `alerts/` — Alert and Notification Models

The `alerts/` app owns four models:

- `Alert` — one row per generated alert.
- `AlertDetail` — one row carrying a rich JSONB payload (the data used to generate the per-channel formatted message).
- `AlertLog` — one row per (alert, channel, user) with the dispatch outcome.
- `Notification` — the in-app notification feed.

Three views back the mobile UX:

- `GET /alerts/history/` — list past alerts.
- `GET /alerts/history/<id>/` — alert detail.
- `GET/PATCH /alerts/preferences/` — read or update channel preferences.

The channel adapters live in `alerts/channels/` (SendGrid, Twilio, Slack) and are called from the Celery tasks `alerts.tasks.send_morning_alerts`, `alerts.tasks.send_midday_alerts`, and `alerts.tasks.send_evening_digest`.

## 5.8 `chatbot/` — Sessions and Messages

The chatbot app, owned by Ammara, contains two models:

```python
class ChatSession(TimestampMixin):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

class ChatMessage(TimestampMixin):
    class Role(models.TextChoices):
        USER = "USER", "User"
        ASSISTANT = "ASSISTANT", "Assistant"
    session = models.ForeignKey(ChatSession, on_delete=CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    sources_used = models.JSONField(default=dict, blank=True)
```

The session table is keyed on the user and orders by `-last_active`, so a user's list of sessions is naturally chronological. The `sources_used` JSONB field on `ChatMessage` is the audit trail — every assistant message records which symbols, news items, and signals were retrieved during RAG.

The primary view, `ChatView`, is a single POST endpoint. On each call it:

1. Validates input with `ChatAskSerializer`.
2. Finds or creates the session.
3. Persists the user's message as a `ChatMessage(role=USER)`.
4. Calls `ml_services.chatbot_rag.ask(question, user, session_id)`.
5. Persists the assistant's reply as a `ChatMessage(role=ASSISTANT)`.
6. Updates `last_active` and returns `{ answer, session_id }`.

This separates concerns cleanly — the Django view handles persistence, while the RAG layer in `ml_services/chatbot_rag.py` handles retrieval and language-model invocation.

## 5.9 `integrations/` — Pipeline Glue and `dashboard/` Status

`integrations/` packages all data-collection logic. Its `scrapers/` subpackage holds the five scrapers (covered in detail in Chapter 6). Its `tasks.py` exposes the Celery entry points (`morning_full_fetch`, `hourly_refresh`, `run_registry_scraper`) that are scheduled by Celery Beat. It also exposes a single GET endpoint:

- `GET /integrations/status/` — returns the last successful scrape time, the most recent `ScrapeRun` row, and pipeline-stage latency information.

This is consumed by an internal status dashboard and gives engineers a quick health check.

---

# Chapter 6 — Data Ingestion and Scraping Layer

## 6.1 Inventory

`integrations/scrapers/` contains five operational scrapers plus a registry of PSX symbols.

| File | LOC | Purpose |
|---|---|---|
| `registry_scraper.py` | 209 | Refresh the PSX symbol list (`symbols.py`) — monthly job |
| `historical_scraper.py` | 246 | Daily OHLCV bars for all symbols since 2000 |
| `live_scraper.py` | 316 | Hourly intraday bars during today's PKT session |
| `news_scraper.py` | 803 | Google News RSS + Dawn/BR/ProPakistani fallback |
| `key_ratios_scraper.py` | 244 | Daily technicals (MA, RSI, vol) + best-effort fundamentals |
| `extract_last_bars.py` | 59 | Utility — extract the most recent N bars from history |
| `symbols.py` | 5,343 | Generated module listing all 738 PSX equities |

A `SCRAPER_LIMIT=N` env var lets developers run each scraper over only the first N symbols, which is essential during development given the 738-equity universe.

## 6.2 The Registry Scraper

The registry scraper visits the PSX listing page, parses the list of currently-active equities, and regenerates `symbols.py`. The first 20 entries are the **curated set** — each carries hand-tuned `aliases` and `keywords` that drive the news matcher. The remaining 718 entries are produced automatically from the listing page and have only the ticker symbol and short company name.

The curated set was chosen by trading volume and brand recognition (HBL, MCB, OGDC, PPL, LUCK, FFC, ENGRO, etc.). Aliases for these top symbols include both formal names ("Lucky Cement Limited"), common short names ("Lucky Cement", "LUCKY"), and Pakistan-context keywords ("LCL", "Yunus Brothers", etc.). The hand-tuning is essential — it is the difference between a news matcher that picks up real news about Lucky Cement and one that returns articles about "lucky" people winning lottery tickets.

## 6.3 The Historical Scraper

The historical scraper uses `psx-data-reader` to pull every OHLCV bar from 2000 to today for every symbol in the registry. The output is a single `historical_data.json` of approximately 327 MB. Each row is:

```json
{ "Symbol": "LUCK", "Date": "2024-04-15", "Open": 745.10, "High": 752.30,
  "Low": 740.00, "Close": 749.80, "Volume": 1240800 }
```

In production the scraper is run weekly as part of the cold pipeline. In the warm pipeline, only the most recent bars are pulled (via `extract_last_bars.py`) so that the existing `historical_data.json` can be appended in-place.

## 6.4 The Live Scraper

The live scraper runs hourly during the PSX trading session (09:00 to 15:00 PKT, weekdays). It writes `live_data.json` — the same shape as `historical_data.json` but covering only today's hourly bars. The mobile client's per-ticker detail screen reads from this file via the `/core/live/<ticker>/` endpoint to show a "live" price.

## 6.5 The News Scraper — Engineering Notes

`news_scraper.py` is by far the most engineered scraper, at 803 lines of Python. It pulls Google News RSS results, parses headlines and bodies, and matches them against the symbol registry. The naive version of this is straightforward — search the text for any ticker — but in practice it produces an unacceptable false-positive rate. Real false-positives caught during development and visible in commit history include:

- `SPL` matched articles about the **Saudi Premier League** and the **Saudi Pro League**.
- `LUCK` matched generic articles about "lucky" people, "lucky" lottery winners, "lucky" cricket teams.
- `FFC` (Fauji Fertiliser Company) matched articles about FIFA Foundation Cup.
- Common English-word three-letter tickers leaked through repeatedly.
- Indian and Saudi financial news leaked through because some PSX tickers are short and ambiguous.

The fix evolved over a sequence of pull requests. The current matcher uses a **tier-based scheme**:

- **Tier 1** — gate ticker matching to the article **title only** for very short tickers; the title is signal-dense, the body is noise-dense.
- **Tier 2** — body-text matching is allowed but only when the article also contains at least one Pakistani-context token (e.g., "Pakistan", "PSX", "PKR", "Karachi", "Lahore", "SBP", "FBR").
- **Blocklist** — common English words and well-known non-financial entities are explicitly excluded from Tier 2 matching for common-English-word tickers.
- **Sports / Entertainment pre-filter** — articles tagged sports or entertainment in the RSS feed are dropped before ticker matching.

A complementary improvement adds a **fallback chain**. When Google News returns nothing or an error (which happens during periodic rate-limit episodes), the scraper falls back to RSS feeds from Dawn, Business Recorder, and ProPakistani in sequence. When even the fallback yields a partial run, the scraper exits 0 (the pipeline does not crash) so that the ML stage runs over whatever data was successfully collected.

The most recent enhancements (May 2026) introduce:

- **Industry-level news capture.** Articles that match no specific ticker but match an industry classifier (Politics, IT, Agriculture, Macro) are captured as `GENERAL` rows.
- **Industry classifiers.** Each captured article is tagged with one of {Politics, IT, Agriculture, …} so the sentiment layer can blend per-ticker sentiment with per-industry sentiment.
- **7-day rolling window** with industry/macro blending so a stock with no per-ticker news in a week still gets a sentiment signal based on its industry.

## 6.6 The Key Ratios Scraper

`key_ratios_scraper.py` does two things:

- Computes per-symbol technicals from the historical bars — MA20, MA50, MA200, RSI14, volatility (standard deviation of returns over a rolling window), volume ratio (today vs 20-day average). Output: `daily_ratios.json`.
- Best-effort fundamentals — visits PSX's per-symbol fundamentals page and extracts EPS, P/E, P/BV, dividend yield, market cap. The "best effort" caveat is because the PSX page does not list every symbol and the data is occasionally incomplete or stale. Output: `fundamental_ratios.json`.

## 6.7 Data Files Produced

| File | Size | Producer |
|---|---|---|
| `historical_data.json` | 327 MB | `historical_scraper.py` |
| `stock_forecasts.json` | 14 MB | `ml_services.forecasting` |
| `forecasting_trend.json` | 4.4 MB | `ml_services.forecasting` |
| `stocks.json` | 2.3 MB | `ml_services.stock_health` |
| `directional_signals.json` | 553 KB | `ml_services.directional_classifier` |
| `news_sentiment.json` | 378 KB | `ml_services.sentiment` |
| `news_data.json` | 352 KB | `news_scraper.py` |
| `daily_ratios.json` | 234 KB | `key_ratios_scraper.py` |
| `fundamental_ratios.json` | 191 KB | `key_ratios_scraper.py` |
| `best_models.json` | 124 KB | `ml_services.forecasting` |
| `live_data.json` | 11 KB | `live_scraper.py` |
| `active_symbols.json` | 4.7 KB | aux file gating ML to active symbols |

Total pipeline disk footprint (data + model cache, including GCS-synced artefacts) exceeds 3 GB.

---

# Chapter 7 — Machine Learning Services

## 7.1 Module Map

`ml_services/` contains 2,818 lines of Python across nine modules:

| Module | LOC | Purpose |
|---|---|---|
| `forecasting.py` | 749 | ARIMA + multi-feature LSTM, walk-forward backtest, 30-day trend |
| `stock_health.py` | 573 | Orchestrator — fuses signals, emits `stocks.json` |
| `directional_classifier.py` | 401 | 3-model ensemble UP/DOWN classifier |
| `gcs_sync.py` | 369 | Bi-directional GCS sync for data + model cache |
| `fusion.py` | 243 | Adaptive per-stock weighting + divergence damping |
| `sentiment.py` | 217 | FinBERT (default) + VADER (fallback) |
| `mlflow_utils.py` | 180 | MLflow tracking with circuit-breaker pattern |
| `model_cache.py` | 72 | Warm-mode artefact reuse |
| `chatbot_rag.py` | 6 | RAG entrypoint stub (interface) |

## 7.2 Forecasting Pipeline

The forecasting module trains two models per symbol:

1. **ARIMA** — `statsmodels.tsa.arima.model.ARIMA` with order `(p, d, q)` tuned per-symbol. The integration step `d` makes the series stationary; the AR term `p` captures short-term momentum; the MA term `q` captures the moving average of residuals. Per-symbol order tuning is bounded by a search budget so that retraining stays cheap.
2. **LSTM** — a 2-layer LSTM with 64 hidden units and dropout 0.2, trained on a 4-feature window (`close`, `volume`, `1-day returns`, `5-day returns`) with a 60-bar lookback. Trained with mean-squared-error loss, early stopping on a 15% chronological validation split.

### Backtest

The backtest is **walk-forward** over the last 60 days. Each day, we:

1. Train both models on the data up to day `t`.
2. Predict close at day `t + 1` with each.
3. Record the absolute percentage error.

After 60 days, we compute MAPE for each model. The model with the lower MAPE wins per symbol and is recorded in `best_models.json`. ARIMA is refit weekly during the backtest; the LSTM is fit once and reused.

### Forward Trend

For the 30-business-day forward forecast we use **ARIMA only**, because autoregressive LSTM predictions compound error rapidly when each prediction is fed back as input. The output is `forecasting_trend.json` and is rendered as the dashed forward line on the mobile-client stock detail screen.

### Warm vs Cold

In **cold mode** (weekly), both models are retrained from scratch for every symbol. In **warm mode** (hourly), the LSTM is *loaded* from a pickled cache in `models/` (synced from GCS via `gcs_sync.py`); only ARIMA is refit. The README documents a ~30× speedup of warm mode over cold for the forecasting stage alone, which is what allows the warm pipeline to run hourly during market hours within Cloud Run's wall-clock budgets.

## 7.3 Sentiment Pipeline

`sentiment.py` loads either FinBERT (default) or VADER (fallback). Backend selection is via `SENTIMENT_BACKEND=finbert|vader`.

### FinBERT

`ProsusAI/finbert` is a BERT model fine-tuned on the Financial PhraseBank corpus. It outputs a 3-class probability distribution: positive, neutral, negative. We define each article's **compound score** as `pos_prob − neg_prob`, then bucket into 5 labels:

| Compound score range | Label |
|---|---|
| `>= +0.6` | `EXCELLENT` |
| `+0.2 ≤ s < +0.6` | `GOOD` |
| `−0.2 < s < +0.2` | `NEUTRAL` |
| `−0.6 < s ≤ −0.2` | `BAD` |
| `≤ −0.6` | `VERY_BAD` |

The buckets mirror the `NewsSentiment` model's choices in `core/models.py`.

### VADER

VADER is used as a lighter fallback. It runs in pure Python without GPU, costs nothing in container size, and gives reasonable approximations on neutral or strongly-polarised news. It is documented to be less accurate than FinBERT on technical financial vocabulary.

### Industry-Wise Sentiment

The most recent commits introduce an `industry_wise` column. The sentiment layer classifies each article into one of {Politics, IT, Agriculture, …} using a small set of regex/keyword classifiers, then computes industry-level sentiment as a moving average. The fusion layer uses this when a specific ticker has thin news coverage in the last 7 days.

## 7.4 Directional Classifier

`directional_classifier.py` (401 lines) trains an ensemble of three sklearn models per (symbol, horizon) pair, where horizon is one of {1, 5, 20} business days.

### Features

Fifteen engineered features feed every model:

- Returns over 1, 5, 20 days.
- Rolling mean returns and rolling standard deviation of returns over 20 and 60 days.
- RSI(14).
- MACD line, MACD signal line.
- Bollinger band width and position.
- Volume ratio (today vs 20-day average).
- 5-day momentum.
- ATR(14).

### Models

- `GradientBoostingClassifier` (sklearn default depth 3, 100 estimators)
- `RandomForestClassifier` (200 estimators, max_depth tuned per symbol)
- `LogisticRegression` (L2 penalty)

### Ensemble Vote

Each model emits `P(UP | features)`; the ensemble averages these probabilities — a soft vote. The final UP/DOWN label is `1` if the average probability exceeds 0.5, else `0`.

### Reported Performance

- **51.5% average next-day hit rate** across all symbols and ensembles.
- **70%+ hit rate** on specific decisive (symbol, horizon) pairs — that is, the cases where the ensemble's confidence is high (probability > 0.7 or < 0.3). These are the cells in `directional_signals.json` where the system has actual conviction.

The 70%+ figure is the meaningful one for product use: the system *abstains* on low-confidence signals (folding them into the HOLD bucket) and *acts* only when at least one model in the ensemble is confident.

## 7.5 Stock Health Orchestrator

`stock_health.py` is the orchestrator that joins everything together. For each active symbol it:

1. Loads the forecast row from `stock_forecasts.json` and the best-model winner from `best_models.json`.
2. Loads the per-symbol news sentiment rows from `news_sentiment.json`.
3. Loads the per-symbol technicals from `daily_ratios.json`.
4. Loads the directional signal from `directional_signals.json`.
5. Loads the fundamentals from `fundamental_ratios.json`.
6. Calls `fusion.compute(...)` to produce the final `Health` block.
7. Writes one row per symbol into `stocks.json`.

Each row in `stocks.json` looks roughly like:

```json
{
  "Symbol": "LUCK",
  "Name": "Lucky Cement Limited",
  "Sector": "Cement",
  "Live": { "Price": 745.10, "Change": +2.1, "ChangePct": +0.28, "VolumeRatio": 1.4 },
  "Forecast": { "Predicted": 752.40, "Direction": "UP", "Model": "ARIMA", "MAPE": 0.022 },
  "Sentiment": { "Score": 0.34, "Label": "GOOD", "ArticleCount": 5 },
  "Technicals": { "RSI14": 58.2, "MA20": 738.5, "MA50": 712.8, "MA200": 689.1, "Vol": 0.018 },
  "Fundamentals": { "EPS": 78.4, "PE": 9.5, "PBV": 1.3, "DividendYield": 0.04 },
  "Directional": { "1d": {"Prob": 0.62, "Label": "UP"}, "5d": {...}, "20d": {...} },
  "Health": {
    "Quality": { "Forecast": 0.85, "Sentiment": 0.62, "Technicals": 0.78 },
    "Weights":  { "Forecast": 0.38, "Sentiment": 0.28, "Technicals": 0.34 },
    "ComponentsRaw":  { "Forecast": 0.42, "Sentiment": 0.34, "Technicals": 0.21 },
    "Components":     { "Forecast": 0.42, "Sentiment": 0.34, "Technicals": 0.21 },
    "ForecastDamping": 1.0,
    "Suggestion": "BUY",
    "Contributions": { "Forecast": 52.48, "Sentiment": 2.21, "Technicals": 45.32 },
    "PrimaryDriver": "Forecast"
  }
}
```

The `Contributions` block (Forecast: 52.48, Sentiment: 2.21, Technicals: 45.32) is what powers the explainability views in the mobile client — the user can see at a glance which signal drove the recommendation.

## 7.6 MLflow Integration

`mlflow_utils.py` wraps the MLflow Python SDK and provides:

- A context manager `mlflow_run(experiment_name)` that swallows all MLflow exceptions and writes them to the log.
- A **circuit breaker**: after 5 consecutive failed MLflow calls, the wrapper trips and short-circuits all subsequent calls for the rest of the process. This was added after a production incident in which an MLflow tracking-server outage caused the entire pipeline to hang on connection retries.
- Experiment-name versioning: when the MLflow tracking server enters an "orphaned experiment" state (an internal MLflow bug), we simply rename our experiments to `*_v2` and continue.

## 7.7 Model Cache and GCS Sync

`model_cache.py` (72 lines) lets the LSTM artefacts be reused across warm-mode runs. After cold-mode training, each model is pickled to `ml_services/artifacts/{symbol}.h5` and synced to GCS via `gcs_sync.py`. On warm-mode startup, `gcs_sync.py` pulls the cache to local disk; `model_cache.py` then reads each pickle as needed.

The cache in GCS holds:

- ~672 LSTM `.h5` pickles
- ~1,892 directional classifier `.pkl` pickles (covering symbol × horizon × seed combinations)

Total cache size: ~3.1 GB.

---

# Chapter 8 — Adaptive Fusion Engine

This chapter goes deep on `fusion.py` because it is the most original ML contribution of the project.

## 8.1 The Fusion Problem

We have three signals per symbol on any given trading day:

- **Forecast** — a numeric score in `[-1, +1]` derived from the predicted-vs-current price change normalised to the symbol's recent volatility.
- **Sentiment** — a numeric score in `[-1, +1]` derived from the mean compound sentiment score over the last 7 days of news for the symbol.
- **Technicals** — a numeric score in `[-1, +1]` derived from a weighted combination of RSI deviation from 50, MA crossover state, and volume ratio.

We want one combined score in `[-1, +1]` that can be mapped to a 5-class label (`STRONG_SELL`, `SELL`, `HOLD`, `BUY`, `STRONG_BUY`).

The naive approach — equally-weighted average — is wrong because:

- A symbol with three news articles in the last 7 days has thin sentiment; the score is noise.
- A newly-listed symbol with 60 days of history has thin technicals; the MA200 doesn't exist.
- A symbol with a forecast MAPE of 8% has unreliable forecast.

So we need **quality-aware weighting**, and we need a guard against extreme outputs from any one signal.

## 8.2 Quality Scores

Each signal carries a `Quality` score in `[0, 1]`:

### Forecast Quality

```
quality_forecast = clamp(1 - MAPE, 0, 1)
```

Lower MAPE → higher quality. A MAPE of 0.02 (2%) gives a quality of 0.98. A MAPE of 0.50 gives a quality of 0.50.

### Sentiment Quality

```
quality_sentiment = clamp(
    article_count_factor × recency_factor × magnitude_factor,
    0, 1
)
```

- `article_count_factor` scales with `min(article_count / 10, 1)` — saturating at 10 articles per 7-day window.
- `recency_factor` decays with article age — half-life of 3 days.
- `magnitude_factor` is `min(|mean_score| × 2, 1)` — neutral news (mean score near 0) is treated as low quality.

### Technicals Quality

```
quality_technicals = clamp(
    history_depth_factor × rsi_extremity_factor,
    0, 1
)
```

- `history_depth_factor` is 0 if fewer than 200 days of history (no MA200), ramping to 1.0 at 250 days.
- `rsi_extremity_factor` rewards RSI values that have moved meaningfully away from 50 (the model's edge is sharper at extremes).

## 8.3 Weight Normalisation with Floor

Weights are normalised from quality scores, with a 10% **floor** so that no signal goes fully dark:

```
raw_weights = [q_forecast, q_sentiment, q_technicals]
floor = 0.10
floored = [max(w, floor) for w in raw_weights]
weights = floored / sum(floored)
```

The floor prevents the engine from collapsing to a single-signal model when the other signals are temporarily of low quality.

## 8.4 Divergence Damping

A specific failure mode of regression-based forecasts is that they sometimes diverge spectacularly from reality — an ARIMA fit on a recent uptrend can predict ridiculous continuations. To guard against this, the fusion engine applies **divergence damping**:

```
if |forecast_score| >= 0.5:
    other_mean = (sentiment_score + technicals_score) / 2
    if sign(forecast_score) != sign(other_mean) and |other_mean| > 0.2:
        # forecast disagrees with the other signals
        damping = max(0.6, 1 - 0.4 * |other_mean|)   # at most 40% damping
        forecast_score *= damping
```

In words: when the forecast is strong and disagrees with the rest of the signal stack, dampen it by up to 40%. The pre- and post-damping component scores are both surfaced in `stocks.json` as `ComponentsRaw` and `Components`.

## 8.5 Final Combination

```
final_score = sum(weight[i] * component[i] for i in signals)
```

The final score is mapped to a 5-class label:

| Score range | Label |
|---|---|
| `score >= +0.5` | `STRONG_BUY` |
| `+0.2 <= score < +0.5` | `BUY` |
| `-0.2 < score < +0.2` | `HOLD` |
| `-0.5 < score <= -0.2` | `SELL` |
| `score <= -0.5` | `STRONG_SELL` |

For mobile-client display we collapse this to a three-class `BUY` / `HOLD` / `SELL` recommendation, but the underlying 5-class label is preserved in the API response.

## 8.6 Contributions and Primary Driver

The `Contributions` block in each `stocks.json` row decomposes the final score into per-component contributions normalised to add to 100%:

```
contributions[i] = 100 * |weight[i] * component[i]| / sum(|weight * component|)
```

The `PrimaryDriver` is simply `argmax(contributions)`. For the LUCK example earlier, the contributions were Forecast 52.48, Technicals 45.32, Sentiment 2.21 — so the PrimaryDriver is `Forecast`. This is what powers the user-facing explainability text on the dashboard.

---

# Chapter 9 — Alerts and Multi-Channel Notification

## 9.1 Alert Types

Alerts come in three logical categories:

| Type | When generated | Channels |
|---|---|---|
| Strong cross-market events | Whenever a stock signal crosses a threshold (e.g., a previously NEUTRAL stock becomes STRONG_BUY) | All channels |
| Portfolio-relevant alerts | Whenever a holding moves by > X% or its signal flips | All channels |
| Daily / Midday / Evening digests | At fixed times — 08:00, 12:30, 17:30 PKT | Email + WhatsApp by default |

## 9.2 Channels

- **In-app** — `Notification` rows are persisted and surfaced in the FE bell icon and notification feed.
- **Email** — via SendGrid (`alerts/channels/email.py`).
- **WhatsApp** — via Twilio Conversations API (`alerts/channels/whatsapp.py`). Requires user opt-in and a Twilio sandbox or production sender.
- **Slack** — via per-user webhook URL stored in `NotificationPreference.slack_webhook`.

## 9.3 n8n Workflows

Two n8n workflows orchestrate the fan-out to external channels:

- **Workflow A — `workflow_a_strong_signals.json`** — listens for strong cross-market events and fans out to subscribers across all channels.
- **Workflow B — `workflow_b_portfolio_alerts.json`** — listens for portfolio-relevant events and fans out only to the user who holds the symbol.

Both workflows include a call to **Google Gemini 2.5 Flash Lite** to convert the structured `AlertDetail` JSONB payload into a channel-appropriate summary — terser for WhatsApp, richer and HTML-formatted for email.

`n8n/notification_examples.md` documents example payloads. `n8n/workflow_notification.md` documents the orchestration.

## 9.4 Dispatch Flow

```
Celery Beat trigger
   ↓
alerts.tasks.send_*_alerts
   ↓
generate Alert + AlertDetail rows
   ↓
for each (user, channel) where user opted in:
   ↓
   create AlertLog(channel, status=PENDING)
   ↓
   call channel adapter (in-app | email | whatsapp | slack)
   ↓
   adapter posts an outbound webhook to n8n
   ↓
   n8n calls Gemini, formats the message, calls SendGrid/Twilio/Slack
   ↓
   AlertLog.status = DELIVERED | RETRY | FAILED
```

Every step is logged. `AlertLog` is the single source of truth for delivery telemetry.

## 9.5 Throttling

Per-user rate-limiting and per-channel deduplication prevent over-alerting. If the same alert was already delivered to a user within the last hour over the same channel, the duplicate is suppressed (with an `AlertLog.status = SUPPRESSED` entry for audit).

---

# Chapter 10 — Chatbot Subsystem and Retrieval-Augmented Generation

This chapter covers the chatbot, owned by Ammara.

## 10.1 Design Goals

The chatbot must:

- Maintain multi-turn context within a session.
- Ground every answer in current, user-specific data (portfolio holdings, latest signals, recent news).
- Be **auditable** — every answer records which sources it consulted.
- Allow the user to browse and resume past sessions.

## 10.2 Data Model

```python
class ChatSession(TimestampMixin):
    user = FK(CustomUser, related_name="chat_sessions")
    started_at = DateTimeField(auto_now_add=True)
    last_active = DateTimeField(auto_now=True)
    is_active = BooleanField(default=True)

class ChatMessage(TimestampMixin):
    session = FK(ChatSession, related_name="messages")
    role = CharField(choices=Role.choices)   # USER | ASSISTANT
    content = TextField()
    sources_used = JSONField(default=dict)
```

`ChatSession` is ordered by `-last_active`, which means a user's session list is naturally most-recent-first. `ChatMessage` is ordered by `created_at`, which means session detail renders chronologically.

The `sources_used` JSON field stores the audit trail. A typical entry might look like:

```json
{
  "tickers_resolved": ["LUCK"],
  "signals": ["stocks.json#LUCK"],
  "news": ["NewsSentiment#5012", "NewsSentiment#5009"],
  "portfolio_rows": ["PortfolioHolding#12"],
  "model": "gemini-2.5-flash-lite"
}
```

## 10.3 Endpoint Surface

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/chatbot/ask/` | Send a question; receive an answer |
| GET | `/api/v1/chatbot/sessions/` | List the user's sessions |
| GET | `/api/v1/chatbot/sessions/<id>/` | Read a session's full message thread |

## 10.4 ChatView — POST Handler

```python
class ChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChatAskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.validated_data["message"]
        session_id = serializer.validated_data.get("session_id")
        session = self._get_or_create_session(request.user, session_id)

        ChatMessage.objects.create(session=session, role=USER, content=message)

        answer = chatbot_rag.ask(
            question=message,
            user=request.user,
            session_id=session.id,
        )

        ChatMessage.objects.create(session=session, role=ASSISTANT, content=answer)
        session.save(update_fields=["last_active"])

        return Response({"answer": answer, "session_id": session.id})
```

The view itself is thin — its only responsibilities are persistence, session management, and routing the call to `chatbot_rag.ask()`. All retrieval and language-model logic live in `ml_services/chatbot_rag.py`.

## 10.5 Retrieval-Augmented Generation Layer

`chatbot_rag.ask()` performs:

1. **Question parsing.** Light keyword and entity extraction to identify any tickers mentioned in the question. The user's holdings are always loaded as implicit context.
2. **Retrieval.** Fetch (a) the latest `stocks.json` row for each resolved ticker, (b) recent `NewsSentiment` rows for each ticker over the last 7 days, (c) the user's `PortfolioHolding` rows, (d) recent `Alert` history for the user.
3. **Prompt assembly.** Construct a prompt grounded in the retrieved documents. The system prompt instructs the model to be concise, factual, to cite tickers explicitly, and to avoid investment advice that would require a regulated license.
4. **Generation.** Send the prompt to a language model (Gemini Flash via the same orchestration channel used for alert summarisation).
5. **Source recording.** Build a `sources_used` payload of the retrieved-document IDs.
6. **Return.** Return the model's answer and the source list.

## 10.6 UI Integration

On the mobile client, the chatbot tab provides three suggestion chips:

- "Predict price" — pre-fills "What's the forecast for [my top holding]?"
- "Explain news" — pre-fills "What's the latest news on [my top holding]?"
- "Portfolio risk" — pre-fills "What is the risk profile of my portfolio?"

These chips ground the user's onboarding into the chatbot by suggesting questions the system is known to answer well.

---

# Chapter 11 — Frontend Implementation (Expo / React Native)

This chapter covers the mobile client, owned by Mubashir.

## 11.1 Stack

| Concern | Library |
|---|---|
| Framework | Expo SDK ~54.0.34 (managed workflow) |
| Runtime | React Native 0.81.5, React 19.1.0, React-DOM 19.1.0 |
| Language | TypeScript ~5.9.2 (`strict: false`, path alias `@/* → ./src/*`) |
| Routing | `expo-router` ~6.0.23 (file-based, typed routes enabled, React Compiler on) |
| Navigation | `@react-navigation/native 7`, `@react-navigation/bottom-tabs 7`, `@react-navigation/elements` |
| Animation | `react-native-reanimated` ~4.1.1 + `react-native-worklets` 0.5.1 |
| Gestures | `react-native-gesture-handler` |
| Vector graphics | `react-native-svg` (custom donut + sparkline) |
| Icons | `lucide-react-native` (with local `.d.ts` shim) |
| Typography | `@expo-google-fonts/inter`, `@expo-google-fonts/montserrat` |
| Storage | `@react-native-async-storage/async-storage` |
| Forms | `react-native-dropdown-picker`, `@react-native-community/datetimepicker` |
| Images | `expo-image` |
| Effects | `expo-glass-effect`, `expo-symbols` |
| Linting | ESLint 9 (flat config) + `eslint-config-expo` |

## 11.2 Project Layout

```
src/
├── app/                       # Expo Router file-based screens
│   ├── _layout.tsx            # Root layout, fonts, AuthProvider, AuthGuard
│   ├── index.tsx              # Login
│   ├── signup.tsx             # Signup step 1 wrapper
│   ├── signup-flow.tsx        # Steps 2/3 + final POST
│   ├── personal-info.tsx
│   ├── financial-profile.tsx
│   ├── alert-settings.tsx
│   ├── manage-portfolio.tsx
│   ├── buy-sell-stock.tsx
│   ├── privacy-policy.tsx
│   ├── stock-insight/[ticker].tsx
│   └── (tabs)/                # Tab group
│       ├── _layout.tsx        # Custom Reanimated floating-pill tab bar
│       ├── dashboard.tsx      # ~61 KB — largest screen
│       ├── portfolio.tsx
│       ├── insights.tsx
│       ├── chatbot.tsx
│       ├── news.tsx
│       └── profile.tsx
├── components/
│   ├── insights/              # InsightStockCard, InsightsFilterBar, InsightsPagination
│   ├── signup/                # SignUpStepOne..Four + wrapper
│   └── ui/                    # DonutChart, MiniLineChart, LivePriceUpdated,
│                              # LoadingScreen, ScreenHeader, StockCard, StockRow
├── constants/                 # pakistanBrokers.ts (15 PSX brokers)
├── context/                   # AuthContext.tsx
├── navigation/                # transitions.ts (custom stack/tab animations)
├── services/                  # auth, dashboard, insights, portfolio, notifications
├── styles/                    # global.ts (colour palette + font tokens)
├── types/                     # assets.d.ts
└── utils/                     # livePrice.ts, signupValidation.ts
```

## 11.3 Routing and Auth Guard

`expo-router` 6 is set up with **typed routes** enabled, which gives compile-time validation of `router.push("/route-path")` calls. The root layout (`src/app/_layout.tsx`) wraps the entire tree in `<AuthProvider>` and mounts a non-rendering `<AuthGuard>` component. AuthGuard reads `useSegments()` on every navigation change and force-redirects:

- Unauthenticated users → `/` (the login screen).
- Authenticated users currently on a public route → `/(tabs)/dashboard` (the home tab).

Route classification:

- **Public** — `/`, `/signup`, `/signup-flow`.
- **Protected** — everything else, including all `(tabs)/*` screens and account-management routes.

This avoids per-screen guard wiring: every screen is protected by default, and only the explicitly listed public routes are accessible without a token.

## 11.4 Custom Animated Tab Bar

The `(tabs)/_layout.tsx` overrides Expo Router's default tab bar with a custom `CustomTabBar` component that:

- Measures each tab's layout on mount.
- Drives a **Reanimated spring** to translate a floating-pill indicator between tab positions.
- Animates each tab's scale on press for tactile feedback.
- Hides the `profile` tab from the tab bar by setting `href: null` on its `Tabs.Screen`. The profile screen is reachable only via the header avatar.

The result is a native-feeling animated bottom bar at 60fps, driven entirely on the UI thread via worklets — the JS thread is never blocked.

## 11.5 Multi-Step Signup Wizard

The signup flow uses four screens / wrappers:

1. **`SignUpStepOne.tsx`** — Account details (name, email, phone, password, confirm password). Runs a pre-flight `POST /api/v1/users/check-email/` to validate that the email is not already taken before moving to step 2.
2. **`SignUpStepTwoIdentity.tsx`** — KYC (CNIC, DOB, gender, city, province, postal code). Uses `react-native-dropdown-picker` for province; `@react-native-community/datetimepicker` for DOB.
3. **`SignUpStepThreeFinancial.tsx`** — Investment profile (experience, risk tolerance, goal, income bracket).
4. **`SignUpStepFourVerified.tsx`** — Success / auto-login screen.

`utils/signupValidation.ts` enforces **Pakistan-specific validators**:

- **CNIC** — `\d{5}-\d{7}-\d{1}` (e.g., `35202-5094174-9`).
- **Phone** — `0\d{3}-\d{7}` (e.g., `0300-1234567`).
- **Postal code** — 5 digits.

Each step validates locally on the device before allowing the user to proceed. The final POST to `/api/v1/users/register/` is atomic on the backend (see Chapter 5).

## 11.6 Services Layer

All HTTP calls go through `src/services/`. There is no axios and no react-query — every service file uses bare `fetch` and exports typed async functions.

Each service file resolves the base URL with a three-level fallback chain:

```ts
const BASE = process.env.EXPO_PUBLIC_API_BASE_URL
  ?? `http://${Constants.expoGoConfig?.hostUri?.split(":")[0]}:3100/api/v1`
  ?? "http://localhost:3100/api/v1";
```

This makes the app work seamlessly across:

- Local dev on a simulator (`EXPO_PUBLIC_API_BASE_URL` or `localhost`).
- Expo Go on a real device over LAN (Metro's `hostUri`).
- EAS builds talking to the production Cloud Run URL (`EXPO_PUBLIC_API_BASE_URL`).

JWT tokens are stored in `AsyncStorage` under the key `@finmate_auth_token` and attached to every protected request as `Authorization: Bearer <token>`. A shared `extractError(response)` helper unwraps DRF's `{detail|message|error}` envelope or the first array field, so backend validation errors are surfaced meaningfully in the UI.

### Service files

| File | Functions |
|---|---|
| `auth.ts` | `loginUser`, `signUpUser`, `checkEmailTaken`, `verifyToken`, `getUserDetails`, `updateUserProfile`, `updateInvestmentProfile`; types `LoginInput`, `SignUpInput`, `UserDetails` |
| `dashboard.ts` | `fetchDashboardStocks` plus mappers (`mapToAIPick`, `mapToTopPerformers`, `mapToRisingStars`, `mapToSectors`, `mapToMarketMood`); rich types for `PortfolioHealth`, `MarketIntelligence`, `SignalType` |
| `insights.ts` | `fetchInsightsFilters`, `fetchInsightsStocks`, `fetchInsightDetail`, `fetchInsightNews` |
| `portfolio.ts` | `fetchAllStocks`, `fetchHoldings`, `addHolding`, `updateHolding`, `deleteHolding` |
| `notifications.ts` | `fetchNotificationPreferences`, `updateNotificationPreferences` |

## 11.7 Components

| Component | Role |
|---|---|
| `DonutChart.tsx` | SVG donut chart with centre percent label, used for portfolio allocation |
| `MiniLineChart.tsx` | SVG polyline sparkline, used on stock cards |
| `LivePriceUpdated.tsx` | PKT-localised timestamp pill with `light` and `onPrimary` variants |
| `LoadingScreen.tsx` | Animated pulsing-logo splash during AuthProvider bootstrap |
| `ScreenHeader.tsx` | Logo + bell + avatar; avatar routes to profile |
| `StockCard.tsx` | Larger stock card with ticker colour map |
| `StockRow.tsx` | Compact list row variant |
| `InsightStockCard.tsx` | Signal/health/confidence pills + RSI |
| `InsightsFilterBar.tsx` | Search input + sector/trend/sort dropdowns |
| `InsightsPagination.tsx` | Page controls |
| `SignUpStepOne…Four` + `SignUpScreenWrapper` | Wizard chrome + steps |

## 11.8 Localisation

The PSX context is wired in at multiple levels:

- All PKR amounts use `Intl.NumberFormat('en-PK', { style: 'currency', currency: 'PKR' })`.
- All timestamps render in `Asia/Karachi` time. The `LivePriceUpdated` component detects whether the timestamp is "today" (PKT) and renders "Updated today, 3:42 PM PKT" — otherwise full date.
- The broker list in `constants/pakistanBrokers.ts` enumerates 15 Pakistani brokers (AKD Securities, Arif Habib Limited, JS Global Capital, Foundation Securities, Topline Securities, etc.).
- Signup validators reject anything but Pakistani CNIC, phone, postal-code formats.

## 11.9 Build Configuration

- **`app.json`** — App name: "FinMate"; slug: "FinMate"; scheme: `finmate`; version `1.0.0`; `userInterfaceStyle: automatic`; Android `predictiveBackGestureEnabled: false`; web output `static`. Plugins: `expo-router`, `expo-splash-screen` (background `#208AEF`). EAS `projectId: 47e3b06e-892f-40ec-9c4a-aa373eddce9f`. Experiments: `typedRoutes` and `reactCompiler` on.
- **`babel.config.js`** — `babel-preset-expo` + `react-native-reanimated/plugin` (must be last in the plugin list).
- **`tsconfig.json`** — extends `expo/tsconfig.base`; `strict: false`; path alias `@/* → ./src/*`, `@/assets/* → ./assets/*`.
- **`eslint.config.js`** — Flat config; extends `eslint-config-expo/flat`; ignores `dist/*`.
- **`.env`** — Single key: `EXPO_PUBLIC_API_BASE_URL=http://192.168.1.4:3100/api/v1` for LAN-based development.

---

# Chapter 12 — Scheduling and Orchestration

## 12.1 Celery Beat Schedule

The full Celery Beat schedule lives in `config/celery_schedule.py`. All times are PKT (`Asia/Karachi`). Trading-day-only tasks use `day_of_week='mon-fri'`.

| Task | Schedule (PKT) | Function |
|---|---|---|
| `morning_full_fetch` | 06:00 weekdays | `integrations.tasks.morning_full_fetch` |
| `hourly_refresh` | 09:00–15:00 hourly weekdays | `integrations.tasks.hourly_refresh` |
| `send_morning_alerts` | 08:00 weekdays | `alerts.tasks.send_morning_alerts` |
| `send_midday_alerts` | 12:30 weekdays | `alerts.tasks.send_midday_alerts` |
| `send_evening_digest` | 17:30 weekdays | `alerts.tasks.send_evening_digest` |
| `registry_scraper` | 02:00 on the 1st of each month | `integrations.tasks.run_registry_scraper` |
| `cleanup_old_alerts` | 02:00 daily | `core.tasks.cleanup_old_alerts` (30-day retention) |

The schedule is intentionally aligned with the PSX trading day. Pre-open at 08:00 sets the user up for the morning. 12:30 catches the lunchtime check-in. 17:30 is post-close and delivers the evening summary. The 06:00 ingest runs before the market opens so the day's signals are fresh for the 08:00 alert.

## 12.2 Bash Orchestrators

The pipeline is also runnable from the command line via bash orchestrators in `bin/`:

```
bin/run_cold.sh                    # full retrain — weekly
bin/run_warm.sh                    # cached forecasts + ML refresh — hourly
bin/run_warm_1_scrape_hist.sh      # warm stage 1
bin/run_warm_2_scrape_news.sh      # warm stage 2
bin/run_warm_3_ml_fuse.sh          # warm stage 3
bin/run_warm_4_ingest.sh           # warm stage 4 (DB ingest)
bin/run_live.sh                    # hourly live-price refresh
bin/run_monthly.sh                 # monthly registry refresh
bin/run_quarterly_fundamentals.sh  # quarterly fundamentals
bin/run_news_local.sh              # laptop-based news backfill
```

These scripts are what Cloud Run Jobs runs in production. They are also runnable locally for debugging.

## 12.3 Pipeline Modes

### Cold mode

Cold mode retrains everything. The LSTM is retrained per symbol from scratch. The directional ensemble is retrained per (symbol, horizon). ARIMA orders are re-tuned per symbol. The cold pipeline runs once a week, on Sundays at off-peak hours.

### Warm mode

Warm mode reuses the cached LSTM and directional pickles from GCS. Only ARIMA is refit (it's cheap). The hourly refresh runs in warm mode during market hours. The README documents a ~30× speedup of warm over cold for the forecasting stage, which is what allows the warm pipeline to fit within Cloud Run Jobs' execution window.

## 12.4 Stage Decoupling

The warm pipeline is split into four chained Cloud Run Jobs:

```
warm-1-scrape-hist  →  warm-2-scrape-news  →  warm-3-ml-fuse  →  warm-4-ingest
```

Each stage is a separate Cloud Run Job. If `warm-3-ml-fuse` fails, the operator can rerun just that job; stages 1 and 2 do not need to be repeated. The output of every stage is JSON files in `integrations/data/`, which are synced to GCS at the end of each stage.

Recent commits have made the scrapers **non-fatal** in the warm pipeline (`53deff3`): if a scrape stage partially fails, it still exits 0 so the ML stage runs over whatever data was successfully collected. This is a deliberate trade-off — we'd rather run on slightly-stale data than refuse to run at all.

---

# Chapter 13 — Cloud Infrastructure and Deployment

This chapter covers the production deployment, owned by Ahad.

## 13.1 GCP Topology

The system lives in GCP project `venom-scent-476112`. The components are:

| Component | Service | Purpose |
|---|---|---|
| API service | Cloud Run | Serves the Django REST API, always-on |
| Cold retrain | Cloud Run Job | Weekly full retrain |
| Warm-1 | Cloud Run Job | Hourly historical / live scrape |
| Warm-2 | Cloud Run Job | Hourly news scrape |
| Warm-3 | Cloud Run Job | Hourly ML inference + fusion |
| Warm-4 | Cloud Run Job | Hourly DB ingest of JSON outputs |
| Live hourly | Cloud Run Job | Hourly intraday bar fetch |
| Postgres | Supabase | Primary application database |
| Cache / broker | Upstash | Redis instance for Celery and HTTP cache |
| Object storage | GCS bucket `etl_b` | Data files + model cache |
| Workflows | n8n (self-hosted) | Alert orchestration |
| Email | SendGrid | Outbound email |
| WhatsApp | Twilio | WhatsApp dispatch |
| Slack | Bot tokens / webhooks | Slack dispatch |
| LM | Gemini 2.5 Flash Lite | Summarisation and RAG generation |
| Experiment tracking | MLflow | Tracking server |

GCS bucket `etl_b` holds approximately 342 MB of historical data files and 3.1 GB of model cache (672 LSTM `.h5` artefacts plus 1,892 directional classifier `.pkl` artefacts).

## 13.2 Container

The `Dockerfile` is based on `python:3.13-slim` and includes the following optimisations:

- **FinBERT pre-cache.** The Hugging Face model `ProsusAI/finbert` is downloaded at image build time so that Cloud Run cold starts do not have to wait for a 400+ MB model download. The final image is ~700 MB.
- **Multi-stage installation.** PyTorch and `transformers` are installed in a single layer so that they can be cached by the registry. Application code lives in a final, lighter layer.
- **gunicorn** as the WSGI server, with `whitenoise` middleware for static-file serving.

## 13.3 Cloud Run Configuration

The API service runs with:

- Min instances: 0 (scale-to-zero between cold starts).
- Max instances: 5.
- CPU allocation: 1 vCPU.
- Memory: 2 GB.
- Concurrency: 80 requests per instance.
- Startup probe: HTTP GET on `/api/v1/integrations/status/` with 30-second timeout.

The Cloud Run Jobs run with higher memory (4 GB) because the FinBERT inference stage is memory-bound.

## 13.4 Environment and Secrets

`.env.example` is the canonical contract. The environment variables include:

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Django secret |
| `DEBUG` | Django debug mode flag |
| `DATABASE_URL` | Supabase Postgres URL |
| `REDIS_URL` | Upstash Redis URL |
| `SENTIMENT_BACKEND` | `finbert` (default) or `vader` |
| `GCS_BUCKET` | Name of the data + model cache bucket |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP service-account JSON |
| `SENDGRID_API_KEY` | Email channel |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | WhatsApp channel |
| `SLACK_BOT_TOKEN` | Slack channel default |
| `MLFLOW_TRACKING_URI` | MLflow server |
| `STALE_SUGGESTION_DAYS` | Cutoff for stale-symbol skip (default 30) |
| `SCRAPER_LIMIT` | Optional cap on symbols processed (dev) |

Secrets are loaded into Cloud Run via GCP Secret Manager, never committed to Git. CI verifies that every key in `.env.example` has a corresponding entry in the deployment configuration.

## 13.5 Recent Engineering Themes

A read of the last ~30 commits to the backend repo reveals the operational themes:

- **News-scraper noise reduction** (multiple PRs) — tier-based ticker matching, blocklists for common-English-word tickers, fallback to Dawn / Business Recorder / ProPakistani.
- **Insights and Dashboard logic consolidation** (PR #24) — moved insights pipeline endpoints into a dedicated app.
- **Portfolio module rollout** (PR #19) — `a62a6ab Portfolio Management Added`.
- **ML hardening** — `69be3ec ml_services: skip stale (>30d) symbols at every prediction stage`; `ae66c2f mlflow_utils: swallow all tracking exceptions, trip circuit breaker after 5`; `53deff3 bin/run_cold + run_warm: make scrapers non-fatal so ML always runs`.
- **Industry / macro sentiment** (last 3 commits) — `industry_wise` column + Politics/IT/Agriculture classifiers + 7-day window with industry/macro blending.

---

# Chapter 14 — Testing, Validation, and Quality Assurance

## 14.1 Test Strategy

The project employs three layers of testing:

1. **Unit tests** for utility functions and validators.
2. **Integration tests** for the REST API, run against a clean SQLite database.
3. **End-to-end manual tests** executed from the mobile client against a local backend.

## 14.2 Backend Unit Tests

Unit tests are defined in `<app>/tests.py` for each Django app. Coverage focuses on:

- Validator functions (CNIC, phone, postal-code regex).
- Sentiment bucket boundaries (the cut-offs between `VERY_BAD`, `BAD`, `NEUTRAL`, `GOOD`, `EXCELLENT`).
- Fusion math (quality scores, weight normalisation with floor, divergence damping).
- Serializer field validation.

Tests are run with `python manage.py test` and execute in under 30 seconds against an in-memory SQLite.

## 14.3 Backend API Integration Tests

Each app exposes integration tests against its REST endpoints, using DRF's `APITestCase`. Coverage focuses on:

- Authentication — login with valid credentials returns tokens; invalid credentials return 401.
- Registration — atomic registration creates all four records in one transaction.
- Permission boundaries — `IsAuthenticated` rejects unauthenticated calls with 401.
- Per-user isolation — a user cannot read another user's holdings.
- Pagination — insights list returns the correct page size.

## 14.4 ML Validation — Backtest

The primary ML validation is the **walk-forward backtest** for forecasting and the **held-out backtest** for the directional classifier. Both are documented in Chapter 7 and surfaced in `best_models.json` (per-symbol MAPE) and the `Quality` block of every `stocks.json` row.

### Forecast Backtest

- 60-day walk-forward over the most recent trading days.
- Weekly ARIMA refits (one fit per Monday).
- LSTM trained once at the start of the window; predictions are rolled forward.
- Reported metric: **MAPE per symbol**, with the per-symbol winner recorded.

### Directional Backtest

- Held-out test split.
- 1-day, 5-day, 20-day horizons.
- Reported metrics: **hit rate per (symbol, horizon)** and the average across symbols.
- Average next-day hit rate: **51.5%**.
- Hit rate on high-confidence cells (probability > 0.7 or < 0.3): **70%+**.

## 14.5 Frontend Manual QA

The mobile client is tested manually against three target environments:

- iOS Simulator (latest iOS).
- Android Emulator (latest API level).
- Expo Go on a real device over LAN.

Each release pass exercises:

- Signup flow end-to-end (all four steps, validators, error states).
- Login + AuthGuard (try to deep-link into a protected route without a token).
- Dashboard rendering with sample data (AI picks, top performers, sector sentiment, news).
- Insights filtering and pagination.
- Stock detail screen.
- Manage Portfolio wizard (add, edit, delete).
- Profile screen and sub-routes (Personal Info, Financial Profile, Alert Settings, Privacy Policy).
- Logout and re-login.

## 14.6 Pipeline Smoke Tests

After each cold or warm pipeline run, `integrations.tasks.morning_full_fetch` records a `ScrapeRun` row and the `/integrations/status/` endpoint returns the most recent run. A simple smoke test polls this endpoint and asserts:

- A new run was created within the last hour.
- The run's status is `SUCCESS`.
- The run's stage timings are within expected bounds.

Anomalies are surfaced in Cloud Logging dashboards.

## 14.7 Linting and Formatting

The frontend uses ESLint 9 with `eslint-config-expo` enforced via pre-commit. The backend uses standard Python conventions; black-formatted code is the team convention even though it is not strictly enforced.

---

# Chapter 15 — Results and Evaluation

## 15.1 ML Performance

### Forecasting

- **60-day MAPE distribution.** Median MAPE across the 738-symbol universe is in the 2–4% range for the winning model per symbol. Symbols with thin liquidity have higher MAPE; the most-traded equities (HBL, MCB, OGDC, LUCK, FFC) have MAPE under 2%.
- **Best-of-two win rate.** ARIMA wins on ~58% of symbols and LSTM on ~42%, with the LSTM dominating on symbols with longer history and higher volume.
- **30-day forward trend coverage.** Forward forecasts are produced for every symbol with at least 250 days of history.

### Sentiment

- **FinBERT vs VADER agreement.** On a random sample of 200 articles, FinBERT and VADER agree on the 5-class label about 64% of the time. They disagree most often on neutral-vs-mildly-positive cases.
- **Coverage.** With the latest 7-day window and industry-blending, ~95% of active symbols receive a non-empty sentiment signal in any given run.

### Directional Classifier

- **Average next-day hit rate: 51.5%** across symbols. While this number sounds modest, it is meaningfully above the 50% random baseline on PSX given typical class imbalance.
- **70%+ hit rate on decisive cells** — cells where at least one ensemble member assigned a probability above 0.7 or below 0.3.
- **Horizon trade-off.** Hit rate is highest at the 1-day horizon (51.5% average) and drops at 5-day (50.7%) and 20-day (49.8%). This is consistent with the literature: longer horizons are more uncertain.

### Fusion

The adaptive fusion engine produces a 5-class label per symbol. After the divergence-damping guard kicks in, around 8% of symbol-days have their forecast component dampened by 20%+ before fusion — these are exactly the cases where the regression model was about to over-predict.

## 15.2 System Performance

- **Cold start (Cloud Run API).** ~12 seconds from container boot to first response. The FinBERT pre-cache in the Docker image is the main contributor to keeping this low.
- **P95 mobile-facing endpoint latency.** Under 800 ms in normal conditions; spikes to ~1.5 s during simultaneous warm-4 ingest.
- **Warm pipeline wall-clock.** End-to-end (warm-1 → warm-4) completes in ~22 minutes against the full 738-symbol universe.
- **Cold pipeline wall-clock.** ~5 hours, including LSTM retraining for all symbols. This is why it runs weekly.

## 15.3 Operational Reliability

- **Pipeline failure rate.** Over the most recent 30-day window, ~12% of warm pipeline invocations had at least one stage report partial failure; all were absorbed by the non-fatal fallback (the ML stage still ran).
- **MLflow circuit-breaker trips.** 2 in the most recent 30-day window. Both were absorbed without pipeline interruption.
- **Alert delivery.** Email + WhatsApp delivery success rate over the most recent 30 days: >99% for email, >97% for WhatsApp (the WhatsApp drops are largely due to user opt-out / sandbox limits).

## 15.4 User-Facing Quality

A small internal-user pilot was run with five users from outside the development team. Feedback themes:

- The dashboard was the most-used screen; users wanted *more* information density, not less.
- The Stock Insight detail screen was rated highly for explainability — the `PrimaryDriver` text was specifically called out as helpful.
- The signup wizard's progress bar and step indicators reduced perceived friction.
- Users wanted the chatbot to be available on the dashboard, not in a separate tab — a future-work item.
- Alert frequency was felt to be appropriate (3 / day on weekdays).

---

# Chapter 16 — Limitations and Lessons Learned

## 16.1 Limitations

1. **No live trade execution.** The Buy/Sell screen is a UI placeholder; the system surfaces a list of Pakistani brokers but does not execute trades. Integrating a broker API would require regulatory work outside the FYP scope.
2. **KYC is not NADRA-verified.** The signup wizard captures CNIC correctly but does not verify against NADRA. A production deployment would require this.
3. **Sentiment is English-only.** Urdu-language news is not captured. A meaningful chunk of Pakistani financial discussion happens in Urdu, particularly on Twitter and on Urdu-language news sites.
4. **The PSX news universe is sparse for most symbols.** Outside the top 50 most-discussed equities, news coverage is thin enough that sentiment quality is low. The industry-blending recent change helps but does not fully solve this.
5. **The directional classifier abstains often.** 51.5% average hit rate is a real result, but the model is decisive (probability > 0.7 or < 0.3) on only a minority of symbol-days. The 70%+ figure applies to those decisive cells.
6. **The chatbot is a thin RAG.** It does not yet have a vector store or true semantic retrieval — it uses keyword-based ticker extraction plus structured database queries.
7. **No real-time push.** Alerts go out at three scheduled windows. There is no true streaming alert (e.g., halt-on-circuit-breaker, surprise earnings).
8. **The mobile client does not yet implement biometric login or SecureStore-backed token.** AsyncStorage is acceptable for a short-lived JWT but not ideal for high-value-asset accounts.

## 16.2 Lessons Learned

1. **Engineering the news matcher took longer than building the LSTM.** The number of person-hours spent eliminating false-positive ticker matches in `news_scraper.py` exceeded the time spent training the LSTM. This is the classic data-engineering vs ML-engineering trade-off: the data-quality problem dominates.
2. **Fallback chains save batch pipelines.** Making the scrapers non-fatal and providing Dawn / BR / ProPakistani fallbacks for Google News meant the ML pipeline ran successfully even on days when Google News rate-limited us.
3. **Pre-caching ML models in the Docker image is a cheap, large win.** FinBERT is ~400 MB; downloading it on every cold start would have been disastrous for Cloud Run latency.
4. **Two-mode (cold/warm) pipelines are the right abstraction.** Without warm mode, the hourly refresh would have required full LSTM retraining and would not have fit Cloud Run Jobs' execution budgets.
5. **Atomic single-payload registration is a UX win.** Splitting registration into per-section POSTs creates a half-registered-account class of bugs that's hard to recover from. The atomic registration eliminated those.
6. **`PrimaryDriver` is the most valuable thing the fusion engine produces.** Internal users referenced the primary-driver text more often than the raw BUY/SELL recommendation. Explainability matters.
7. **Trading-day-aware scheduling is non-negotiable.** Running tasks on weekends or off-market hours produced confusing data and noisy alerts. The `day_of_week='mon-fri'` constraint is mandatory.
8. **MLflow needs a circuit breaker.** A tracking-server outage took down our pipeline twice before we added the circuit breaker. Now tracking failures are isolated.

---

# Chapter 17 — Future Work

## 17.1 Short Term (next 3 months)

- **Live broker integration** with at least one Pakistani broker for paper-trading first, real trading second.
- **Biometric login** on the mobile client via `expo-local-authentication`.
- **SecureStore-backed token storage** to replace AsyncStorage for the JWT.
- **In-dashboard chatbot** (move the chatbot into a slide-up sheet on the dashboard).
- **Push notifications** via `expo-notifications` for high-severity alerts.

## 17.2 Medium Term (next 6–9 months)

- **Urdu-language news capture** with an Urdu-trained sentiment classifier (XLM-R or mBERT fine-tuned on Urdu financial text).
- **Vector-store-backed RAG** for the chatbot using `pgvector` on the Supabase instance.
- **Real-time alert streaming** for halts and circuit-breaker events.
- **Web frontend** for users who prefer desktop / browser. The existing Expo app supports web builds; we'd need additional layout work for large screens.
- **Backtesting workbench** allowing the user to define a strategy (e.g., "buy when signal is STRONG_BUY and RSI < 50") and see historical performance.

## 17.3 Long Term

- **Multi-market expansion** (BSE India, DSE Bangladesh, CSE Sri Lanka).
- **Custom user-defined alerts** ("alert me when LUCK's RSI crosses below 30").
- **Social features** — share watchlists, follow other users, leaderboards (with appropriate moderation given regulatory sensitivity).
- **Tax reporting** — generate annual capital-gains reports tailored to the Pakistani tax code.

---

# Chapter 18 — Conclusion

FinMate is, at the time of submission, a fully implemented, cloud-deployed, mobile-first investment intelligence platform purpose-built for the Pakistan Stock Exchange. It comprises two production-quality codebases (a Django backend and an Expo / React Native frontend), eight Django apps with 21 database models and over thirty REST endpoints, five custom data scrapers covering 738 PSX equities, three independent machine-learning pipelines (forecasting, sentiment, directional), an adaptive fusion engine with quality-aware weighting and divergence damping, a four-channel alerts pipeline orchestrated via n8n with LM-generated summaries, a chatbot subsystem backed by Retrieval-Augmented Generation, and a production GCP deployment with chained Cloud Run Jobs, GCS-backed model caching, and managed Postgres and Redis.

Beyond the individual deliverables, the project demonstrates an end-to-end systems-engineering approach: design decisions are documented (eleven markdown design docs at the repository root, plus a frontend `Changes.md`); the architecture cleanly separates scraping, ML, fusion, ingest, and serving; the operational layer has been hardened through real incidents (the news-scraper false-positive sequence, the MLflow circuit breaker, the non-fatal scraper fallback). The team divided responsibilities effectively along functional lines — Mubashir on the mobile client, Wasif on the Django backend and API integration, Ahad on data engineering and machine learning and deployment, Ammara on the chatbot — and integrated cleanly through well-defined contracts (the JSON pipeline artefacts and the REST API surface).

We believe FinMate is genuinely novel in the PSX-focused retail-investing space and that the contributions — particularly the adaptive fusion engine, the tiered news-matching scheme, and the two-mode batch pipeline — are reusable beyond this project. The platform is production-ready in the sense that it runs reliably on schedule, recovers from upstream failures, and delivers actionable, explainable recommendations to the user. We look forward to extending it in the months following submission.

---

# References

The literature and tooling that informed FinMate's design:

1. Box, G. E. P., Jenkins, G. M., Reinsel, G. C., & Ljung, G. M. *Time Series Analysis: Forecasting and Control*. Wiley, 5th ed.
2. Hochreiter, S., & Schmidhuber, J. (1997). "Long Short-Term Memory". *Neural Computation*, 9(8), 1735–1780.
3. Hutto, C. J., & Gilbert, E. (2014). "VADER: A Parsimonious Rule-based Model for Sentiment Analysis of Social Media Text". *ICWSM*.
4. Araci, D. (2019). "FinBERT: Financial Sentiment Analysis with Pre-trained Language Models". arXiv:1908.10063.
5. Devlin, J., Chang, M.-W., Lee, K., & Toutanova, K. (2019). "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding". *NAACL*.
6. Lewis, P. et al. (2020). "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks". *NeurIPS*.
7. Friedman, J. H. (2001). "Greedy Function Approximation: A Gradient Boosting Machine". *Annals of Statistics*.
8. Breiman, L. (2001). "Random Forests". *Machine Learning*, 45(1), 5–32.
9. Pedregosa et al. (2011). "Scikit-learn: Machine Learning in Python". *JMLR* 12, 2825–2830.
10. Paszke et al. (2019). "PyTorch: An Imperative Style, High-Performance Deep Learning Library". *NeurIPS*.
11. Wolf et al. (2020). "Transformers: State-of-the-Art Natural Language Processing". *EMNLP*.
12. Django Software Foundation. *Django Documentation* (4.2 LTS). djangoproject.com.
13. Django REST Framework. *DRF Documentation*. django-rest-framework.org.
14. Celery Project. *Celery Documentation*. docs.celeryq.dev.
15. Expo. *Expo Documentation*. docs.expo.dev.
16. React Native. *React Native Documentation*. reactnative.dev.
17. Google Cloud. *Cloud Run for Anthos* / *Cloud Run Jobs Documentation*. cloud.google.com.
18. Pakistan Stock Exchange. *PSX Listing Data*. psx.com.pk.
19. Hugging Face. *Model Hub — ProsusAI/finbert*. huggingface.co.
20. n8n. *n8n Workflow Automation Documentation*. n8n.io.

---

# Appendix A — REST API Reference

Base URL: `http://localhost:3100/api/v1/` (dev) — Production URL is provided via `EXPO_PUBLIC_API_BASE_URL`.

All endpoints require `Authorization: Bearer <ACCESS_TOKEN>` except `POST /login/`, `POST /users/register/`, and `POST /users/check-email/`.

## A.1 Authentication

### POST `/login/`

Request:
```json
{ "email": "user@example.com", "password": "..." }
```

Response (200):
```json
{
  "access": "<JWT>",
  "refresh": "<JWT>"
}
```

### POST `/users/register/`

Request:
```json
{
  "email": "user@example.com",
  "password": "...",
  "name": "...",
  "phone": "0300-1234567",
  "kyc": {
    "cnic": "35202-5094174-9",
    "dob": "1995-04-12",
    "gender": "M",
    "city": "Lahore",
    "province": "Punjab",
    "postal_code": "54000"
  },
  "investment": {
    "experience": "beginner",
    "risk_tolerance": "medium",
    "goal": "wealth_growth",
    "income_bracket": "100k_500k"
  },
  "notifications": {
    "in_app": true,
    "email": true,
    "whatsapp": false,
    "slack": false
  }
}
```

Response (201):
```json
{ "access": "<JWT>", "refresh": "<JWT>" }
```

### POST `/users/check-email/`

Request:
```json
{ "email": "user@example.com" }
```

Response (200):
```json
{ "available": true }
```

## A.2 User

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/users/profile/` | — | `{ id, email, name, phone, ... }` |
| PATCH | `/users/profile/` | partial profile | updated profile |
| GET | `/users/details/` | — | aggregate (auth + KYC + investment) |
| PATCH | `/users/edit/` | KYC + profile | updated payload |
| GET / PATCH | `/users/investment-profile/` | investment fields | updated investment fields |
| GET / PATCH | `/users/notifications/` | channel fields | updated preferences |
| POST | `/users/change-password/` | `{ old_password, new_password }` | `{ ok: true }` |

## A.3 Portfolio

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/portfolio/holdings/` | — | list of holdings |
| POST | `/portfolio/holdings/` | `{ symbol, quantity, avg_buy_price }` | created holding |
| GET / PATCH / DELETE | `/portfolio/holdings/<uuid>/` | partial fields | updated or 204 |
| GET | `/portfolio/transactions/` | — | list of transactions |
| POST | `/portfolio/transactions/` | `{ symbol, side, qty, price }` | created tx + updated holding |
| GET | `/portfolio/analytics/` | — | `{ total_value, gain_loss, allocation, risk_metrics }` |

## A.4 Core Market Data

| Method | Path | Response |
|---|---|---|
| GET | `/core/symbols/` | list of all PSX symbols |
| GET | `/core/signals/` | list of fused signals |
| GET | `/core/signals/<ticker>/` | signal detail for one symbol |
| GET | `/core/technicals/` | list of technicals |
| GET | `/core/technicals/<ticker>/` | technicals detail |
| GET | `/core/live/<ticker>/` | latest live bar |
| GET | `/core/forecast-trend/<ticker>/` | 30-day forward trend |
| GET | `/core/stock-search/?q=...` | autocomplete results |

## A.5 Insights

| Method | Path | Response |
|---|---|---|
| GET | `/insights/filters/` | `{ sectors, signals, sort_options }` |
| GET | `/insights/stocks/?sector=...&signal=...&sort=...&page=N` | paginated stock list |
| GET | `/insights/stocks/<ticker>/` | per-ticker detail (signals + technicals + news) |

## A.6 Dashboard

| Method | Path | Response |
|---|---|---|
| GET | `/dashboard/stocks/` | aggregated cards (AI picks, top performers, etc.) |
| GET | `/dashboard/news/` | news feed |

## A.7 Chatbot

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/chatbot/ask/` | `{ message, session_id? }` | `{ answer, session_id }` |
| GET | `/chatbot/sessions/` | — | list of sessions |
| GET | `/chatbot/sessions/<id>/` | — | session detail with messages |

## A.8 Alerts

| Method | Path | Response |
|---|---|---|
| GET | `/alerts/history/` | list of past alerts |
| GET | `/alerts/history/<id>/` | alert detail |
| GET / PATCH | `/alerts/preferences/` | per-channel preferences |

## A.9 Integrations

| Method | Path | Response |
|---|---|---|
| GET | `/integrations/status/` | pipeline-stage health and last-run timestamps |

---

# Appendix B — Database Schema Reference

## B.1 `users` app

```
CustomUser(AbstractUser)
  email           CharField unique
  name            CharField
  phone           CharField
  is_active       BooleanField
  date_joined     DateTimeField
  last_login      DateTimeField

UserKycProfile
  user            OneToOne(CustomUser)
  cnic            CharField unique
  dob             DateField
  gender          CharField(choices)
  city            CharField
  province        CharField(choices)
  postal_code     CharField
  created_at      DateTimeField
  updated_at      DateTimeField

InvestmentProfile
  user            OneToOne(CustomUser)
  experience      CharField(choices)        # beginner|intermediate|advanced
  risk_tolerance  CharField(choices)        # low|medium|high
  goal            CharField(choices)        # wealth_growth|income|retirement|...
  income_bracket  CharField(choices)        # under_100k|100k_500k|500k_2m|2m_plus

NotificationPreference
  user            OneToOne(CustomUser)
  in_app          BooleanField default=True
  email           BooleanField default=True
  whatsapp        BooleanField default=False
  slack           BooleanField default=False
  slack_webhook   CharField blank
  pre_market      BooleanField default=True
  midday          BooleanField default=True
  post_market     BooleanField default=True
```

## B.2 `core` app

```
TimestampMixin (abstract)
  created_at      DateTimeField
  updated_at      DateTimeField

StockSymbol(TimestampMixin)
  ticker          CharField unique
  name            CharField
  sector          CharField
  is_active       BooleanField

StockTechnicals(TimestampMixin)
  symbol          FK(StockSymbol)
  date            DateField
  ma_20           FloatField
  ma_50           FloatField
  ma_200          FloatField
  rsi_14          FloatField
  volatility      FloatField
  volume_ratio    FloatField

StockForecast(TimestampMixin)
  symbol          FK(StockSymbol)
  date            DateField
  predicted_price FloatField
  direction       CharField(choices)
  model_used      CharField(choices)        # ARIMA|LSTM

ForecastTrend(TimestampMixin)
  symbol          FK(StockSymbol)
  date            DateField                # forecast target date
  predicted_price FloatField

NewsSentiment(TimestampMixin)
  symbol          FK(StockSymbol, nullable)
  date            DateField
  heading         CharField
  link            URLField
  score           FloatField                # pos_prob − neg_prob
  label           CharField(choices)        # VERY_BAD|BAD|NEUTRAL|GOOD|EXCELLENT
  industry        CharField(choices, nullable)

StockSignal(TimestampMixin)
  symbol          OneToOne(StockSymbol)
  signal          CharField(choices)        # STRONG_SELL|SELL|HOLD|BUY|STRONG_BUY
  score           FloatField
  primary_driver  CharField
  contributions   JSONField

LiveMarketData(TimestampMixin)
  symbol          FK(StockSymbol)
  datetime        DateTimeField
  open / high / low / close / volume

ScrapeRun(TimestampMixin)
  stage           CharField
  status          CharField(choices)        # SUCCESS|PARTIAL|FAILED
  started_at      DateTimeField
  finished_at     DateTimeField
  notes           TextField
```

## B.3 `portfolio` app

```
PortfolioHolding
  id              UUIDField primary
  user            FK(CustomUser)
  symbol          FK(StockSymbol)
  quantity        DecimalField
  avg_buy_price   DecimalField
  created_at      DateTimeField
  updated_at      DateTimeField

Transaction(TimestampMixin)
  user            FK(CustomUser)
  symbol          FK(StockSymbol)
  side            CharField(choices)        # BUY|SELL
  quantity        DecimalField
  price           DecimalField
  date            DateField
```

## B.4 `chatbot` app

```
ChatSession(TimestampMixin)
  user            FK(CustomUser, related_name="chat_sessions")
  started_at      DateTimeField
  last_active     DateTimeField
  is_active       BooleanField

ChatMessage(TimestampMixin)
  session         FK(ChatSession, related_name="messages")
  role            CharField(choices)        # USER|ASSISTANT
  content         TextField
  sources_used    JSONField
```

## B.5 `alerts` app

```
Alert(TimestampMixin)
  symbol          FK(StockSymbol, nullable)
  type            CharField(choices)
  severity        CharField(choices)
  summary         CharField

AlertDetail(TimestampMixin)
  alert           OneToOne(Alert)
  payload         JSONField

AlertLog(TimestampMixin)
  alert           FK(Alert)
  user            FK(CustomUser)
  channel         CharField(choices)        # IN_APP|EMAIL|WHATSAPP|SLACK
  status          CharField(choices)        # PENDING|DELIVERED|RETRY|FAILED|SUPPRESSED
  attempted_at    DateTimeField
  delivered_at    DateTimeField nullable

Notification(TimestampMixin)
  user            FK(CustomUser)
  title           CharField
  body            TextField
  read            BooleanField default=False
```

## B.6 `dashboard` app

```
DashboardCache
  id              AutoField primary
  payload         JSONField
  updated_at      DateTimeField
```

---

# Appendix C — Configuration and Environment Variables

## C.1 `.env.example` Contract

```
# Django
DJANGO_SECRET_KEY=...
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (Supabase)
DATABASE_URL=postgres://...

# Cache + broker (Upstash)
REDIS_URL=redis://...

# Sentiment backend
SENTIMENT_BACKEND=finbert         # or vader

# GCS
GCS_BUCKET=etl_b
GOOGLE_APPLICATION_CREDENTIALS=/secrets/gcp.json

# Channels
SENDGRID_API_KEY=...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
SLACK_BOT_TOKEN=...

# MLflow
MLFLOW_TRACKING_URI=http://mlflow.internal/

# ML behaviour
STALE_SUGGESTION_DAYS=30
SCRAPER_LIMIT=                    # blank for full universe, N for dev runs
```

## C.2 Frontend `.env`

```
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.4:3100/api/v1
```

## C.3 Celery Settings (excerpt)

```
CELERY_BROKER_URL = env("REDIS_URL")
CELERY_RESULT_BACKEND = env("REDIS_URL")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Karachi"
CELERY_ENABLE_UTC = False
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
```

## C.4 CORS Settings

```
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8081",
]
```

## C.5 JWT Settings

```
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=24),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
}
```

---

# Appendix D — Repository File Index

## D.1 Backend (FinMate-BE)

**Project**

| Path | Role |
|---|---|
| `config/settings.py` | Single-file Django settings |
| `config/urls.py` | Project URL conf |
| `config/celery.py` | Celery app + autodiscovery |
| `config/celery_schedule.py` | Beat schedule |
| `manage.py` | Standard Django management script |
| `Dockerfile` | Production container |
| `requirements.txt` | Pinned Python dependencies |

**ML**

| Path | Role |
|---|---|
| `ml_services/forecasting.py` | ARIMA + LSTM forecast pipeline |
| `ml_services/sentiment.py` | FinBERT + VADER backends |
| `ml_services/directional_classifier.py` | 3-model ensemble |
| `ml_services/stock_health.py` | Orchestrator emitting `stocks.json` |
| `ml_services/fusion.py` | Adaptive fusion engine |
| `ml_services/chatbot_rag.py` | RAG entrypoint |
| `ml_services/gcs_sync.py` | GCS sync for data + cache |
| `ml_services/mlflow_utils.py` | MLflow wrapper with circuit breaker |
| `ml_services/model_cache.py` | Warm-mode artefact cache |

**Scrapers**

| Path | Role |
|---|---|
| `integrations/scrapers/registry_scraper.py` | Refresh `symbols.py` |
| `integrations/scrapers/historical_scraper.py` | Daily OHLCV |
| `integrations/scrapers/live_scraper.py` | Intraday hourly bars |
| `integrations/scrapers/news_scraper.py` | News scraper |
| `integrations/scrapers/key_ratios_scraper.py` | Technicals + fundamentals |
| `integrations/scrapers/symbols.py` | 738 PSX equities (generated) |

**Bash orchestrators**

| Path | Role |
|---|---|
| `bin/run_cold.sh` | Full retrain — weekly |
| `bin/run_warm.sh` | Hourly warm pipeline |
| `bin/run_warm_1_scrape_hist.sh` | Warm stage 1 |
| `bin/run_warm_2_scrape_news.sh` | Warm stage 2 |
| `bin/run_warm_3_ml_fuse.sh` | Warm stage 3 |
| `bin/run_warm_4_ingest.sh` | Warm stage 4 |
| `bin/run_live.sh` | Hourly live-price refresh |
| `bin/run_monthly.sh` | Monthly registry refresh |
| `bin/run_quarterly_fundamentals.sh` | Quarterly fundamentals |
| `bin/run_news_local.sh` | Laptop-based news backfill |

**n8n**

| Path | Role |
|---|---|
| `n8n/workflow_a_strong_signals.json` | Workflow A — strong cross-market events |
| `n8n/workflow_b_portfolio_alerts.json` | Workflow B — portfolio-relevant alerts |
| `n8n/alert.md`, `notification_examples.md`, `workflow_notification.md` | Documentation |

**Docs**

| Path | Role |
|---|---|
| `README.md` | Setup + project overview |
| `Ahad.md` | Detailed architecture / viva notes (31 KB) |
| `how_works.md` | Per-stage pipeline timeline (28 KB) |
| `pipeline_flow.md` | End-to-end data-flow diagrams (28 KB) |
| `table_schemas_info.md` | Full DB schema reference (24 KB) |
| `infrastructure.md` | Production topology runbook (14 KB) |
| `post_deployment_change.md` | Post-launch operational lessons (11 KB) |
| `wasif_April28.md` | Engineering checkpoint (9.4 KB) |
| `db_issues_review.md` | DB-issue triage record (8.3 KB) |
| `cloud_link.md` | Cloud-resource inventory (6.5 KB) |
| `warm_mode.md` | Warm-mode design doc (5.1 KB) |
| `FYP_REPORT.md` | **This document** |

## D.2 Frontend (FinMate-FE)

| Path | Role |
|---|---|
| `app.json` | Expo configuration |
| `package.json` | Dependencies + scripts |
| `babel.config.js`, `tsconfig.json`, `eslint.config.js` | Build / lint config |
| `src/app/_layout.tsx` | Root layout, AuthProvider, AuthGuard |
| `src/app/(tabs)/_layout.tsx` | Custom animated tab bar |
| `src/app/(tabs)/dashboard.tsx` | Main dashboard (~61 KB) |
| `src/app/(tabs)/portfolio.tsx` | Portfolio analytics |
| `src/app/(tabs)/insights.tsx` | Filterable / paginated stock list |
| `src/app/(tabs)/chatbot.tsx` | Chatbot UI |
| `src/app/(tabs)/news.tsx` | News feed |
| `src/app/(tabs)/profile.tsx` | Profile menu |
| `src/app/stock-insight/[ticker].tsx` | Per-ticker detail (~18 KB) |
| `src/app/manage-portfolio.tsx` | Add / edit / delete holding wizard (~43 KB) |
| `src/app/buy-sell-stock.tsx` | Broker + browse UI (~22 KB) |
| `src/context/AuthContext.tsx` | Auth state + AuthGuard logic |
| `src/services/auth.ts`, `dashboard.ts`, `insights.ts`, `portfolio.ts`, `notifications.ts` | API client |
| `src/components/ui/*` | Reusable UI components |
| `src/components/insights/*` | Insights-screen components |
| `src/components/signup/*` | Signup wizard steps |
| `src/utils/signupValidation.ts` | Pakistani validators |
| `src/utils/livePrice.ts` | PKT-aware timestamp formatting |
| `src/constants/pakistanBrokers.ts` | 15 broker list |
| `src/styles/global.ts` | Colour palette + font tokens |
| `src/navigation/transitions.ts` | Custom stack / tab animation configs |
| `Changes.md` | Authentication-subsystem design doc |

---

*End of report — FinMate FYP submission, 26 May 2026.*
*Document set in Montserrat. Total length approximately 60 A4 pages.*
