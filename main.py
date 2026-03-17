import os
import yfinance as yf
from openai import OpenAI
import requests
import traceback
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import markdown
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
    
    # 讀取現有記憶
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except: 
            history = []

    # 如果有新紀錄則寫入
    if new_entry:
        history.append(new_entry)
        history = history[-7:] # 滾動記憶：只保留最近 7 天
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=4)
            
    return history

def get_detailed_stock_info():
    """獲取技術指標數據"""
    tks = {
        "加權指數": "^TWII", "櫃買指數": "^TWOII", 
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
                
                # 計算均線與 RSI
                sma7 = round(df['Close'].rolling(window=7).mean().iloc[-1].item(), 2)
                sma20 = round(df['Close'].rolling(window=20).mean().iloc[-1].item(), 2)
                rsi_val = round(calculate_rsi(df['Close']).iloc[-1].item(), 2)
                
                trend = "多頭" if curr_p > sma20 else "空頭"
                color = "#d73a49" if diff >= 0 else "#22863a" # 紅漲綠跌 (GitHub 風格)
                
                cards_html += f"""
                <div class="stock-card">
                    <div class="stock-name">{name}</div>
                    <div class="stock-price">${curr_p:,}</div>
                    <div class="stock-change" style="color:{color}">{'+' if diff >= 0 else ''}{diff} ({pct}%)</div>
                    <div class="stock-meta">RSI: {rsi_val} | SMA7: {sma7}</div>
                    <div class="stock-meta">趨勢: {trend} (MA20)</div>
                </div>"""
                summary_data[name] = {"price": curr_p, "pct": pct, "trend": trend, "rsi": rsi_val}
        except Exception as e:
            print(f"抓取 {name} 失敗: {e}")
    return cards_html, summary_data

def get_news_pool():
    """多路徑新聞爬蟲 (OpenCrawl 邏輯)"""
    news = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    # 來源 1：鉅亨網
    try:
        r = requests.get("https://api.cnyes.com/media/api/v1/newslist/category/tw_stock?limit=15", timeout=10)
        for item in r.json()['items']['data']: news.append(f"【鉅亨】{item['title']}")
    except: pass
    # 來源 2：Yahoo 財經
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

    # 1. 喚醒記憶
    past_history = manage_memory()
    # 簡化歷史記憶，只給 AI 最近三天的摘要
    memory_context = "這是初次分析，尚無歷史記憶。" if not past_history else json.dumps(past_history[-3:], ensure_ascii=False)

    # 2. 獲取當前數據與新聞
    stock_cards_html, stock_summary = get_detailed_stock_info()
    news_pool = get_news_pool()

    # 3. AI Agent 決策思考 (對比構面)
    prompt = f"""
    任務：你是具備長期記憶能力的台股分析代理人。請比對歷史並分析今日走勢。
    
    【歷史記憶】：{memory_context}
    【今日數據】：{json.dumps(stock_summary, ensure_ascii=False)}
    【今日新聞】：{news_pool[:25]}

    請嚴格依照以下格式輸出 Markdown：
    ## 🧠 跨日趨勢追蹤 (關鍵對比)
    (在此部分，請比對歷史紀錄。若今日 RSI 較昨日下降，或連續幾日處於空頭，請明確指出趨勢演變)

    ## 📰 今日重點解讀
    (分析今日新聞中真正影響大盤的 3 大因素)

    ## 📊 數據異常觀測
    (針對個股技術指標如 RSI 過高、跌破均線等進行警示)

    ## 🎯 明日交易觀測
    (給出明日的操作觀察點)
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "你是一位專業的台股 Agent，擅長從歷史趨勢中發現規律。"},
                  {"role": "user", "content": prompt}],
        temperature=0.3
    )
    
    ai_report = response.choices[0].message.content
    
    # 4. 存入今日記憶
    today_entry = {
        "date": time_str[:10],
        "index_price": stock_summary.get("加權指數", {}).get("price"),
        "key_conclusion": ai_report[:150].replace("\n", " ") # 存儲簡短摘要供明天比對
    }
    manage_memory(today_entry)

    # 5. 生成視覺化 HTML
    html_report = markdown.markdown(ai_report, extensions=['nl2br'])
    full_html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
        <style>
            body {{ background-color: #0d1117; color: #c9d1d9; max-width: 1000px; margin: 0 auto; padding: 20px; font-family: -apple-system, sans-serif; }}
            .markdown-body {{ background: transparent !important; color: inherit !important; font-size: 16px; }}
            .cards-container {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 15px; margin-bottom: 30px; }}
            .stock-card {{ background: #ffffff; border-radius: 12px; padding: 15px; color: #1f2328; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
            .stock-name {{ font-size: 1.1em; font-weight: bold; color: #0969da; border-bottom: 1px solid #eaecef; margin-bottom: 8px; }}
            .stock-price {{ font-size: 1.5em; font-weight: 800; margin: 5px 0; }}
            .stock-change {{ font-weight: bold; margin-bottom: 8px; }}
            .stock-meta {{ font-size: 0.85em; color: #57606a; }}
            .info-banner {{ background: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 5px solid #238636; }}
        </style>
    </head>
    <body class="markdown-body">
        <h1>🚀 AI 代理人：台股跨日分析報告</h1>
        <div class="info-banner">
            📅 更新時間：{time_str} <br>
            🧠 記憶庫狀態：已累積 {len(past_history)+1} 天數據 | 模式：Agentic Reasoning
        </div>
        <div class="cards-container">{stock_cards_html}</div>
        <hr>
        {html_report}
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(full_html)
    print(f"--- 報告生成成功，記憶已存檔 (目前天數: {len(past_history)+1}) ---")

except Exception as e:
    print(f"運作異常: {traceback.format_exc()}")
