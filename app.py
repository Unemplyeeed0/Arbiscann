import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import streamlit as st
import yfinance as yf

DB_PATH = os.getenv("ARBISCAN_DB", "arbiscan_paper.db")

st.set_page_config(page_title="ArbiScan India", page_icon="📊", layout="wide")

DEFAULT_WATCHLIST = pd.DataFrame([
    {"name": "Reliance Industries", "nse": "RELIANCE.NS", "bse": "500325.BO"},
    {"name": "TCS", "nse": "TCS.NS", "bse": "532540.BO"},
    {"name": "Infosys", "nse": "INFY.NS", "bse": "500209.BO"},
    {"name": "HDFC Bank", "nse": "HDFCBANK.NS", "bse": "500180.BO"},
    {"name": "ICICI Bank", "nse": "ICICIBANK.NS", "bse": "532174.BO"},
])

def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            name TEXT NOT NULL,
            buy_venue TEXT NOT NULL,
            sell_venue TEXT NOT NULL,
            buy_symbol TEXT NOT NULL,
            sell_symbol TEXT NOT NULL,
            qty INTEGER NOT NULL,
            buy_price REAL NOT NULL,
            sell_price REAL NOT NULL,
            gross_pnl REAL NOT NULL,
            estimated_cost REAL NOT NULL,
            net_pnl REAL NOT NULL,
            status TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

def get_quote(symbol: str):
    """Return bid/ask only. Never substitute last trade/close for executable prices."""
    try:
        fi = yf.Ticker(symbol).fast_info
        bid = fi.get("bid")
        ask = fi.get("ask")
        last = fi.get("lastPrice")
        currency = fi.get("currency", "INR")
        if bid is None or ask is None:
            return {"ok": False, "symbol": symbol, "reason": "Bid/ask unavailable from free feed",
                    "last": last, "currency": currency}
        bid, ask = float(bid), float(ask)
        if bid <= 0 or ask <= 0 or bid > ask:
            return {"ok": False, "symbol": symbol, "reason": "Invalid bid/ask quote",
                    "last": last, "currency": currency}
        return {"ok": True, "symbol": symbol, "bid": bid, "ask": ask,
                "last": last, "currency": currency}
    except Exception as e:
        return {"ok": False, "symbol": symbol, "reason": f"Feed error: {str(e)[:100]}"}

def scan_row(row, all_in_cost_bps: float, min_net_bps: float):
    nse = get_quote(row["nse"])
    bse = get_quote(row["bse"])
    if not nse["ok"] or not bse["ok"]:
        reasons = []
        if not nse["ok"]: reasons.append("NSE: " + nse["reason"])
        if not bse["ok"]: reasons.append("BSE: " + bse["reason"])
        return {
            "Stock": row["name"], "Status": "NO VALID QUOTE",
            "Buy venue": "-", "Buy ask": None, "Sell venue": "-",
            "Sell bid": None, "Gross spread %": None, "Est. net %": None,
            "Signal": "SKIP", "Reason": "; ".join(reasons)
        }

    # Compare executable top-of-book directions.
    choices = [
        ("NSE", nse["ask"], "BSE", bse["bid"]),
        ("BSE", bse["ask"], "NSE", nse["bid"]),
    ]
    buy_v, buy_ask, sell_v, sell_bid = max(
        choices, key=lambda x: (x[3] - x[1]) / x[1]
    )
    gross_bps = ((sell_bid - buy_ask) / buy_ask) * 10000
    net_bps = gross_bps - all_in_cost_bps
    signal = "PAPER CANDIDATE" if net_bps >= min_net_bps else "NO TRADE"
    reason = ("Indicative only; verify executable depth, quote freshness, inventory and settlement."
              if signal == "PAPER CANDIDATE" else "Spread does not clear configured cost hurdle.")
    return {
        "Stock": row["name"], "Status": "QUOTE FIELDS FOUND",
        "Buy venue": buy_v, "Buy ask": buy_ask,
        "Sell venue": sell_v, "Sell bid": sell_bid,
        "Gross spread %": gross_bps / 100,
        "Est. net %": net_bps / 100,
        "Signal": signal, "Reason": reason,
        "_buy_symbol": row["nse"] if buy_v == "NSE" else row["bse"],
        "_sell_symbol": row["bse"] if sell_v == "BSE" else row["nse"],
    }

def send_telegram(message: str):
    import requests
    token = st.secrets.get("TELEGRAM_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", ""))
    chat_id = st.secrets.get("TELEGRAM_CHAT_ID", os.getenv("TELEGRAM_CHAT_ID", ""))
    if not token or not chat_id:
        return False, "Telegram credentials not configured."
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": message},
            timeout=10,
        )
        r.raise_for_status()
        payload = r.json()
        if not payload.get("ok"):
            return False, str(payload)
        return True, "Telegram alert sent."
    except Exception as e:
        return False, str(e)

st.title("📊 ArbiScan India")
st.caption("Read-only NSE/BSE cross-listing monitor + paper-trade ledger")

st.error(
    "IMPORTANT DATA LIMITATION: this starter uses Yahoo Finance's unofficial free quote interface. "
    "It is not an exchange-authorized real-time feed, may be delayed, stale or missing bid/ask fields, "
    "and must never be used to place live orders. A displayed candidate is not a verified arbitrage."
)

with st.sidebar:
    st.header("Scanner settings")
    all_in_cost_bps = st.number_input(
        "Estimated all-in round-trip costs (basis points)", min_value=0.0,
        max_value=500.0, value=35.0, step=1.0,
        help="Placeholder estimate only. Replace with your broker's actual statutory, brokerage, DP, slippage and other charges."
    )
    min_net_bps = st.number_input(
        "Minimum estimated net spread (bps)", min_value=0.0,
        max_value=1000.0, value=30.0, step=5.0
    )
    capital = st.number_input("Paper capital (₹)", min_value=1000, max_value=1000000,
                              value=10000, step=1000)
    qty = st.number_input("Paper quantity (shares)", min_value=1, max_value=10000,
                          value=1, step=1)
    st.caption("No broker account or live order placement is required.")

