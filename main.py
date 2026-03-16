import os
import yfinance as yf
from openai import OpenAI
import requests
import random
import traceback
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import markdown

# 1. 配置 OpenAI Client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_news_pool(limit=50):
    """抓取 Google News RSS，回傳結構化清單 (含標題與連結分離)"""
    url = (
        f"https://news.google.com/rss/search?"
        f"q=股市+今日+台股+盤勢分析+when:1d"
        f"&hl=zh-TW&gl=TW&ceid=TW:zh-Hant&t={random.random()}"
    )
    headers = {"User-Agent": "Mozilla/5.0"}
    pool = []
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, features="xml")
        items = soup.find_all("item", limit=limit)
        for item in items:
            title = item.title.text.strip()
            link  = item.link.text.replace('\n', '').strip()
            if '&' in link:
                link = link[:link.index('&')]
            # 嘗試解析來源
            source = ""
            if item.source:
                source = item.source.text.strip()
            pool.append({"title": title, "link": link, "source": source})
        return pool
    except Exception:
        return [{"title": "無法取得即時新聞", "link": "#", "source": ""}]


def format_pool_for_prompt(pool):
    """將新聞池轉成 prompt 用的文字，索引號方便 AI 引用"""
    lines = []
    for i, item in enumerate(pool, 1):
        src = f" ({item['source']})" if item["source"] else ""
        lines.append(f"[{i}] 標題: {item['title']}{src} | 連結: {item['link']}")
    return "\n".join(lines)


