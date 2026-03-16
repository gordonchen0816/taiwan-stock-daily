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
    """計算 RSI 指標"""
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_detailed_stock_info():
    """抓取股市數據並產生 HTML 字卡與 AI 摘要"""
    # 監控標的：加權、櫃買、台指期、台積電、精材、鴻海
    tks = {
        "加權指數": "^TWII",
        "櫃買指數": "^TWOII",
        "台指近月": "WTX&=F",
        "台積電": "2330.TW",
        "精材": "7769.TW",
        "鴻海": "2317.TW"
    }
    
    cards_html = ""
    summary_for_ai = ""
    
    for name, code in tks.items():
        try:
            # 抓取 40 天數據以計算 SMA20 與 RSI
            df = yf.download(code, period="40d", interval="1d", progress=False)
            if not df.empty:
                # 取得最新與昨日收盤
                curr_price = round(float(df['Close'].iloc[-1].item()), 2)
                prev_price = round(float(df['Close'].iloc[-2].item()), 2)
                diff = round(curr_price - prev_price, 2)
                pct = round((diff / prev_price) * 100, 2)
                
                # 計算指標
                sma7 = round(df['Close'].rolling(window=7).mean().iloc[-1].item(), 2)
                sma20 = round(df['Close'].rolling(window=20).mean().iloc[-1].item(), 2)
                rsi_val = round(calculate_rsi(df['Close']).iloc[-1].item(), 2)
                
                # 均線趨勢與台股顏色習慣 (紅漲綠跌)
                trend = "均線多頭" if sma7 > sma20 else "均線空頭"
                color = "#d73a49" if diff >= 0 else "#22863a"
                
                # 格式化 HTML 字卡
                cards_html += f"""
                <div class="stock-card">
                    <div class="stock-name">{name}</div>
                    <div class="stock-price">${curr_price:,}</div>
                    <div class="stock-change" style="color:{color}">{'+' if diff >= 0 else ''}{diff} ({pct}%)</div>
                    <div class="stock-meta">RSI: {rsi_val}</div>
                    <div class="stock-meta">SMA7: ${sma7:,}</div>
                    <div class="stock-meta">SMA20: ${sma20:,}</div>
                    <div class="stock-trend">{trend}</div>
                </div>
                """
                summary_for_ai += f"{name}: {curr_price} ({pct}%, {trend}, RSI:{rsi_val}); "
        except:
            cards_html += f"<div class='stock-card'>{name}: 讀取失敗</div>"
            
    return cards_html, summary_for_ai

def get_news_pool(limit=45):
    """從 Google RSS 獲取 24 小時內新聞"""
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
    print("--- 啟動 AI 財經主編 (完整最終版) ---")
    tw_now = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_now.strftime('%Y-%m-%d %H:%M:%S')
    
    # 執行數據獲取
    stock_cards_html, stock_summary_text = get_detailed_stock_info()
    news_pool = get_news_pool(50)
    
    # AI 撰寫報告指令
    prompt = f"""
    任務：將財經資訊轉化為專業「每日彙整報告」。
    語言：全篇繁體中文。
    數據參考：{stock_summary_text}
    新聞參考：{news_pool}
    
    請依下列格式輸出 Markdown：

    ## 📰 今日重點摘要
    (歸納 5 個關鍵事件。格式：1. **[關鍵字]**：描述)

    ## 📊 市場概況與技術解讀
    (結合數據 {stock_summary_text}，分析加權、櫃買與台指期的表現與連動關係。)

    ## 🔍 技術分析與心理
    (解釋 RSI 與均線趨勢代表的意義。目前市場是過熱還是超跌？)

    ## 😱 市場情緒與風險提醒
    (判斷投資人情緒，找出未來 24 小時潛在風險。)

    ## 🎯 今日觀察重點
    (列出 3 個明日觀察點。)

    【要求】：嚴禁舊聞，點數必須精確對應。
    """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "你是一位台灣專業財經主編，擅長歸納數據與新聞趨勢。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    
    md_text = response.choices[0].message.content
    html_body = markdown.markdown(md_text, extensions=['nl2br'])

    # 生成 HTML 檔案
    full_html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>台股每日彙整報告</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
        <style>
            .markdown-body {{ box-sizing: border-box; min-width: 200px; max-width: 1000px; margin: 0 auto; padding: 45px; font-family: sans-serif; }}
            @media (max-width: 767px) {{ .markdown-body {{ padding: 15px; }} }}
            .info-banner {{ background-color: #f8f9fa; border-left: 5px solid #0366d6; padding: 15px; margin-bottom: 25px; border-radius: 4px; }}
            .cards-container {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 30px; }}
            .stock-card {{ 
                background: #fff; border: 1px solid #e1e4e8; border-radius: 10px; padding: 12px; 
                flex: 1; min-width: 150px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            }}
            .stock-name {{ font-weight: bold; font-size: 1em; color: #0366d6; margin-bottom: 4px; }}
            .stock-price {{ font-size: 1.25em; font-weight: bold; color: #24292e; }}
            .stock-change {{ font-size: 0.85em; margin-bottom: 8px; font-weight: bold; }}
            .stock-meta {{ font-size: 0.75em; color: #586069; line-height: 1.4; }}
            .stock-trend {{ margin-top: 8px; font-size: 0.75em; font-weight: bold; color: #0366d6; background: #f1f8ff; padding: 2px 8px; border-radius: 10px; display: inline-block; }}
        </style>
    </head>
    <body class="markdown-body">
        <h1>📈 台股每日彙整報告</h1>
        <div class="info-banner">
            📋 <strong>最後更新：</strong> {time_str} (台北時間)
        </div>
        
        <h2>📊 市場數據監測</h2>
        <div class="cards-container">
            {stock_cards_html}
        </div>

        {html_body}
        <hr>
        <p style="text-align: center; color: #999; font-size: 0.7em;">Data Source: Yahoo Finance & Google News</p>
    </body>
    </html>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print("--- 網頁生成成功 ---")

except Exception as e:
    print(f"失敗: {traceback.format_exc()}")
