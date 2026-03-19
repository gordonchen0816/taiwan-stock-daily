"""
台股每日彙整 - 合併版主程式
結合：yfinance 股價、cnyes 法人、RSS + cnyes 新聞、GPT 報告、歷史記憶
"""

import os
import json
import time
import traceback
import feedparser
import requests
import pandas as pd
import yfinance as yf
import markdown
from openai import OpenAI
from datetime import datetime, timedelta
from pathlib import Path

# ── 設定 ────────────────────────────────────────────────────
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

WATCH_LIST = {
    "台積電": "2330.TW",
    "鴻海":   "2317.TW",
    "鴻勁":   "7769.TW",
    "聯發科": "2454.TW",
}

NEWS_KEYWORDS = [
    "台積電", "AI", "NVDA", "輝達", "殖利率",
    "黃金", "房地產", "股匯", "ETF", "美債",
    "AI Agent", "籌碼", "聯發科", "鴻海",
]

RSS_FEEDS = {
    "工商時報":  "https://ctee.com.tw/feed",
    "經濟日報":  "https://money.udn.com/rssfeed/news/1001/5591?ch=money",
    "MoneyDJ":  "https://www.moneydj.com/rss/rssnews.aspx",
    "鉅亨網":    "https://news.cnyes.com/rss/tw_stock",
}

DATA_DIR  = Path(__file__).parent.parent / "data"
DOCS_DIR  = Path(__file__).parent.parent / "docs"
HIST_FILE = DATA_DIR / "history.json"


