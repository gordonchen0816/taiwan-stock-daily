import os
import requests
from bs4 import BeautifulSoup
import yfinance as yf
from openai import OpenAI
import markdown
from datetime import datetime

# 1. 初始化 OpenAI 客戶端 (會自動讀取 GitHub Secrets 的環境變數)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_stock_data():
    """獲取即時股市數據"""
    tks = {"加權指數": "^TWII", "台積電": "2330.TW", "鴻海": "2317.TW"}
    data_summary = ""
    for name, symbol in tks.items():
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d")
        if len(hist) >= 2:
            price = hist['Close'].iloc[-1]
            change = price - hist['Close'].iloc[-2]
            pct = (change / hist['Close'].iloc[-2]) * 100
            data_summary += f"{name}: {price:.2f} (漲跌: {change:.2f}, 幅度: {pct:.2f}%)\n"
    return data_summary

def get_news(query):
    """抓取 Google News RSS 並強制篩選 24 小時內新聞"""
    # 關鍵字後方加入 when:1d 確保時效性
    url = f"https://news.google.com/rss/search?q={query}+when:1d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    res = requests.get(url)
    soup = BeautifulSoup(res.content, "xml")
    items = soup.find_all("item")[:15]
    news_list = []
    for item in items:
        news_list.append(f"{item.title.text} - {item.source.text}")
    return "\n".join(news_list)

def analyze_news(stock_info, news_pool):
    """發送給 AI 進行過濾與深度分析"""
    prompt = f"""
    你是台灣專業財經報紙主編。請根據以下原始資訊撰寫一份簡報。
    
    【當前真實數據】:
    {stock_info}
    
    【待處理新聞池】:
    {news_pool}
    
    【重要指令 - 請嚴格遵守】:
    1. 檢查時效性：若新聞標題包含過期月份(如10月、12月)或過期節日(如國慶、春節)，請直接剔除。
    2. 檢查邏輯：若新聞提到的指數(如2萬點、3萬點)與當前真實數據差距超過 3000 點，視為舊聞，請直接剔除。
    3. 分類摘要：請將精選出的「真正今日新聞」分為「財經綜合」、「個股要聞」、「國際影響」。
    4. 焦點交集：找出 3 條今天各大媒體共同關注的「焦點交集」。
    5. 專業口氣：以客觀、精煉的財經主編語氣撰寫。
    """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# --- 執行流程 ---
print("正在獲取數據...")
stock_summary = get_stock_data()
# 分別抓取不同維度的關鍵字，增加廣度
news_pool = get_news("台股+大盤") + "\n" + get_news("台積電+半導體") + "\n" + get_news("台灣+經濟成長")

print("AI 正在分析與過濾舊聞...")
ai_analysis = analyze_news(stock_summary, news_pool)

# --- 生成網頁內容 ---
now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
html_content = markdown.markdown(ai_analysis)

full_html = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>台股 AI 精選情報</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
    <style>
        body {{ box-sizing: border-box; min-width: 200px; max-width: 980px; margin: 0 auto; padding: 45px; }}
        .header {{ border-bottom: 2px solid #333; margin-bottom: 20px; padding-bottom: 10px; }}
        .footer {{ margin-top: 50px; font-size: 0.8em; color: #666; border-top: 1px solid #eee; padding-top: 20px; }}
        .live-time {{ color: #d73a49; font-weight: bold; }}
    </style>
</head>
<body class="markdown-body">
    <div class="header">
        <h1>📊 台灣股市 AI 精選情報</h1>
        <p>📋 最後更新 (伺服器抓取)：<strong>{now_str}</strong></p>
        <p>🕒 您目前的瀏覽時間：<span id="clock" class="live-time"></span></p>
    </div>

    <div class="content">
        {html_content}
    </div>

    <hr>
    <h3>📈 即時市場數據參考</h3>
    <pre><code>{stock_summary}</code></pre>

    <div class="footer">
        <p>數據來源：Google News RSS, Yahoo Finance API<br>
        本頁面由 AI 自動彙整生成，僅供參考，投資請謹慎評估風險。</p>
    </div>

    <script>
        function updateClock() {{
            const now = new Date();
            document.getElementById('clock').innerText = now.toLocaleString();
        }}
        setInterval(updateClock, 1000);
        updateClock();
    </script>
</body>
</html>
"""

# 寫入檔案
with open("index.html", "w", encoding="utf-8") as f:
    f.write(full_html)

print("網頁更新成功！")
