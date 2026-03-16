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
    # 鎖定 24 小時內新聞，確保內容新鮮度，避免資訊穿越
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
    # 這裡維持加權指數與核心權值股的監控
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
                # 統一格式輸出：名稱: 點數 (漲跌, 幅度%)
                res_list.append(f"{name}: {curr} ({diff}, {pct}%)")
        except:
            res_list.append(f"{name}: 獲取失敗")
    return " ".join(res_list)

try:
    print("--- 啟動 AI 財經主編 (數據同步強化版) ---")
    tw_now = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_now.strftime('%Y-%m-%d %H:%M:%S')
    
    news_pool = get_news_pool(50)
    stocks = get_stock_data()
    
    # 重新設計 Prompt，強制 AI 維持數據與分析的一致性
    prompt = f"""
    任務：將台灣財經資訊轉化為一份「每日彙整報告」。
    語言：全篇必須使用「繁體中文」。
    今日真實股市數據：{stocks}
    當前新聞池內容：{news_pool}
    
    請嚴格依照以下格式輸出 Markdown，並確保分析內容與上述數據 {stocks} 完全吻合：

    # 📈 台股每日彙整報告

    ## 📰 今日重點摘要
    (請從新聞池中歸納出 5 個最重要的台股、經濟事件，並加上簡短分析。格式：1. **關鍵字**：描述)

    ## 📊 市場概況
    當前股市真實數據為：{stocks}。
    (請根據上述數據描述整體大盤與權值股的強弱表現。若數據顯示下跌，分析應偏向謹慎；若上漲則偏向樂觀。)

    ## 🔍 技術分析解讀
    (針對數據 {stocks} 的點數與漲跌幅進行解讀。請判斷目前是多頭、空頭還是盤整，並根據新聞提到的市場心理，給出短期的支撐與壓力觀察建議。)

    ## 😱 市場情緒
    (綜合新聞池與數據表現，判斷投資人情緒。是「極度恐懼」、「謹慎觀望」還是「樂觀追價」？請說明原因。)

    ## ⚠️ 風險提醒
    (從新聞中找出未來 24-48 小時內潛在的利空因素或不確定性，如美股波動、財報公佈或國際地緣政治。)

    ## 🎯 今日觀察重點
    (列出 3 個今日收盤後或明日開盤最值得關注的動向。)

    【嚴格過濾指令】：
    1. 數據唯一性：分析中若提到點數或漲幅，必須與 {stocks} 內容完全一致，嚴禁自行虛構數字。
    2. 時效性檢查：若新聞池中出現「去年」、「國慶」、「10月/12月」等明顯過期字眼，請直接剔除該新聞不予分析。
    """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "你是一位專業的台灣財經分析專家，擅長將雜亂數據與新聞歸納為高品質繁體彙整報告。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    
    md_text = response.choices[0].message.content
    # 使用 nl2br 擴充套件確保換行在 HTML 中正確顯示
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
            h1, h2 {{ border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; margin-top: 1.5em; }}
            strong {{ color: #d73a49; }}
            #update-time {{ color: #666; font-weight: normal; }}
        </style>
    </head>
    <body class="markdown-body">
        <div class="info-banner">
            <p>📋 <strong>最後更新：</strong> {time_str} (台北時間)</p>
            <p>🏦 <strong>監控對象：</strong> 加權指數、台積電 (2330)、鴻海 (2317)</p>
        </div>
        {html_body}
        <hr>
        <p style="text-align: center; color: #999; font-size: 0.8em;">數據來源：Yahoo Finance, Google News RSS</p>
    </body>
    </html>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print(f"--- 網頁更新完成 (數據同步模式) ---")

except Exception as e:
    print(f"失敗: {traceback.format_exc()}")