st.subheader("Watchlist")
if "watchlist" not in st.session_state:
    st.session_state.watchlist = DEFAULT_WATCHLIST.copy()

edited = st.data_editor(
    st.session_state.watchlist, num_rows="dynamic", use_container_width=True,
    column_config={
        "name": st.column_config.TextColumn("Company"),
        "nse": st.column_config.TextColumn("Yahoo NSE symbol"),
        "bse": st.column_config.TextColumn("Yahoo BSE symbol"),
    },
    key="watchlist_editor"
)
st.session_state.watchlist = edited

col1, col2 = st.columns([1, 3])
with col1:
    run_scan = st.button("🔄 Scan now", type="primary", use_container_width=True)
with col2:
    st.caption("Manual refresh is intentional. Free quote endpoints do not provide dependable real-time exchange data.")

if run_scan:
    results = []
    progress = st.progress(0)
    rows = edited.fillna("").to_dict("records")
    for i, row in enumerate(rows):
        if not row.get("name") or not row.get("nse") or not row.get("bse"):
            continue
        results.append(scan_row(row, all_in_cost_bps, min_net_bps))
        progress.progress((i + 1) / max(1, len(rows)))
    st.session_state.scan_results = results
    st.session_state.scan_time = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    progress.empty()

if "scan_results" in st.session_state:
    st.caption(f"Last scan: {st.session_state.get('scan_time', 'unknown')}")
    df = pd.DataFrame(st.session_state.scan_results)
    display_cols = ["Stock", "Status", "Buy venue", "Buy ask", "Sell venue",
                    "Sell bid", "Gross spread %", "Est. net %", "Signal", "Reason"]
    st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
    candidates = [r for r in st.session_state.scan_results if r.get("Signal") == "PAPER CANDIDATE"]
    if candidates:
        st.warning(f"{len(candidates)} indicative candidate(s). These are not executable trade recommendations.")
        if st.button("Send Telegram summary"):
            msg = "ArbiScan India — indicative paper candidates\n" + "\n".join(
                f"{r['Stock']}: buy {r['Buy venue']} @ {r['Buy ask']:.2f}; "
                f"sell {r['Sell venue']} @ {r['Sell bid']:.2f}; "
                f"estimated net {r['Est. net %']:.3f}%"
                for r in candidates
            )
            ok, detail = send_telegram(msg)
            (st.success if ok else st.info)(detail)
    else:
        st.info("No candidates passed the configured hurdle. Missing bid/ask quotes are skipped, not guessed.")

st.divider()
st.subheader("Paper trading")
st.write("Select a candidate from the latest scan and simulate a paired fill at displayed top-of-book prices. This assumes both legs fill, which may not happen in reality.")
if "scan_results" in st.session_state:
    candidate_names = [r["Stock"] for r in st.session_state.scan_results
                       if r.get("Signal") == "PAPER CANDIDATE"]
    if candidate_names:
        selected = st.selectbox("Candidate", candidate_names)
        chosen = next(r for r in st.session_state.scan_results if r["Stock"] == selected)
        if st.button("Record paper trade"):
            buy_price = float(chosen["Buy ask"])
            sell_price = float(chosen["Sell bid"])
            gross = (sell_price - buy_price) * int(qty)
            estimated_cost = (buy_price * int(qty)) * all_in_cost_bps / 10000
            net = gross - estimated_cost
            if buy_price * int(qty) > capital:
                st.error("Paper trade exceeds configured capital. Reduce quantity or increase paper capital.")
            else:
                conn = db()
                conn.execute("""
                    INSERT INTO paper_trades
                    (created_at,name,buy_venue,sell_venue,buy_symbol,sell_symbol,qty,
                     buy_price,sell_price,gross_pnl,estimated_cost,net_pnl,status)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                    chosen["Stock"], chosen["Buy venue"], chosen["Sell venue"],
                    chosen.get("_buy_symbol", ""), chosen.get("_sell_symbol", ""),
                    int(qty), buy_price, sell_price, gross, estimated_cost, net,
                    "SIMULATED — ASSUMED BOTH LEGS FILLED"
                ))
                conn.commit()
                conn.close()
                st.success(f"Paper trade recorded. Estimated net P&L: ₹{net:.2f}")
    else:
        st.caption("No current candidates to paper trade.")
else:
    st.caption("Run a scan first.")

conn = db()
trades = pd.read_sql_query("SELECT * FROM paper_trades ORDER BY id DESC", conn)
conn.close()
st.subheader("Paper-trade history")
if trades.empty:
    st.info("No paper trades recorded yet.")
else:
    st.dataframe(trades, use_container_width=True, hide_index=True)
    total = trades["net_pnl"].sum()
    st.metric("Cumulative simulated net P&L (not realized)", f"₹{total:,.2f}")
    csv = trades.to_csv(index=False).encode("utf-8")
    st.download_button("Download paper-trade CSV", csv, "arbiscan_paper_trades.csv", "text/csv")

st.divider()
st.subheader("Telegram setup")
st.markdown("""
1. In Telegram, open **@BotFather**, send `/newbot`, and copy the bot token.
2. Open your new bot and send it `/start`.
3. Obtain your chat ID using a trusted Telegram bot/API method.
4. Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` as Streamlit secrets or environment variables.
5. Never share your token publicly or commit it to GitHub.
""")
st.caption("This app does not place orders, access a demat account, or guarantee market-data freshness.")