# ── 工具函式 ────────────────────────────────────────────────
def calculate_rsi(series, window=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(window).mean()
    loss  = (-delta.clip(upper=0)).rolling(window).mean()
    return 100 - (100 / (1 + gain / loss))


def manage_memory(new_entry=None):
    DATA_DIR.mkdir(exist_ok=True)
    history = []
    if HIST_FILE.exists():
        try:
            with open(HIST_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
    if new_entry:
        history.append(new_entry)
        history = history[-42:]
        with open(HIST_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    return history


# ── 模組一：法人買賣超（cnyes） ─────────────────────────────
def fetch_institutional():
    url = "https://api.cnyes.com/media/api/v1/investor/total"
    for i in range(3):
        try:
            r = requests.get(url, timeout=10)
            items = r.json().get("items", {})
            f_buy = round(items.get("foreign", 0) / 1e8, 2)
            t_buy = round(items.get("trust",   0) / 1e8, 2)
            d_buy = round(items.get("dealer",  0) / 1e8, 2)
            total = round(f_buy + t_buy + d_buy, 2)
            is_final = total != 0
            status   = "✅ 數據已結算" if is_final else "⚠️ 盤中監控（結算未出）"
            text = f"{status} | 外資：{f_buy}億 | 投信：{t_buy}億 | 自營：{d_buy}億 | 合計：{total}億"
            return text, {"foreign": f_buy, "trust": t_buy, "dealer": d_buy, "total": total, "is_final": is_final}
        except Exception:
            if i < 2:
                time.sleep(5)
    return "📡 法人資料暫時無法取得", {"total": 0, "is_final": False}


# ── 模組二：個股股價與技術指標（yfinance） ───────────────────
def fetch_stocks():
    results = []
    for name, ticker in WATCH_LIST.items():
        try:
            df = yf.download(ticker, period="60d", interval="1d", progress=False, auto_adjust=True)
            if df.empty:
                continue
            close     = df["Close"].squeeze()
            curr_p    = round(float(close.iloc[-1]), 2)
            prev_p    = round(float(close.iloc[-2]), 2)
            diff      = round(curr_p - prev_p, 2)
            pct       = round((diff / prev_p) * 100, 2)
            sma7      = round(float(close.rolling(7).mean().iloc[-1]),  2)
            sma20     = round(float(close.rolling(20).mean().iloc[-1]), 2)
            rsi       = round(float(calculate_rsi(close).iloc[-1]), 2)
            high_30   = round(float(close.tail(30).max()), 2)
            low_30    = round(float(close.tail(30).min()), 2)
            trend     = "多頭" if curr_p > sma20 else "空頭"
            results.append({
                "name":    name,
                "ticker":  ticker,
                "close":   curr_p,
                "diff":    diff,
                "pct":     pct,
                "sma7":    sma7,
                "sma20":   sma20,
                "rsi":     rsi,
                "high_30": high_30,
                "low_30":  low_30,
                "trend":   trend,
            })
            print(f"✅ {name}：{curr_p} ({pct:+.2f}%)  RSI {rsi}")
        except Exception as e:
            print(f"❌ {name} 失敗：{e}")
    return results


# ── 模組三：新聞（RSS + cnyes 關鍵字過濾） ───────────────────
def fetch_news():
    news_list = []

    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:6]:
                title = entry.get("title", "").strip()
                if any(kw.lower() in title.lower() for kw in NEWS_KEYWORDS):
                    news_list.append({
                        "source": source,
                        "title":  title,
                        "link":   entry.get("link", ""),
                    })
            print(f"✅ RSS {source}：已過濾")
        except Exception as e:
            print(f"❌ RSS {source} 失敗：{e}")

    try:
        r = requests.get(
            "https://api.cnyes.com/media/api/v1/newslist/category/tw_stock?limit=40",
            timeout=10,
        )
        for item in r.json()["items"]["data"]:
            title = item["title"]
            if any(kw.lower() in title.lower() for kw in NEWS_KEYWORDS):
                news_list.append({
                    "source": "鉅亨網",
                    "title":  title,
                    "link":   f"https://news.cnyes.com/news/id/{item['newsId']}",
                })
        print("✅ cnyes：已過濾")
    except Exception as e:
        print(f"❌ cnyes 新聞失敗：{e}")

    seen, dedup = set(), []
    for n in news_list:
        if n["title"] not in seen:
            seen.add(n["title"])
            dedup.append(n)
    return dedup[:30]


# ── 模組四：GPT 報告 ────────────────────────────────────────
def generate_report(stocks, inst_text, news, past_history, mode_label):
    stock_summary = "\n".join([
        f"{s['name']}：{s['close']} ({s['pct']:+.2f}%)  RSI {s['rsi']}  趨勢：{s['trend']}"
        for s in stocks
    ])
    news_titles = "\n".join([f"・[{n['source']}] {n['title']}" for n in news[:15]])

    prompt = f"""
任務：你是台股分析 Agent。模式：{mode_label}。
【重要】若法人合計為 0，請專注分析權值股技術面與 RSI 變化。
【歷史記憶（近 3 筆）】：{json.dumps(past_history[-3:], ensure_ascii=False)}
【三大法人籌碼】：{inst_text}
【個股技術面】：
{stock_summary}
【今日關鍵新聞】：
{news_titles}

請用繁體中文，條列式輸出以下 Markdown 格式：

## 📈 大盤與籌碼總覽
## 🔍 個股技術面速覽
## 📰 新聞重點摘要（5 則）
## ⚠️ 今日需注意
## 🎯 下一階段觀察點
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "你是一位專業台股分析顧問，擅長籌碼分析與技術面判讀。"},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=1500,
        temperature=0.3,
    )
    return response.choices[0].message.content


# ── 模組五：產生 HTML ───────────────────────────────────────
def build_html(stocks, inst_text, inst_data, news, ai_report, time_str):
    cards_html = ""
    for s in stocks:
        color = "#d73a49" if s["diff"] >= 0 else "#22863a"
        sign  = "+" if s["diff"] >= 0 else ""
        cards_html += f"""
        <div class="stock-card">
            <div class="stock-name">{s['name']} <span style="color:#666;font-size:.8em">{s['ticker']}</span></div>
            <div class="stock-price">{s['close']:,}</div>
            <div class="stock-change" style="color:{color}">{sign}{s['diff']} ({sign}{s['pct']}%)</div>
            <div class="stock-meta">RSI: {s['rsi']} | {s['trend']} | SMA7: {s['sma7']} / SMA20: {s['sma20']}</div>
            <div class="stock-meta">30日高: {s['high_30']} / 低: {s['low_30']}</div>
        </div>"""

    news_items = ""
    for n in news:
        news_items += f"""
        <li>
            <span class="news-source">{n['source']}</span>
            <a href="{n['link']}" target="_blank">{n['title']}</a>
        </li>"""

    inst_border = "#f39c12" if inst_data.get("is_final") else "#0969da"
    html_report = markdown.markdown(ai_report, extensions=["nl2br"])

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>台股每日彙整</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
<style>
  body {{ background:#ffffff; color:#1f2328; max-width:1000px; margin:0 auto; padding:20px; font-family:-apple-system,sans-serif; }}
  .markdown-body {{ background:transparent!important; color:#1f2328!important; }}
  h1 {{ border-bottom:2px solid #d0d7de; padding-bottom:.5rem; }}
  .inst-banner {{ background:#f6f8fa; border:2px solid {inst_border}; padding:15px; border-radius:8px; margin-bottom:20px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:15px; margin-bottom:30px; }}
  .stock-card {{ background:#f6f8fa; border:1px solid #d0d7de; border-radius:10px; padding:15px; }}
  .stock-name {{ font-weight:700; color:#0969da; margin-bottom:4px; }}
  .stock-price {{ font-size:1.4rem; font-weight:700; }}
  .stock-change {{ font-size:.95rem; margin:2px 0; }}
  .stock-meta {{ font-size:.8rem; color:#57606a; margin-top:4px; }}
  .news-list {{ list-style:none; padding:0; }}
  .news-list li {{ padding:.6rem 0; border-bottom:1px solid #d0d7de; display:flex; gap:.6rem; align-items:baseline; }}
  .news-source {{ font-size:.72rem; color:#0969da; background:rgba(9,105,218,.1); padding:.1rem .4rem; border-radius:3px; white-space:nowrap; flex-shrink:0; }}
  .news-list a {{ color:#1f2328; text-decoration:none; font-size:.88rem; line-height:1.5; }}
  .news-list a:hover {{ color:#0969da; }}
  details summary {{ cursor:pointer; padding:12px; background:#f1f8ff; border:1px solid #0969da; border-radius:8px; color:#0969da; font-weight:700; margin-top:20px; }}
  footer {{ text-align:center; color:#57606a; font-size:.78rem; padding:2rem 0; border-top:1px solid #d0d7de; margin-top:2rem; }}
</style>
</head>
<body class="markdown-body">
<h1>💹 台股每日彙整報告</h1>
<div class="inst-banner">
  <strong>📊 三大法人籌碼：</strong>{inst_text}<br>
  <small>📅 更新時間：{time_str}</small>
</div>
<div class="cards">{cards_html}</div>
<hr>
<h2>🤖 AI 每日分析報告</h2>
{html_report}
<details>
  <summary>📂 今日關鍵字過濾新聞（共 {len(news)} 則）</summary>
  <ul class="news-list">{news_items}</ul>
</details>
<footer>資料每個交易日自動更新 ・ Taiwan Stock Daily Digest</footer>
</body>
</html>"""


# ── 主程式 ──────────────────────────────────────────────────
def main():
    tw_now   = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_now.strftime("%Y-%m-%d %H:%M:%S")
    today    = tw_now.strftime("%Y-%m-%d")
    hour_min = tw_now.strftime("%H:%M")

    print(f"🚀 開始執行：{time_str}")

    is_after   = "14:30" <= hour_min <= "23:59"
    mode_label = "【盤後籌碼定調模式】" if is_after else "【盤中動態監控模式】"

    past_history         = manage_memory()
    inst_text, inst_data = fetch_institutional()
    stocks               = fetch_stocks()
    news                 = fetch_news()

    print("🤖 產生 AI 報告...")
    ai_report = generate_report(stocks, inst_text, news, past_history, mode_label)

    html = build_html(stocks, inst_text, inst_data, news, ai_report, time_str)

    DATA_DIR.mkdir(exist_ok=True)
    DOCS_DIR.mkdir(exist_ok=True)

    daily_data = {
        "date":          today,
        "time":          time_str,
        "stocks":        stocks,
        "institutional": inst_data,
        "news":          news,
        "report":        ai_report,
    }
    with open(DATA_DIR / f"{today}.json", "w", encoding="utf-8") as f:
        json.dump(daily_data, f, ensure_ascii=False, indent=2)

    with open(DOCS_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(html)

    manage_memory({
        "time":    time_str,
        "index":   next((s["close"] for s in stocks if s["name"] == "台積電"), None),
        "summary": ai_report[:120],
    })

    print("✅ 完成！報告已寫入 docs/index.html")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(f"ERROR:\n{traceback.format_exc()}")
        raise
