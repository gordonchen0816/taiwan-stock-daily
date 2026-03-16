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
import json

# 1. 配置 OpenAI Client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_detailed_stock_info():
    tks = {
        "加權指數": "^TWII",
        "櫃買指數": "^TWOII",
        "台指近月": "WTX&=F",
        "台積電": "2330.TW",
        "鴻勁": "7769.TW",
        "鴻海": "2317.TW"
    }
    cards_html = ""
    summary_for_ai = ""
    for name, code in tks.items():
        try:
            df = yf.download(code, period="40d", interval="1d", progress=False)
            if not df.empty:
                curr_price = round(float(df['Close'].iloc[-1].item()), 2)
                prev_price = round(float(df['Close'].iloc[-2].item()), 2)
                diff = round(curr_price - prev_price, 2)
                pct = round((diff / prev_price) * 100, 2)
                sma7 = round(df['Close'].rolling(window=7).mean().iloc[-1].item(), 2)
                sma20 = round(df['Close'].rolling(window=20).mean().iloc[-1].item(), 2)
                rsi_val = round(calculate_rsi(df['Close']).iloc[-1].item(), 2)
                trend = "均線多頭" if sma7 > sma20 else "均線空頭"
                color = "#d73a49" if diff >= 0 else "#22863a"
                trend_color = "#f1f8ff" if sma7 > sma20 else "#fff5f5"
                trend_text_color = "#0366d6" if sma7 > sma20 else "#d73a49"
                cards_html += f"""
                <div class="stock-card">
                    <div class="stock-name">{name}</div>
                    <div class="stock-price">${curr_price:,}</div>
                    <div class="stock-change" style="color:{color}">{'+' if diff >= 0 else ''}{diff} ({pct}%)</div>
                    <div class="stock-meta">RSI: {rsi_val} | SMA7: {sma7:,}</div>
                    <div class="stock-meta">SMA20: ${sma20:,}</div>
                    <div class="stock-trend" style="background:{trend_color}; color:{trend_text_color}">{trend}</div>
                </div>"""
                summary_for_ai += f"{name}: {curr_price} ({pct}%, {trend}); "
        except:
            cards_html += f"<div class='stock-card'>{name}: 讀取失敗</div>"
    return cards_html, summary_for_ai

def get_news_pool():
    news_list = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # 來源 A: Anue 鉅亨網 API (抓取最新 20 則)
    try:
        anue_url = "https://api.cnyes.com/media/api/v1/newslist/category/tw_stock?limit=20"
        r = requests.get(anue_url, headers=headers, timeout=10)
        data = r.json()
        for item in data['items']['data']:
            news_list.append(f"【鉅亨網】{item['title']}")
    except: pass

    # 來源 B: Yahoo 財經 RSS
    try:
        yahoo_url = "https://tw.stock.yahoo.com/rss/tw-stock"
        r = requests.get(yahoo_url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.content, features="xml")
        for item in soup.find_all('item', limit=15):
            news_list.append(f"【Yahoo財經】{item.title.text}")
    except: pass

    # 來源 C: Google News (針對經濟日報、工商時報、MoneyDJ)
    queries = ["經濟日報+台股", "工商時報+台股", "MoneyDJ+台股"]
    for q in queries:
        try:
            g_url = f"https://news.google.com/rss/search?q={q}+when:1d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            r = requests.get(g_url, headers=headers, timeout=10)
            soup = BeautifulSoup(r.content, features="xml")
            for item in soup.find_all('item', limit=8):
                news_list.append(item.title.text)
        except: pass

    return list(set(news_list)) # 去重

try:
    print("--- 啟動 AI 財經主編 (多源聚合版) ---")
    tw_now = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_now.strftime('%Y-%m-%d %H:%M:%S')
    
    stock_cards_html, stock_summary_text = get_detailed_stock_info()
    news_pool = get_news_pool()
    
    # AI 報告指令
    prompt = f"""
    任務：專業台股日報。語言：繁體中文。
    數據：{stock_summary_text}
    來源池：{news_pool}
    
    請依下列格式輸出：
    ## 📰 今日重點摘要
    (從 {len(news_pool)} 則新聞中歸納 5 個最重要事件，格式：1. **[標籤]**：描述)

    ## 📊 市場概況與技術解讀
    (結合數據 {stock_summary_text} 與新聞池熱度，分析大盤與個股。)

    ## 🔍 全方位新聞清單 (篩選後精選 15-20 則)
    (請將新聞池中值得讀的標題列出，按來源分類)

    ## 🎯 今日觀察重點
    (列出 3 個明日觀察點)
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini", # 建議使用 mini 處理大量新聞較快且便宜
        messages=[{"role": "system", "content": "你是一位專業台股主編。"}, {"role": "user", "content": prompt}],
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
        <title>台股多源聚合報告</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
        <style>
            body {{ background-color: #0d1117; color: #c9d1d9; max-width: 1000px; margin: 0 auto; padding: 30px; }}
            .markdown-body {{ background-color: transparent !important; color: inherit !important; }}
            .info-banner {{ background-color: #f6f8fa; color: #24292e; border-left: 5px solid #0366d6; padding: 12px; margin-bottom: 25px; border-radius: 4px; }}
            .cards-container {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin-bottom: 30px; }}
            .stock-card {{ background: #fff; border: 1px solid #e1e4e8; border-radius: 10px; padding: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
            .stock-name {{ font-weight: bold; color: #0366d6; }}
            .stock-price {{ font-size: 1.2em; font-weight: bold; color: #24292e; }}
            .stock-meta {{ font-size: 0.75em; color: #586069; }}
            .stock-trend {{ margin-top: 5px; font-size: 0.75em; font-weight: bold; padding: 2px 8px; border-radius: 10px; display: inline-block; }}
        </style>
    </head>
    <body class="markdown-body">
        <h1>📈 台股多源聚合報告</h1>
        <div class="info-banner">📋 更新時間：{time_str} | 累計偵測新聞：{len(news_pool)} 則</div>
        <div class="cards-container">{stock_cards_html}</div>
        {html_body}
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
except Exception as e:
    print(f"失敗: {traceback.format_exc()}")
