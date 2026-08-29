# Risk Analytics Tab — Plan for Basis

## Context
Basis is an existing full-stack portfolio backtester (Python + Flask + MySQL + Angular) that currently supports three trading **strategies**: SMA crossover, RSI, and Buy-and-Hold. This plan adds a new **"Risk Analytics"** tab containing four quant/risk **models**, which are conceptually different from the existing strategies.

**Strategies vs. Models — the distinction:**
- **Strategies** (existing) = trading rules answering "when should I buy/sell?" (e.g., RSI: buy when oversold, sell when overbought)
- **Models** (this tab) = valuation/risk calculations answering "what's it worth?" or "how risky is it?" — not action rules, but numbers/distributions computed from data

Adding these models signals a different skill set (quant/risk modeling) alongside the existing strategy/backtesting skill set — useful for targeting quant research, markets tech, or risk roles (e.g., JPMC, Amex).

## Decision: why this approach
Considered three options:
1. **Standalone new project** ("Quant Risk Toolkit") — rejected. Would require rebuilding data layer, API, and frontend from scratch — time goes into plumbing, not into understanding the models.
2. **Finnhub-integrated live-data version** — rejected as a starting point. Live data adds complexity (API keys, rate limits, error handling) without adding to the core goal of understanding the models. Deprioritized as a possible future upgrade, not a v1 requirement.
3. **New tab inside Basis, using existing yfinance data** — **chosen.** Reuses the existing data layer, Flask API pattern, and Angular dashboard shell. All new effort goes into the model math and one new tab, not new infrastructure. Also produces one deep, connected project rather than two shallow ones — a stronger interview story ("I built a backtester, then extended it with quant risk models").

## The four models, in build order

1. **Monte Carlo Simulation**
   Simulates thousands of possible future price paths via random sampling (based on historical drift/volatility). Built first because its simulation engine gets reused by VaR.

2. **Value at Risk (VaR)**
   Answers "how much could I lose, at a given confidence level?" (e.g., "95% confident I won't lose more than $X tomorrow"). Can reuse the Monte Carlo engine, or be computed historically/parametrically.

3. **Markowitz Portfolio Optimization (Modern Portfolio Theory)**
   Given a set of assets, computes the optimal allocation (weights) that maximizes return for a given risk level (or minimizes risk for a given return) — the efficient frontier.

4. **Black-Scholes Option Pricing**
   Closed-form formula for theoretical option pricing, given stock price, strike, time to expiry, volatility, and risk-free rate. Built last — it's fully standalone and doesn't depend on the other three.

## Per-model workflow (repeated for each of the 4)
1. **Understand** — learn the concept/formula, assumptions, and what it's used for before writing any code
2. **Standalone script** — implement it in a small Python script (`monte_carlo.py`, `var.py`, etc.), test against real yfinance data
3. **Verify** — sanity-check output against known/expected values (not just "it runs")
4. **API endpoint** — expose it via a new Flask route, following the same pattern as the existing `/api/backtest` and `/api/compare` endpoints
5. **Frontend** — add the corresponding sub-section/chart inside the new "Risk Analytics" tab in the Angular dashboard

## Notes
- Data source: yfinance (already integrated in Basis) — not Finnhub, for now
- No fixed timeline — models are being learned/understood first, one at a time, before implementation begins in earnest
- Full existing Basis architecture and session history is documented separately; this file covers only the new Risk Analytics tab plan
