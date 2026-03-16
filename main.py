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
    # 鎖定監控標的：加權、櫃買、台指期、台積電、精材、鴻海
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
            # 抓取 40 天數據以計算指標
            df = yf.download(code, period="40d", interval="1d", progress=False)
            if not df.empty:
                curr_price = round(float(df['Close'].iloc[-1].item()), 2)
                prev_price = round(float(df['Close'].iloc[-2].item()), 2)
                diff = round(curr_price - prev_price, 2)
                pct = round((diff / prev_price) * 100, 2)
                
                # 計算技術指標
                sma7 = round(df['Close'].rolling(window=7).mean().iloc[-1].item(), 2)
                sma20 = round(df['Close'].rolling(window=20).mean().iloc[-1].item(), 2)
                rsi_val = round(calculate_rsi(df['Close']).iloc[-1].item(), 2)
                
                # 趨勢判斷與顏色 (紅漲綠跌)
                trend = "均線多頭" if sma7 > sma20 else "均線空頭"
                color = "#d73a49" if diff >= 0 else "#22863a"
                trend_color = "#f1f8ff" if sma7 > sma20 else "#fff5f5"
                trend_text_color = "#0366d6" if sma7 > sma20 else "#d73a49"
                
                # 生成卡片 HTML
                cards_html += f"""
                <div class="stock-card">
                    <div class="stock-name">{name}</div>
                    <div class="stock-price">${curr_price:,}</div>
                    <div class="stock-change" style="color:{color}">{'+' if diff >= 0 else ''}{diff} ({pct}%)</div>
                    <div class="stock-meta">RSI: {rsi_val}</div>
                    <div class="stock-meta">SMA7: ${sma7:,}</div>
                    <div class="stock-meta">SMA20: ${sma20:,}</div>
                    <div class="stock-trend" style="background:{trend_color}; color:{trend_text_color}">{trend}</div>
                </div>
                """
                summary_for_ai += f"{name}: {curr_price} ({pct}%, {trend}, RSI:{rsi_val}); "
        except Exception as e:
            cards_html += f"<div class='stock-card'>{name}: 讀取失敗</div>"
            
    return cards_html, summary_for_ai

def get_news_pool(limit=45):
    # 鎖定 24 小時內新聞，避免穿越時空
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
    except Exception as e:
        return ["無法取得即時新聞池"]

try:
    print("--- 啟動 AI 財經主編 (格式優化版) ---")
    tw_now = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_now.strftime('%Y-%m-%d %H:%M:%S')
    
    # 執行數據獲取
    stock_cards_html, stock_summary_text = get_detailed_stock_info()
    news_pool = get_news_pool(50)
    
    # AI 報告 Prompt，維持繁體中文
    prompt = f"""
    任務：將台灣財經資訊轉化為一份「每日彙整報告」。
    語言：全篇繁體中文。
    今日股市表現摘要：{stock_summary_text}
    當前新聞池內容：{news_pool}
    
    請依下列格式輸出 Markdown：

    ## 📰 今日重點摘要
    (歸納 5 個台股關鍵事件。格式：1. **[關鍵字]**：描述)

    ## 📊 市場概況與技術解讀
    (結合真實數據 {stock_summary_text} 進行分析，討論多空趨勢。)

    ## 😱 市場情緒與風險提醒
    (判斷投資人情緒。列出未來 24 小時的利空因素。)

    ## 🎯 今日觀察重點
    (列出 3 個明日觀察點。)

    【要求】：剔除日期不符的舊聞。
    """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "你是一位專業的台灣財經分析專家，擅長歸納數據與新聞趨勢。"},
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
            /* 強制深色背景模式 */
            body {{ 
                background-color: #0d1117; color: #c9d1d9; font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; 
                box-sizing: border-box; min-width: 200px; max-width: 1000px; margin: 0 auto; padding: 30px; 
            }}
            .markdown-body {{ 
                background-color: transparent !important; color: inherit !important; 
            }}
            @media (max-width: 767px) {{ body {{ padding: 15px; }} }}
            
            /* 優化 Banner 顏色，解決 image_0.png 閱讀費力問題 */
            .info-banner {{ 
                background-color: #f6f8fa; color: #24292e; border-left: 5px solid #0366d6; padding: 12px; margin-bottom: 25px; border-radius: 4px; font-size: 0.9em; 
            }}
            
            /* 修正卡片排版，強制保持相同大小與格子排列 */
            .cards-container {{ 
                display: grid; 
                grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); 
                gap: 15px; margin-bottom: 30px; 
            }}
            .stock-card {{ 
                background: #ffffff; border: 1px solid #e1e4e8; border-radius: 10px; padding: 15px; 
                box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            }}
            
            /* 卡片內部樣式微調 */
            .stock-name {{ font-weight: bold; font-size: 1.05em; color: #0366d6; margin-bottom: 5px; }}
            .stock-price {{ font-size: 1.35em; font-weight: bold; color: #24292e; }}
            .stock-change {{ font-size: 0.9em; margin-bottom: 10px; font-weight: bold; }}
            .stock-meta {{ font-size: 0.78em; color: #586069; line-height: 1.5; }}
            .stock-trend {{ margin-top: 10px; font-size: 0.8em; font-weight: bold; display: inline-block; padding: 3px 10px; border-radius: 12px; }}
            
            /* Markdown 標題顏色調整 */
            .markdown-body h1, .markdown-body h2 {{ border-bottom: 1px solid #30363d; color: #e6edf3 !important; padding-bottom: 0.3em; margin-top: 1.5em; }}
        </style>
    </head>
    <body class="markdown-body">
        <h1 style="border-bottom:none !important; margin-top: 0;">📉 台股每日彙整報告</h1>
        <div class="info-banner">
            📋 最後更新：{time_str} (台北時間)
        </div>
        
        <h2>📊 市場數據監測</h2>
        <div class="cards-container">
            {stock_cards_html}
        </div>

        {html_body}
        <hr style="border: 0; border-top: 1px solid #30363d; margin-top: 40px;">
        <p style="text-align: center; color: #8b949e; font-size: 0.7em;">Data Source: Yahoo Finance & Google News RSS</p>
    </body>
    </html>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print("--- 網頁生成成功 (格式優化版) ---")

except Exception as e:
    print(f"失敗: {traceback.format_exc()}")
