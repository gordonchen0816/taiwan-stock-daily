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
    # 鎖定 24 小時內新聞，確保內容新鮮
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
    res_list = []
    for name, code in tks.items():
        try:
            d = yf.download(code, period="5d", interval="1d", progress=False)
            if not d.empty:
                curr = round(float(d['Close'].iloc[-1].item()), 2)
                prev = round(float(d['Close'].iloc[-2].item()), 2)
                diff = round(curr - prev, 2)
                pct = round((diff / prev) * 100, 2)
                res_list.append(f"{name}: {curr} ({diff}, {pct}%)")
        except:
            res_list.append(f"{name}: 獲取失敗")
    return " ".join(res_list)

try:
    print("--- 啟動 AI 財經主編 (彙整報告模式) ---")
    tw_now = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_now.strftime('%Y-%m-%d %H:%M:%S')
    
    news_pool = get_news_pool(50)
    stocks = get_stock_data()
    
    # 重新設計 Prompt，模仿用戶提供的加密貨幣報告格式
    prompt = f"""
    任務：將台灣財經資訊轉化為一份「每日彙整報告」。
    語言：必須全部使用「繁體中文」。
    新聞池：{news_pool}
    今日股市數據：{stocks}
    
    請嚴格依照以下格式輸出 Markdown：

    # 📈 台股每日彙整報告

    ## 📰 今日重點摘要
    (請從新聞池中歸納出 5 個最重要的台股、經濟事件，並加上簡短分析，格式如：1. **關鍵字**：描述)

    ## 📊 市場概況
    (結合今日股市數據 {stocks}，描述整體市場氛圍。例如大盤漲跌、權值股表現，以及新聞中提到的市場信心度)

    ## 🔍 技術分析解讀
    (針對數據 {stocks} 提供解讀。雖然只有開收盤價，但請根據漲跌幅與新聞趨勢，判斷目前是多頭、空頭還是盤整，並說明支撐與壓力點位觀察)

    ## 😱 市場情緒
    (根據新聞池內容，綜合判斷當前台灣投資人的情緒。是極度恐懼、謹慎、還是樂觀？請說明原因)

    ## ⚠️ 風險提醒
    (從新聞中找出未來 24-48 小時內潛在的利空因素或不確定性，如國際戰火、通膨數據、財報公佈等)

    ## 🎯 今日觀察重點
    (列出 3 個今日收盤後或明日開盤最值得關注的動向，如特定法說會、美股表現、或是重要政策討論)

    【過濾守則】：
    - 嚴格剔除日期不符的舊聞（如去年、上個月、國慶、封關）。
    - 若數據與新聞明顯矛盾，以真實數據 {stocks} 為準並剔除錯誤新聞。
    """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "你是一位專業的台灣財經分析專家，擅長將雜亂新聞歸納為高品質彙整報告。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    
    md_text = response.choices[0].message.content
    html_body = markdown.markdown(md_text, extensions=['tables', 'fenced_code', 'nl2br'])

    full_html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>台股每日彙整報告</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
        <style>
            .markdown-body {{ box-sizing: border-box; min-width: 200px; max-width: 980px; margin: 0 auto; padding: 45px; font-family: "PingFang TC", "Microsoft JhengHei", sans-serif; }}
            @media (max-width: 767px) {{ .markdown-body {{ padding: 15px; }} }}
            .info-banner {{ background-color: #f8f9fa; border-left: 5px solid #007bff; padding: 15px; margin-bottom: 30px; font-size: 0.9em; }}
            h1, h2 {{ border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }}
            strong {{ color: #d73a49; }}
        </style>
    </head>
    <body class="markdown-body">
        <div class="info-banner">
            <p>最後更新時間：{time_str} (台北時間)</p>
            <p>數據來源：Google News, Yahoo Finance</p>
        </div>
        {html_body}
        <hr>
        <script>
            // 由於彙整報告較長，不建議在正文放動態時鐘干擾閱讀，維持 banner 靜態更新即可
        </script>
    </body>
    </html>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print(f"--- 網頁更新完成 (彙整報告模式) ---")

except Exception as e:
    print(f"失敗: {traceback.format_exc()}")
