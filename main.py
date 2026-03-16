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
    # 加上 when:1d 確保抓取 24 小時內新聞
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
    # --- 在此調整個股排列順序 ---
    # 按照你想顯示的優先順序排列即可
    tks = {
        "加權指數": "^TWII", 
        "台積電": "2330.TW", 
        "鴻海": "2317.TW"
    }
    # --------------------------
    res_list = []
    for name, code in tks.items():
        try:
            d = yf.download(code, period="5d", interval="1d", progress=False)
            if not d.empty:
                curr = round(float(d['Close'].iloc[-1].item()), 2)
                prev = round(float(d['Close'].iloc[-2].item()), 2)
                diff = round(curr - prev, 2)
                pct = round((diff / prev) * 100, 2)
                # 數據精簡格式：名稱: 點數 (漲跌, 幅度%)
                res_list.append(f"{name}: {curr} ({diff}, {pct}%)")
        except:
            res_list.append(f"{name}: 獲取失敗")
    return " ".join(res_list)

try:
    print("--- 啟動 AI 財經主編 (最終定錨版) ---")
    tw_now = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_now.strftime('%Y-%m-%d %H:%M:%S')
    
    news_pool = get_news_pool(50)
    stocks = get_stock_data()
    
    # 強化 Prompt：確保格式、繁體、分行
    prompt = f"""
    任務：專業財經主編分類比對。
    要求：全篇使用「繁體中文」。
    新聞池：{news_pool}
    股市數據：{stocks}
    
    請嚴格依照此 Markdown 格式輸出，標題層級與換行不能變動：

    ## 📰 今日各報頭條摘要

    ### 🏦 財經綜合焦點 (5則)
    (5則新聞，格式：標題 - 來源)

    ### 📖 經濟日報精選 (5則)
    (5則新聞，格式：標題 - 來源)

    ### 🌐 Google RSS 熱門 (5則)
    (5則新聞，格式：標題 - 來源)

    ## 📌 三大媒體焦點交集 (真正重複報導的事件)
    [焦點 1]：描述 (請單獨換行)
    [焦點 2]：描述 (請單獨換行)
    [焦點 3]：描述 (請單獨換行)

    ## 📈 個股現況與大盤分析
    數據：{stocks}
    評論：(針對今日數據與國際局勢進行專業評論，100字內)

    【過濾守則】：剔除過期月份、國慶、封關等舊聞。數據與當前數據差距過大亦剔除。
    """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "你是一位專業的台灣財經專家，僅使用繁體中文。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    
    md_text = response.choices[0].message.content
    # nl2br 擴充功能確保 [焦點] 能夠正確換行
    html_body = markdown.markdown(md_text, extensions=['tables', 'fenced_code', 'nl2br'])

    full_html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>台灣股市 AI 精選情報</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
        <style>
            .markdown-body {{ box-sizing: border-box; min-width: 200px; max-width: 980px; margin: 0 auto; padding: 45px; font-family: "PingFang TC", "Microsoft JhengHei", sans-serif; }}
            @media (max-width: 767px) {{ .markdown-body {{ padding: 15px; }} }}
            .info-banner {{ background-color: #f8f9fa; border-left: 5px solid #007bff; padding: 15px; margin-bottom: 30px; font-size: 0.95em; }}
            #live-clock {{ color: #d73a49; font-weight: bold; }}
            h1, h2, h3 {{ border-bottom: none !important; }}
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
        <p style="text-align: center; color: #666; font-size: 0.8em;">數據來源：Google News, Yahoo Finance</p>
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
    print(f"--- 網頁更新完成 (最終定錨版) ---")

except Exception as e:
    print(f"失敗: {traceback.format_exc()}")