def get_stock_data():
    """下載個股與大盤資料，回傳 (純文字摘要, 結構化清單)"""
    tickers = {
        "加權指數": "^TWII",
        "台積電":   "2330.TW",
        "鴻海":     "2317.TW",
        "聯發科":   "2454.TW",
        "台達電":   "2308.TW",
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
                pct  = round((diff / prev) * 100, 2)
                sign = "▲" if diff >= 0 else "▼"
                color = "up" if diff >= 0 else "down"
                summary_parts.append(f"{name}: {curr} ({sign}{abs(diff)}, {pct}%)")
                structured.append({
                    "name": name,
                    "price": curr,
                    "diff": diff,
                    "pct": pct,
                    "sign": sign,
                    "color": color,
                })
        except Exception:
            summary_parts.append(f"{name}: 獲取失敗")

    return " &nbsp; ".join(summary_parts), structured


def build_stock_html(structured):
    """將結構化股價資料轉為精緻 HTML 卡片"""
    cards = []
    for s in structured:
        diff_str = f"{s['sign']}{abs(s['diff'])}"
        pct_str  = f"{s['pct']:+.2f}%"
        cards.append(f"""
        <div class="stock-card {s['color']}">
            <div class="stock-name">{s['name']}</div>
            <div class="stock-price">{s['price']:,.2f}</div>
            <div class="stock-change">{diff_str} &nbsp; {pct_str}</div>
        </div>""")
    return "\n".join(cards)


# ── 主流程 ────────────────────────────────────────────────────────────────────
try:
    print("--- 啟動 AI 財經主編 ---")
    tw_now   = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_now.strftime("%Y-%m-%d %H:%M:%S")

    news_pool        = get_news_pool(50)
    pool_text        = format_pool_for_prompt(news_pool)
    stock_summary, structured_stocks = get_stock_data()
    stock_cards_html = build_stock_html(structured_stocks)

    # ── Prompt：要求先輸出評論，再列新聞，連結必須用索引號對應 ──────────────
    prompt = f"""
    任務：你是台灣頂級財經主編，請依照以下格式輸出，語言：繁體中文。

    【新聞池（請根據索引號引用連結）】
    {pool_text}

    【今日股市數據摘要】
    {stock_summary}

    ── 輸出格式（嚴格遵守，不得新增或刪除區段）──

    ## 📈 今日盤勢重點分析
    （針對今日數據與市場局勢進行 120 字內的專業評論，必須放在所有新聞列表之前）

    ## 📰 財經綜合焦點（5 則）
    （格式：- [新聞標題](對應連結) — 來源）

    ## 📖 經濟/科技精選（5 則）
    （格式：- [新聞標題](對應連結) — 來源）

    ## 🌐 市場熱門話題（5 則）
    （格式：- [新聞標題](對應連結) — 來源）

    ## 📌 三大市場焦點交集
    **焦點 1**：描述（30 字內）
    **焦點 2**：描述（30 字內）
    **焦點 3**：描述（30 字內）

    【規則】
    1. 連結必須從新聞池索引號取得，格式：[標題](連結)，不得捏造連結。
    2. 評論區段（盤勢重點分析）必須是輸出的第一個區段。
    3. 剔除封關、過期超過 24 小時之舊聞。
    4. 每則新聞標題保持原文，不得改寫。
    5. 新聞格式必須為 [標題](連結) - 來源，每個新聞僅能有一個連結，嚴禁重複輸出網址，且必須完整閉合 Markdown 括號。
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一位專業的台灣財經主編，只使用繁體中文，"
                    "絕不捏造連結，嚴格依照使用者指定的 Markdown 格式輸出。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )

    md_text   = response.choices[0].message.content
    html_body = markdown.markdown(
        md_text, extensions=["tables", "fenced_code", "nl2br"]
    )

    # ── HTML 模板 ────────────────────────────────────────────────────────────
    full_html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>台灣股市 AI 精選情報</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        /* ── 基礎重置 ── */
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

        :root {{
            --bg:        #0d1117;
            --surface:   #161b22;
            --border:    #30363d;
            --text:      #e6edf3;
            --muted:     #8b949e;
            --accent:    #58a6ff;
            --up:        #3fb950;
            --down:      #f85149;
            --up-bg:     #0d2818;
            --down-bg:   #2d1117;
            --tag-bg:    #1f2937;
        }}

        body {{
            background: var(--bg);
            color: var(--text);
            font-family: "Noto Sans TC", sans-serif;
            font-size: 15px;
            line-height: 1.75;
        }}

        /* ── 版面容器 ── */
        .page-wrapper {{
            max-width: 900px;
            margin: 0 auto;
            padding: 32px 20px 64px;
        }}

        /* ── 頁首 ── */
        .site-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid var(--border);
            padding-bottom: 18px;
            margin-bottom: 28px;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .site-title {{
            font-size: 1.35rem;
            font-weight: 700;
            color: var(--accent);
            letter-spacing: 0.02em;
        }}
        .site-meta {{
            font-family: "JetBrains Mono", monospace;
            font-size: 0.78rem;
            color: var(--muted);
        }}
        #live-clock {{ color: var(--accent); }}

        /* ── 股價卡片區塊 ── */
        .stock-section {{
            margin-bottom: 32px;
        }}
        .section-label {{
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--muted);
            margin-bottom: 12px;
        }}
        .stock-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 12px;
        }}
        .stock-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 14px 16px;
            transition: transform 0.15s ease;
        }}
        .stock-card:hover {{ transform: translateY(-2px); }}
        .stock-card.up   {{ border-left: 3px solid var(--up);   background: var(--up-bg);   }}
        .stock-card.down {{ border-left: 3px solid var(--down); background: var(--down-bg); }}
        .stock-name  {{ font-size: 0.78rem; color: var(--muted); margin-bottom: 4px; }}
        .stock-price {{ font-family: "JetBrains Mono", monospace; font-size: 1.25rem; font-weight: 600; }}
        .stock-card.up   .stock-price {{ color: var(--up);   }}
        .stock-card.down .stock-price {{ color: var(--down); }}
        .stock-change {{ font-family: "JetBrains Mono", monospace; font-size: 0.78rem; margin-top: 4px; color: var(--muted); }}

        /* ── 分隔線 ── */
        .divider {{
            border: none;
            border-top: 1px solid var(--border);
            margin: 28px 0;
        }}

        /* ── Markdown 內容區 ── */
        .md-body h2 {{
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--accent);
            margin: 32px 0 14px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--border);
        }}
        .md-body h2:first-child {{ margin-top: 0; }}

        /* ── 盤勢評論特別樣式 ── */
        .md-body h2:first-of-type + p {{
            background: #111827;
            border-left: 4px solid var(--accent);
            border-radius: 0 8px 8px 0;
            padding: 16px 20px;
            color: #c9d1d9;
            font-size: 0.95rem;
            line-height: 1.9;
            margin-bottom: 8px;
        }}

        .md-body ul {{
            list-style: none;
            padding: 0;
        }}
        .md-body ul li {{
            padding: 9px 0;
            border-bottom: 1px solid #1c2128;
            font-size: 0.92rem;
            color: #c9d1d9;
        }}
        .md-body ul li:last-child {{ border-bottom: none; }}
        .md-body a {{
            color: var(--accent);
            text-decoration: none;
            font-weight: 500;
        }}
        .md-body a:hover {{ text-decoration: underline; }}

        /* ── 焦點交集 ── */
        .md-body strong {{ color: #f0f6fc; }}

        /* ── 頁尾 ── */
        .site-footer {{
            text-align: center;
            font-size: 0.75rem;
            color: var(--muted);
            margin-top: 48px;
            padding-top: 20px;
            border-top: 1px solid var(--border);
        }}

        @media (max-width: 600px) {{
            .stock-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
    </style>
</head>
<body>
<div class="page-wrapper">

    <!-- 頁首 -->
    <header class="site-header">
        <div class="site-title">📊 台灣股市 AI 精選情報</div>
        <div class="site-meta">
            更新：{time_str}（台北）&nbsp;｜&nbsp; 現在：<span id="live-clock">—</span>
        </div>
    </header>

    <!-- 股價區塊（明顯置頂，在評論之前） -->
    <section class="stock-section">
        <div class="section-label">即時行情</div>
        <div class="stock-grid">
            {stock_cards_html}
        </div>
    </section>

    <hr class="divider">

    <!-- AI 分析內容（評論已被 prompt 要求排第一區段） -->
    <div class="md-body">
        {html_body}
    </div>

    <footer class="site-footer">
        數據來源：Google News RSS &bull; Yahoo Finance &bull; OpenAI GPT-3.5
    </footer>
</div>

<script>
    (function () {{
        function tick() {{
            const el = document.getElementById('live-clock');
            if (el) {{
                el.textContent = new Date().toLocaleString('zh-TW', {{
                    timeZone: 'Asia/Taipei',
                    hour12: false,
                }});
            }}
        }}
        tick();
        setInterval(tick, 1000);
    }})();
</script>
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)

    print("--- 網頁更新完成 ---")

except Exception:
    print(f"失敗：\n{traceback.format_exc()}")
