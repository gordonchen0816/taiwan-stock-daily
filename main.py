import os
import yfinance as yf
from openai import OpenAI
import requests
import random
import traceback
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import markdown
import pandas as pd

# 1. 配置 OpenAI Client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_detailed_stock_info():
    # 定義監控標的
    tks = {
        "加權指數": "^TWII",
        "OTC指數": "^TWOII",
        "台積電": "2330.TW",
        "精材": "7769.TW",
        "鴻海": "2317.TW"
    }
    
    cards_html = ""
    summary_for_ai = ""
    
    for name, code in tks.items():
        try:
            # 抓取過去 40 天數據以計算 RSI 與 SMA20
            df = yf.download(code, period="40d", interval="1d", progress=False)
            if not df.empty:
                # 取得最新與昨日數據
                curr_price = round(float(df['Close'].iloc[-1].item()), 2)
                prev_price = round(float(df['Close'].iloc[-2].item()), 2)
                diff = round(curr_price - prev_price, 2)
                pct = round((diff / prev_price) * 100, 2)
                
                # 計算技術指標
                sma7 = round(df['Close'].rolling(window=7).mean().iloc[-1].item(), 2)
                sma20 = round(df['Close'].rolling(window=20).mean().iloc[-1].item(), 2)
                rsi = round(calculate_rsi(df['Close']).iloc[-1].item(), 2)
                
                # 均線趨勢判斷
                trend = "均線多頭" if sma7 > sma20 else "均線空頭"
                color = "#d73a49" if diff > 0 else "#22863a" # 紅漲綠跌 (台股習慣)
                
                # 建立 HTML 字卡格式
                cards_html += f"""
                <div class="stock-card">
                    <div class="stock-name">{name}</div>
                    <div class="stock-price">${curr_price}</div>
                    <div class="stock-change" style="color:{color}">{'+' if diff > 0 else ''}{diff} ({pct}%)</div>
                    <div class="stock-meta">RSI: {rsi}</div>
                    <div class="stock-meta">SMA7: ${sma7}</div>
                    <div class="stock-meta">SMA20: ${sma20}</div>
                    <div class="stock-trend">{trend}</div>
                </div>
                """
                summary_for_ai += f"{name}: {curr_price} ({pct}%, {trend}); "
        except:
            cards_html += f"<div class='stock-card'>{name}: 讀取失敗</div>"
            
    return cards_html, summary_for_ai

def get_news_pool(limit=45):
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

try:
    print("--- 啟動 AI 財經主編 (數據字卡版) ---")
    tw_now = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_now.strftime('%Y-%m-%d %H:%M:%S')
    
    # 獲取字卡 HTML 與 AI 分析用的摘要
    stock_cards, stock_summary = get_detailed_stock_info()
    news_pool = get_news_pool(50)
    
    prompt = f"""
    任務：將台灣財經資訊轉化為一份「每日彙整報告」。
    今日股市表現：{stock_summary}
    新聞池內容：{news_pool}
    
    請依照以下格式輸出繁體中文 Markdown：
    ## 📰 今日重點摘要
    (歸納5個重點，標籤化處理如 1. **[法案/事件]**：描述)

    ## 📊 市場概況與技術解讀
    (參考最新數據 {stock_summary}，分析大盤與權值股的連動，並解釋技術面趨勢)

    ## 😱 市場情緒與風險提醒
    (綜合新聞判斷情緒，列出未來 24 小時風險)

    ## 🎯 今日觀察重點
    (列出3個明日開盤觀察點)
    """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "你是一位專業台灣財經分析專家，擅長整合技術指標與新聞。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    
    md_text = response.choices[0].message.content
    html_body = markdown.markdown(md_text, extensions=['nl2br'])

    full_html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>台股每日彙整報告</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
        <style>
            .markdown-body {{ box-sizing: border-box; min-width: 200px; max-width: 980px; margin: 0 auto; padding: 45px; font-family: sans-serif; }}
            @media (max-width: 767px) {{ .markdown-body {{ padding: 15px; }} }}
            .info-banner {{ background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px; font-size: 0.9em; }}
            /* 字卡容器樣式 */
            .cards-container {{ display: flex; flex-wrap: wrap; gap: 15px; margin-bottom: 30px; }}
            .stock-card {{ 
                background: #fff; border: 1px solid #e1e4e8; border-radius: 10px; padding: 15px; 
                flex: 1; min-width: 160px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }}
            .stock-name {{ font-weight: bold; font-size: 1.1em; color: #0366d6; margin-bottom: 5px; }}
            .stock-price {{ font-size: 1.4em; font-weight: bold; }}
            .stock-change {{ font-size: 0.9em; margin-bottom: 10px; }}
            .stock-meta {{ font-size: 0.8em; color: #586069; line-height: 1.4; }}
            .stock-trend {{ margin-top: 8px; font-size: 0.85em; font-weight: bold; color: #24292e; background: #f1f8ff; display: inline-block; padding: 2px 6px; border-radius: 4px; }}
        </style>
    </head>
    <body class="markdown-body">
        <h1>📈 台股每日彙整報告</h1>
        <div class="info-banner">
            📋 最後更新：{time_str} (台北時間)
        </div>
        
        <h2>📊 市場數據監測</h2>
        <div class="cards-container">
            {stock_cards}
        </div>

        {html_body}
        <hr>
        <p style="text-align: center; color: #999; font-size: 0.8em;">數據來源：Yahoo Finance (20日均線計算), Google News</p>
    </body>
    </html>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print("--- 網頁更新完成 (數據字卡版) ---")

except Exception as e:
    print(f"失敗: {traceback.format_exc()}")
