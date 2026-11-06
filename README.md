# ArbiScan India — Android-friendly starter

A read-only NSE/BSE cross-listing monitor with a SQLite paper-trade ledger and optional Telegram alerts.

## Important limitations

- This starter uses Yahoo Finance's unofficial free quote interface through `yfinance`.
- It is not an exchange-authorized real-time feed. Bid/ask fields may be absent, delayed or stale.
- The app refuses to substitute last price/close for bid/ask.
- A candidate is only an indicative spread, not a verified arbitrage or a recommendation.
- Paper trading assumes both legs fill at displayed top-of-book prices. Real fills may differ or one leg may fail.
- No live order placement, broker login, demat access or investment advice is included.
- NSE/BSE same-share price gaps can be difficult to capture because of inventory, settlement, liquidity, exchange and regulatory constraints.

## Run on Android (no laptop required)

Recommended easiest path: Streamlit Community Cloud via GitHub.

1. Create a GitHub account if needed.
2. Create a new **private** repository named `arbiscan-india`.
3. Upload `app.py` and `requirements.txt`.
4. Visit https://share.streamlit.io/ and deploy the repository:
   - Main file path: `app.py`
5. Open the resulting app URL in Chrome on Android. Use Chrome menu → **Add to Home screen** if desired.

A cloud deployment is not guaranteed to be free forever; check the current hosting terms. The SQLite database on ephemeral hosting may reset after redeploy/restart. For durable records, periodically download the paper-trade CSV. Do not add paid services until the strategy is validated.

## Local run (computer)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Telegram alerts

1. In Telegram, message `@BotFather` and create a bot using `/newbot`.
2. Open the new bot and send `/start`.
3. Obtain your chat ID. Keep the bot token private.
4. For Streamlit Community Cloud, open app Settings → Secrets and add:

```toml
TELEGRAM_BOT_TOKEN = "your_bot_token"
TELEGRAM_CHAT_ID = "your_chat_id"
```

For local use, set environment variables instead. Never commit tokens to GitHub.

## Watchlist symbols

Defaults:
- Reliance: `RELIANCE.NS` / `500325.BO`
- TCS: `TCS.NS` / `532540.BO`
- Infosys: `INFY.NS` / `500209.BO`
- HDFC Bank: `HDFCBANK.NS` / `500180.BO`
- ICICI Bank: `ICICIBANK.NS` / `532174.BO`

Yahoo symbol availability and quote fields can change. Edit the watchlist in the app.

## Cost model

The all-in cost input is a user-configured placeholder in basis points. Replace it only after calculating the actual broker-specific costs for each leg, including:
- brokerage
- STT
- stamp duty
- exchange transaction charges
- SEBI charges
- GST
- DP charges where applicable
- bid/ask slippage and market impact

Do not interpret the default 35 bps as an authoritative estimate.

## Before considering any live strategy

1. Obtain a compliant, reliable market-data source and verify quote timestamps.
2. Use executable bid/ask depth, not last traded prices.
3. Model charges for the exact product and broker.
4. Verify share inventory, settlement, short-selling constraints and exchange rules.
5. Run paper trading over multiple market conditions and record one-leg failures, partial fills and slippage.
6. Review applicable SEBI/exchange/broker algo and data-use requirements.
7. Do not automate orders until compliance and execution risks are resolved.
