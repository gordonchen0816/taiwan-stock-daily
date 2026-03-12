"""
模組二：抓取台股市場數據
- 大盤指數（加權、櫃買）→ TWSE 官方 API（免費、無需 Key）
- 個股價格與技術指標  → TWSE + 自算
- 法人買賣超          → TWSE 官方 API
"""

import requests
import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# 想追蹤的個股清單（股票代號）
WATCH_LIST = ["2330", "2317", "2454", "2412", "2881"]  # 台積電、鴻海、聯發科、中華電、富邦金


# ── 大盤指數 ────────────────────────────────────────────────
def fetch_index() -> dict:
    """
    抓加權指數與櫃買指數今日數據（TWSE 官方 API）
    """
    result = {}
    today = datetime.today().strftime("%Y%m%d")

    # 加權指數
    try:
        url = f"https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={today}"
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get("stat") == "OK" and data.get("data"):
            row = data["data"][-1]
            result["TAIEX"] = {
                "date":   row[0],
                "close":  float(row[4].replace(",", "")),
                "change": row[5],
            }
            logger.info(f"✅ 加權指數：{result['TAIEX']['close']}")
    except Exception as e:
        logger.error(f"❌ 加權指數失敗：{e}")

    # 櫃買指數
    try:
        url = f"https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
        r = requests.get(url, timeout=10)
        data = r.json()
        if data:
            latest = data[-1]
            result["OTC"] = {
                "date":  latest.get("Date", ""),
                "close": latest.get("Index", ""),
            }
            logger.info(f"✅ 櫃買指數：{result['OTC']['close']}")
    except Exception as e:
        logger.error(f"❌ 櫃買指數失敗：{e}")

    return result


# ── 個股技術指標 ────────────────────────────────────────────
def fetch_stock_technicals(stock_id: str) -> dict:
    """
    抓個股近 60 日收盤價，計算 SMA7/20、RSI14。
    使用 TWSE 官方月成交資料拼接。
    """
    prices = []
    today = datetime.today()

    # 抓最近 3 個月資料（足夠算指標）
    for months_ago in range(2, -1, -1):
        dt = today - timedelta(days=30 * months_ago)
        date_str = dt.strftime("%Y%m%d")
        url = (
            f"https://www.twse.com.tw/exchangeReport/STOCK_DAY"
            f"?response=json&date={date_str}&stockNo={stock_id}"
        )
        try:
            r = requests.get(url, timeout=10)
            data = r.json()
            if data.get("stat") == "OK":
                for row in data.get("data", []):
                    try:
                        close = float(row[6].replace(",", ""))
                        prices.append(close)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"⚠️ {stock_id} 月資料失敗：{e}")

    if len(prices) < 20:
        logger.warning(f"⚠️ {stock_id} 資料不足，跳過")
        return {"stock_id": stock_id, "error": "資料不足"}

    df = pd.Series(prices)
    sma7  = df.rolling(7).mean().iloc[-1]
    sma20 = df.rolling(20).mean().iloc[-1]
    delta = df.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rsi   = (100 - (100 / (1 + gain / loss))).iloc[-1]

    latest_price = prices[-1]
    high_30 = max(prices[-30:])
    low_30  = min(prices[-30:])

    result = {
        "stock_id":    stock_id,
        "close":       latest_price,
        "SMA7":        round(sma7, 2),
        "SMA20":       round(sma20, 2),
        "RSI14":       round(rsi, 1),
        "high_30d":    high_30,
        "low_30d":     low_30,
    }
    logger.info(f"✅ {stock_id}：收盤 {latest_price}，RSI {rsi:.1f}")
    return result


# ── 法人買賣超 ──────────────────────────────────────────────
def fetch_institutional_investors() -> dict:
    """
    抓三大法人（外資、投信、自營商）買賣超。
    """
    today = datetime.today().strftime("%Y%m%d")
    url = (
        f"https://www.twse.com.tw/fund/T86"
        f"?response=json&date={today}&selectType=ALLBUT0999"
    )
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get("stat") != "OK":
            return {}

        totals = data.get("totalData", [None])[-1]
        if not totals:
            return {}

        def parse(val):
            return int(val.replace(",", "").replace("+", ""))

        return {
            "date":           data.get("date", today),
            "foreign_net":    parse(totals[4]),   # 外資買賣超（張）
            "trust_net":      parse(totals[10]),  # 投信買賣超
            "dealer_net":     parse(totals[14]),  # 自營商買賣超
            "total_net":      parse(totals[18]),  # 合計
        }
    except Exception as e:
        logger.error(f"❌ 法人買賣超失敗：{e}")
        return {}


# ── 主程式 ──────────────────────────────────────────────────
def fetch_all_market_data() -> dict:
    logger.info("📡 抓取市場數據中...")
    return {
        "index":       fetch_index(),
        "stocks":      [fetch_stock_technicals(sid) for sid in WATCH_LIST],
        "institutional": fetch_institutional_investors(),
    }


if __name__ == "__main__":
    import json
    data = fetch_all_market_data()
    print(json.dumps(data, ensure_ascii=False, indent=2))
