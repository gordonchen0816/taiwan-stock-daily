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
    """記憶中樞：滾動式存儲最近 42 筆紀錄 (對應每 2 小時執行，約 3.5 天記憶)"""
    file_path = "history.json"
    history = []
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except: history = []

    if new_entry:
        history.append(new_entry)
        history = history[-42:] 
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=4)
    return history

def get_institutional_investors():
    """抓取三大法人買賣超 (鉅亨網 API 來源)"""
    try:
        # 抓取市場整體法人動向
        url = "https://api.cnyes.com/media/api/v1/investor/total"
        r = requests.get(url, timeout=10)
        d = r.json()['items']
        f_buy = round(d.get('foreign', 0) / 100000000, 2) # 億
        t_buy = round(d.get('trust', 0) / 100000000, 2)
        d_buy = round(d.get('dealer', 0) / 100000000, 2)
        total = round(f_buy + t_buy + d_buy, 2)
        
        text = f"外資:{f_buy}億 | 投信:{t_buy}億 | 自營:{d_buy}億 | 合計:{total}億"
        data = {"foreign": f_buy, "trust": t_buy, "dealer": d_buy, "total": total}
        return text, data
    except:
        return "暫無即時籌碼數據", {}

def get_detailed_stock_info():
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
    try:
        r = requests.get("https://api.cnyes.com/media/api/v1/newslist/category/tw_stock?limit=20", timeout=10)
        for item in r.json()['items']['data']: news.append(f"【鉅亨】{item['title']}")
    except: pass
    return list(set(news))

try:
    print("--- 啟動籌碼分析級 AI Agent ---")
    tw_now = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_now.strftime('%Y-%m-%d %H:%M:%S')

    # 1. 執行數據抓取
    past_history = manage_memory()
    inst_text, inst_data = get_institutional_investors()
    stock_cards_html, stock_summary = get_detailed_stock_info()
    news_pool = get_news_pool()

    # 2. AI Agent 決策 (籌碼 + 記憶 + 價格)
    memory_context = json.dumps(past_history[-5:], ensure_ascii=False) if past_history else "初步建立記憶中"
    
    prompt = f"""
    任務：你是具備長期記憶與籌碼洞察力的台股 Agent。
    
    【歷史記憶】：{memory_context}
    【今日籌碼】：{inst_text}
    【即時報價】：{json.dumps(stock_summary, ensure_ascii=False)}
    【最新新聞】：{news_pool[:25]}

    請依據以上資訊，嚴格按照格式進行「背離分析」並輸出 Markdown：

    ## 🧠 籌碼趨勢與跨日比對
    (請判斷：法人是否在「趁高出貨」或「低檔承接」？比對歷史記憶中的價格變化，說明籌碼與價位的連動性。)

    ## 🔍 異常警示 (技術 + 籌碼)
    (例如：股價漲但法人大賣、RSI過熱且法人調節、或股價回檔但法人逆勢加碼。)

    ## 🎯 兩小時動態操作觀測
    (給出短線上的支撐與壓力建議，並針對法人動向給予投資人心理建設。)
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "你是一位專業的台股 CFO 顧問，擅長分析法人籌碼與主力動向。"},
                  {"role": "user", "content": prompt}],
        temperature=0.3
    )
    
    ai_report = response.choices[0].message.content
    
    # 3. 儲存當前狀態至記憶
    manage_memory({
        "time": time_str,
        "index": stock_summary.get("加權指數", {}).get("price"),
        "inst_total": inst_data.get("total", 0),
        "summary": ai_report[:120]
    })

    # 4. 生成 HTML
    html_report = markdown.markdown(ai_report, extensions=['nl2br'])
    full_html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
        <style>
            body {{ background-color: #0d1117; color: #c9d1d9; max-width: 1000px; margin: 0 auto; padding: 20px; }}
            .markdown-body {{ background: transparent !important; color: inherit !important; }}
            .cards-container {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }}
            .stock-card {{ background: #ffffff; border-radius: 10px; padding: 15px; color: #1f2328; }}
            .inst-banner {{ background: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-top: 4px solid #f39c12; }}
            .stock-name {{ font-weight: bold; color: #0969da; }}
            .stock-price {{ font-size: 1.4em; font-weight: bold; }}
        </style>
    </head>
    <body class="markdown-body">
        <h1>💹 台股 AI 代理人：籌碼動態報告</h1>
        <div class="inst-banner">
            <strong>📊 今日法人籌碼：</strong> {inst_text} <br>
            <small>📅 更新時間：{time_str} | 記憶深度：{len(past_history)+1} 筆</small>
        </div>
        <div class="cards-container">{stock_cards_html}</div>
        <hr>
        {html_report}
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(full_html)
    print("--- 籌碼版報告生成完成 ---")

except Exception as e:
    print(f"錯誤: {traceback.format_exc()}")
