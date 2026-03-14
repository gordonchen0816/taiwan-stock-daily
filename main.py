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

def get_news_pool(limit=45):
    # 加上 when:1d 確保從 Google RSS 抓取的都是 24 小時內的新聞
    url = f"https://news.google.com/rss/search?q=股市+經濟+台灣+台股+when:1d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant&t={random.random()}"
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
                res += f"{name}: {curr} ({diff}, {pct}%) "
        except:
            res += f"{name}: 獲取失敗 "
    return res

try:
    print("--- 啟動 AI 財經主編 (繁體中文強化版) ---")
    tw_now = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_now.strftime('%Y-%m-%d %H:%M:%S')
    
    news_pool = get_news_pool(50)
    stocks = get_stock_data()
    
    # 強化 Prompt：嚴格規範格式與繁體中文
    prompt = f"""
    任務：專業財經主編分類比對。
    新聞池：{news_pool}
    股市數據：{stocks}
    
    【輸出規範 - 嚴格執行】：
    1. 語言：必須使用「繁體中文」。
    2. 格式：請嚴格依照下方格式輸出：
    
    ## 📰 今日各報頭條摘要
    ### 🏦 財經綜合焦點 (5則)
    (條列5則新聞，標題 - 來源)
    
    ### 📖 經濟日報精選 (5則)
    (條列5則新聞，標題 - 來源)
    
    ### 🌐 Google RSS 熱門 (5則)
    (條列5則新聞，標題 - 來源)
    
    ## 📌 三大媒體焦點交集 (真正重複報導的事件)
    [焦點 1]：(描述)
    [焦點 2]：(描述)
    [焦點 3]：(描述)
    
    ## 📈 個股現況與大盤分析
    數據：{stocks}
    評論：(針對今日新聞與數據給予一段 100 字內的專業分析評論)

    【過濾指令】：
    - 剔除過期月份(10月、12月)或過期標題(如國慶、封關)。
    - 若指數點數與當前數據差距超過3000點，視為舊聞剔除。
    """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "你是一位專業的台灣財經分析專家，僅使用繁體中文回答。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    
    md_text = response.choices[0].message.content
    html_body = markdown.markdown(md_text, extensions=['tables', 'fenced_code'])

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
            .info-banner {{ background-color: #f8f9fa; border-left: 5px solid #007bff; padding: 15px; margin-bottom: 30px; }}
            #live-clock {{ color: #d73a49; font-weight: bold; }}
        </style>
    </head>
    <body class="markdown-body">
        <h1>台灣股市 AI 精選情報</h1>
        <div class="info-banner">
            <p>最後更新時間：{time_str} (台北時間)</p>
            <p>您的瀏覽時間：<span id="live-clock">讀取中...</span></p>
        </div>
        {html_body}
        <hr>
        <p style="text-align: center; color: #666;">數據來源：Google News, Yahoo Finance</p>
        <script>
            function startClock() {{
                setInterval(() => {{
                    const now = new Date();
                    document.getElementById('live-clock').innerText = now.toLocaleString('zh-TW', {{
                        timeZone: 'Asia/Taipei', hour12: false
                    }});
                }}, 1000);
            }}
            startClock();
        </script>
    </body>
    </html>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print(f"--- 網頁更新完成 (繁體中文版) ---")

except Exception as e:
    print(f"失敗: {traceback.format_exc()}")
