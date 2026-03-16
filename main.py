import os
import yfinance as yf
from openai import OpenAI
import requests
import traceback
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import markdown

# 1. 配置 OpenAI Client (使用 GPT-4o-mini)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_news_pool(limit=50):
    """
    抓取鉅亨網與財經M平方 RSS。
    徹底捨棄 Google News，解決長連結亂碼與斷頭問題。
    """
    sources = [
        {"name": "鉅亨網", "url": "https://news.cnyes.com/rss/tw_stock"},
        {"name": "財經M平方", "url": "https://www.macromicro.me/blog/rss"}
    ]
    headers = {"User-Agent": "Mozilla/5.0"}
    pool = []

    for src in sources:
        try:
            response = requests.get(src["url"], headers=headers, timeout=15)
            soup = BeautifulSoup(response.content, features="xml")
            items = soup.find_all("item", limit=25)
            for item in items:
                title = item.title.text.strip()
                # 關鍵：只取連結的主體，去除追蹤參數
                link = item.link.text.split('?')[0].replace('\n', '').strip()
                pool.append({
                    "title": title, 
                    "link": link, 
                    "source": src["name"]
                })
        except Exception as e:
            print(f"抓取 {src['name']} 失敗: {e}")
            continue
            
    return pool[:limit]

def format_pool_for_prompt(pool):
    """將新聞池轉成 prompt 用的文字"""
    lines = []
    for i, item in enumerate(pool, 1):
        lines.append(f"[{i}] 來源: {item['source']} | 標題: {item['title']} | 連結: {item['link']}")
    return "\n".join(lines)

def get_stock_data():
    """下載台股權值股資料"""
    tickers = {
        "加權指數": "^TWII",
        "台積電": "2330.TW",
        "鴻海": "2317.TW",
        "聯發科": "2454.TW",
        "台達電": "2308.TW",
    }
    summary_parts = []
    structured = []

    for name, code in tickers.items():
        try:
            d = yf.download(code, period="5d", interval="1d", progress=False)
            if not d.empty:
                curr = round(float(d["Close"].iloc[-1].item()), 2)
                prev = round(float(d["Close"].iloc[-2].item()), 2)
                diff = round(curr - prev, 2)
                pct = round((diff / prev) * 100, 2)
                sign = "▲" if diff >= 0 else "▼"
                color = "up" if diff >= 0 else "down"
                summary_parts.append(f"{name}: {curr} ({sign}{abs(diff)}, {pct}%)")
                structured.append({
                    "name": name, "price": curr, "diff": diff,
                    "pct": pct, "sign": sign, "color": color,
                })
        except Exception:
            summary_parts.append(f"{name}: 失敗")

    return " &nbsp; ".join(summary_parts), structured

def build_stock_html(structured):
    """股價卡片 HTML"""
    cards = []
    for s in structured:
        diff_str = f"{s['sign']}{abs(s['diff'])}"
        pct_str = f"{s['pct']:+.2f}%"
        cards.append(f"""
        <div class="stock-card {s['color']}">
            <div class="stock-name">{s['name']}</div>
            <div class="stock-price">{s['price']:,.2f}</div>
            <div class="stock-change">{diff_str} &nbsp; {pct_str}</div>
        </div>""")
    return "\n".join(cards)

# ── 主流程 ──
try:
    print("--- 啟動 AI 財經主編 (GPT-4o-mini 版) ---")
    tw_now = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_now.strftime("%Y-%m-%d %H:%M:%S")

    news_pool = get_news_pool(50)
    pool_text = format_pool_for_prompt(news_pool)
    stock_summary, structured_stocks = get_stock_data()
    stock_cards_html = build_stock_html(structured_stocks)

    prompt = f"""
    任務：你是台灣頂級財經主編，請結合『即時新聞』與『總經深度觀點』輸出報告。語言：繁體中文。

    【新聞池】
    {pool_text}

    【今日股市數據】
    {stock_summary}

    ── 輸出格式 ──
    ## 📈 今日盤勢重點分析
    (請結合新聞池中的總經觀點與即時行情，撰寫 150 字內的深度分析)

    ## 📰 財經綜合焦點（5 則）
    (格式：- [新聞標題](連結) — 來源)

    ## 📖 總經與科技精選（5 則）
    (格式：- [新聞標題](連結) — 來源)

    ## 🌐 市場熱門話題（5 則）
    (格式：- [新聞標題](連結) — 來源)

    ## 📌 三大市場焦點交集
    **焦點 1**：內容
    **焦點 2**：內容
    **焦點 3**：內容

    【規則】
    1. 必須嚴格閉合 Markdown 連結格式 [標題](連結)。
    2. 禁止使用 google.com 的連結。
    3. 若來源包含『財經M平方』，請優先放入精選區。
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "你是一位專業的台灣財經主編，擅長總經與台股分析。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=3000
    )

    md_text = response.choices[0].message.content
    html_body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "nl2br"])

    # HTML 模板與樣式已優化，增加連結自動換行防止撐破版面
    full_html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>台股 AI 總經情報站</title>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #0d1117; --surface: #161b22; --border: #30363d;
            --text: #e6edf3; --muted: #8b949e; --accent: #58a6ff;
            --up: #3fb950; --down: #f85149;
        }}
        body {{ background: var(--bg); color: var(--text); font-family: "Noto Sans TC", sans-serif; padding: 20px; line-height: 1.6; }}
        .wrapper {{ max-width: 850px; margin: 0 auto; }}
        header {{ border-bottom: 1px solid var(--border); padding-bottom: 15px; margin-bottom: 25px; }}
        .site-title {{ color: var(--accent); font-size: 1.5rem; font-weight: 700; }}
        .stock-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 30px; }}
        .stock-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 12px; }}
        .stock-card.up {{ border-top: 4px solid var(--up); }}
        .stock-card.down {{ border-top: 4px solid var(--down); }}
        .stock-price {{ font-family: 'JetBrains Mono'; font-size: 1.2rem; font-weight: 600; margin: 5px 0; }}
        .md-body a {{ color: var(--accent); text-decoration: none; word-break: break-all; }}
        .md-body ul li {{ margin-bottom: 10px; border-bottom: 1px solid #21262d; padding-bottom: 5px; list-index: none; list-style: none; }}
        footer {{ text-align: center; font-size: 0.8rem; color: var(--muted); margin-top: 50px; border-top: 1px solid var(--border); padding-top: 20px; }}
    </style>
</head>
<body>
<div class="wrapper">
    <header>
        <div class="site-title">📊 台股 AI 總經情報站</div>
        <div style="font-size: 0.8rem; color: var(--muted);">更新時間：{time_str} (台北)</div>
    </header>

    <div class="stock-grid">{stock_cards_html}</div>
    <div class="md-body">{html_body}</div>

    <footer>
        數據來源：鉅亨網 &bull; 財經M平方 &bull; OpenAI GPT-4o-mini
    </footer>
</div>
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print("--- 任務完成 ---")

except Exception:
    print(traceback.format_exc())
