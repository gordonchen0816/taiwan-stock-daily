import os
import yfinance as yf
from openai import OpenAI
import requests
import random
import traceback
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import markdown

# 1. 配置 OpenAI Client (適用於最新 1.0+ 版本)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_news_pool(limit=45):
    """抓取一個大的新聞池，讓 AI 有足夠素材進行分類與交集比對"""
    url = f"https://news.google.com/rss/search?q=股市+經濟+台灣+台股&hl=zh-TW&gl=TW&ceid=TW:zh-Hant&t={random.random()}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    pool = []
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, features="xml")
        items = soup.find_all('item', limit=limit)
        for item in items:
            pool.append(item.title.text)
        return pool
    except:
        return ["無法取得即時新聞池"]

def get_stock_data():
    """抓取大盤及重點個股數據"""
    tks = {"加權指數": "^TWII", "台積電": "2330.TW", "鴻海": "2317.TW"}
    res = ""
    for name, code in tks.items():
        try:
            d = yf.download(code, period="5d", interval="1d", progress=False)
            if not d.empty:
                curr = round(float(d['Close'].iloc[-1].item()), 2)
                prev = round(float(d['Close'].iloc[-2].item()), 2)
                diff = round(curr - prev, 2)
                pct = round((diff / prev) * 100, 2)
                res += f"{name}: {curr} (漲跌: {diff}, 幅度: {pct}%)\n"
        except:
            res += f"{name}: 獲取失敗\n"
    return res

try:
    print("--- 啟動 AI 財經主編 (動態網頁模式) ---")
    
    # 設定台北時間 (UTC+8)
    tw_now = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_now.strftime('%Y-%m-%d %H:%M:%S')
    
    # 抓取數據
    news_pool = get_news_pool(50)
    stocks = get_stock_data()
    
    # 構建 AI 指令
    prompt = f"""
    任務：你是專業財經主編。請從以下新聞池中，依照要求分類並進行交叉比對。

    【今日原始新聞池】：
    {news_pool}

    【最新股市數據】：
    {stocks}

    指令格式：
    ### 📰 今日各報頭條摘要
    #### 🏦 財經綜合焦點 (5則)
    - (列出 5 則)
    #### 📖 經濟日報精選 (5則)
    - (列出 5 則)
    #### 🌐 Google RSS 熱門 (5則)
    - (列出 5 則)

    ### 📌 三大媒體焦點交集 (真正重複報導的事件)
    - [焦點 1]：描述並說明原因。
    - [焦點 2]：描述並說明原因。
    - [焦點 3]：描述並說明原因。

    ### 📈 個股現況與大盤分析
    - 數據分析：{stocks}
    - 操作建議：(給予專業短評)
    """
    
    # 呼叫 OpenAI
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "你是一位專業的台灣財經分析專家，請使用 Markdown 格式撰寫。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    
    # 將 AI 的 Markdown 轉為 HTML
    md_text = response.choices[0].message.content
    html_body = markdown.markdown(md_text, extensions=['tables', 'fenced_code'])

    # 3. 組合 HTML 模板 (包含每秒跳動的時鐘)
    full_html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>台灣股市 AI 精選情報</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
        <style>
            .markdown-body {{ box-sizing: border-box; min-width: 200px; max-width: 980px; margin: 0 auto; padding: 45px; }}
            @media (max-width: 767px) {{ .markdown-body {{ padding: 15px; }} }}
            .info-banner {{ background-color: #f0f7ff; border: 1px solid #cce3ff; padding: 20px; border-radius: 10px; margin-bottom: 30px; }}
            #live-clock {{ color: #0056b3; font-weight: bold; font-size: 1.1em; }}
        </style>
    </head>
    <body class="markdown-body">
        <h1>📊 台灣股市 AI 精選情報</h1>
        <div class="info-banner">
            <p>📋 <strong>最後更新 (伺服器數據抓取)：</strong> {time_str}</p>
            <p>🕒 <strong>您目前的瀏覽時間 (每秒更新)：</strong> <span id="live-clock">讀取中...</span></p>
        </div>

        {html_body}

        <hr>
        <p style="text-align: center; color: #666;">
            本報告由 AI 自動化系統生成 | 更新於台北時間 {time_str}<br>
            數據來源：Google News RSS, Yahoo Finance
        </p>

        <script>
            function startClock() {{
                setInterval(() => {{
                    const now = new Date();
                    document.getElementById('live-clock').innerText = now.toLocaleString('zh-TW', {{
                        timeZone: 'Asia/Taipei',
                        hour12: false
                    }});
                }}, 1000);
            }}
            startClock();
        </script>
    </body>
    </html>
    """

    # 寫入 index.html (GitHub Pages 會自動讀取這個檔案)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    
    print(f"--- 報告成功生成 index.html！時間：{time_str} ---")

except Exception as e:
    print(f"執行失敗: {traceback.format_exc()}")
