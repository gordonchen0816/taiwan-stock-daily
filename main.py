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

def manage_memory(new_entry=None):
    """記憶中樞：負責讀取與存儲過去 7 天的紀錄"""
    file_path = "history.json"
    history = []
    
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except: history = []

    if new_entry:
        history.append(new_entry)
        history = history[-7:] # 只保留最近 7 天
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=4)
            
    return history

def get_detailed_stock_info():
    tks = {
        "加權指數": "^TWII", "櫃買指數": "^TWOII", "台指近月": "WTX&=F",
        "台積電": "2330.TW", "鴻勁": "7769.TW", "鴻海": "2317.TW"
    }
    cards_html = ""
    summary_data = {}
    for name, code in tks.items():
        try:
            df = yf.download(code, period="40d", interval="1d", progress=False)
            if not df.empty:
                curr_p = round(float(df['Close'].iloc[-1].item()), 2)
                prev_p = round(float(df['Close'].iloc[-2].item()), 2)
                diff = round(curr_p - prev_p, 2)
                pct = round((diff / prev_p) * 100, 2)
                sma20 = round(df['Close'].rolling(window=20).mean().iloc[-1].item(), 2)
                rsi_val = round(calculate_rsi(df['Close']).iloc[-1].item(), 2)
                
                trend = "多頭" if curr_p > sma20 else "空頭"
                color = "#d73a49" if diff >= 0 else "#22863a"
                
                cards_html += f"""
                <div class="stock-card">
                    <div class="stock-name">{name}</div>
                    <div class="stock-price">${curr_p:,}</div>
                    <div class="stock-change" style="color:{color}">{'+' if diff >= 0 else ''}{diff} ({pct}%)</div>
                    <div class="stock-meta">RSI: {rsi_val} | 趨勢: {trend}</div>
                </div>"""
                summary_data[name] = {"price": curr_p, "pct": pct, "trend": trend, "rsi": rsi_val}
        except: pass
    return cards_html, summary_data

def get_news_pool():
    news = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    # 來源：鉅亨網
    try:
        r = requests.get("https://api.cnyes.com/media/api/v1/newslist/category/tw_stock?limit=15", timeout=10)
        for item in r.json()['items']['data']: news.append(f"【鉅亨】{item['title']}")
    except: pass
    # 來源：Yahoo
    try:
        r = requests.get("https://tw.stock.yahoo.com/rss/tw-stock", timeout=10)
        soup = BeautifulSoup(r.content, features="xml")
        for item in soup.find_all('item', limit=10): news.append(f"【Yahoo】{item.title.text}")
    except: pass
    return list(set(news))

try:
    print("--- 啟動進化版 AI Agent (具備跨日記憶) ---")
    tw_now = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_now.strftime('%Y-%m-%d %H:%M:%S')

    # 1. 讀取過去記憶
    past_history = manage_memory()
    memory_context = "無先前紀錄" if not past_history else json.dumps(past_history[-3:], ensure_ascii=False)

    # 2. 獲取今日數據
    stock_cards_html, stock_summary = get_detailed_stock_info()
    news_pool = get_news_pool()

    # 3. AI Agent 決策分析 (思考構面：對比過去與現在)
    prompt = f"""
    任務：你是資深台股分析代理人。請比對歷史記憶並分析今日走勢。
    
    【歷史記憶】：{memory_context}
    【今日數據】：{json.dumps(stock_summary, ensure_ascii=False)}
    【今日新聞】：{news_pool[:30]}

    請依格式輸出 Markdown：
    ## 🧠 跨日趨勢追蹤 (重點)
    (請比對歷史記憶，告訴讀者今日走勢是延續還是反轉？例如：連續三日上漲、RSI從過熱回落等)

    ## 📰 今日核心解讀
    (歸納今日最影響盤勢的 3 件大事)

    ## 📊 數據觀測清單
    (條列今日監控標的的異常狀態)

    ## 🎯 明日觀察站
    (給出具體的支撐或壓力觀察點)
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "你是一位具備長期記憶能力的台股分析代理人。"},
                  {"role": "user", "content": prompt}],
        temperature=0.3
    )
    
    ai_report = response.choices[0].message.content
    
    # 4. 存入今日記憶 (供明天使用)
    today_entry = {
        "date": time_str[:10],
        "market_index": stock_summary.get("加權指數", {}).get("price"),
        "sentiment": ai_report[:100] # 存儲摘要作為語境
    }
    manage_memory(today_entry)

    # 5. 生成網頁 (與之前風格一致但更精簡)
    html_report = markdown.markdown(ai_report, extensions=['nl2br'])
    full_html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
        <style>
            body {{ background-color: #0d1117; color: #c9d1d9; max-width: 900px; margin: 0 auto; padding: 20px; }}
            .markdown-body {{ background: transparent !important; color: inherit !important; }}
            .cards-container {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; margin-bottom: 20px; }}
            .stock-card {{ background: #fff; border-radius: 8px; padding: 12px; color: #24292e; }}
            .stock-name {{ font-weight: bold; color: #0366d6; }}
            .stock-price {{ font-size: 1.2em; font-weight: bold; }}
            .info-banner {{ background: #f6f8fa; color: #24292e; padding: 10px; border-radius: 4px; margin-bottom: 20px; border-left: 5px solid #2ecc71; }}
        </style>
    </head>
    <body class="markdown-body">
        <h1>🚀 AI 代理人：台股跨日分析報告</h1>
        <div class="info-banner">📅 更新時間：{time_str} | 已累積記憶：{len(past_history)+1} 天</div>
        <div class="cards-container">{stock_cards_html}</div>
        {html_report}
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(full_html)
    print("--- 報告與記憶存儲完成 ---")

except Exception as e:
    print(f"失敗: {traceback.format_exc()}")
