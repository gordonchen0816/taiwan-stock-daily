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
    file_path = "history.json"
    history = []
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except: history = []
    if new_entry:
        history.append(new_entry)
        history = history[-42:] # 保留約 3.5 天記憶
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=4)
    return history

def get_institutional_investors():
    """除錯版：具備狀態識別與容錯機制"""
    try:
        url = "https://api.cnyes.com/media/api/v1/investor/total"
        r = requests.get(url, timeout=10)
        json_data = r.json()
        items = json_data.get('items', {})
        
        f_buy = round(items.get('foreign', 0) / 100000000, 2)
        t_buy = round(items.get('trust', 0) / 100000000, 2)
        d_buy = round(items.get('dealer', 0) / 100000000, 2)
        total = round(f_buy + t_buy + d_buy, 2)
        
        # 邏輯偵錯：判斷是否真的是今日結算
        if total == 0:
            status = "⚠️ 盤中監控 (當日結算未出)"
            is_final = False
        else:
            status = "✅ 當日籌碼已結算"
            is_final = True
            
        text = f"{status} 外資:{f_buy}億 | 投信:{t_buy}億 | 自營:{d_buy}億 | 合計:{total}億"
        return text, {"total": total, "is_final": is_final, "text": text}
    except:
        return "📡 籌碼數據源更新中 (暫無即時數據)", {"total": 0, "is_final": False, "text": "數據源更新中"}

def get_detailed_stock_info():
    tks = {"加權指數": "^TWII", "櫃買指數": "^TWOII", "台積電": "2330.TW", "鴻勁": "7769.TW", "鴻海": "2317.TW"}
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

def get_raw_news_data():
    news_list = []
    try:
        r = requests.get("https://api.cnyes.com/media/api/v1/newslist/category/tw_stock?limit=20", timeout=10)
        items = r.json()['items']['data']
        for item in items:
            news_list.append({"title": item['title'], "link": f"https://news.cnyes.com/news/id/{item['newsId']}"})
    except: pass
    return news_list

try:
    print("--- 啟動除錯優化版 AI Agent ---")
    tw_now = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_now.strftime('%Y-%m-%d %H:%M:%S')
    current_hour_min = tw_now.strftime('%H:%M')

    # 1. 數據採集
    past_history = manage_memory()
    inst_text, inst_data = get_institutional_investors()
    stock_cards_html, stock_summary = get_detailed_stock_info()
    raw_news = get_raw_news_data()
    news_titles = [n['title'] for n in raw_news]

    # 2. 模式與邊界判定
    is_after_market = "14:30" <= current_hour_min <= "23:59"
    analysis_mode = "【盤後籌碼定調模式】" if is_after_market else "【盤中動態監控模式】"
    
    # 3. AI Agent 診斷指令 (加入除錯後的決策邊界)
    prompt = f"""
    任務：你是具備「背離分析」能力的台股 Agent。現在進入 {analysis_mode}。
    【重要指令】：
    1. 若籌碼合計為 0，代表數據尚未結算，禁止推測法人買賣超，應轉向分析「價格漲跌」與「RSI指標」是否出現矛盾。
    2. 比對歷史記憶，指出今日與昨日最大的情緒差異。

    【歷史記憶】：{json.dumps(past_history[-3:], ensure_ascii=False)}
    【三大法人籌碼】：{inst_text}
    【即時報價】：{json.dumps(stock_summary, ensure_ascii=False)}
    【最新新聞】：{news_titles[:15]}

    輸出格式 Markdown：
    ## 🧠 {analysis_mode} 核心策略
    ## 🔍 異常警示：出貨 vs 承接
    ## 🎯 下一階段觀察點
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": f"你是一位精通 CFO 邏輯的資深顧問。"},
                  {"role": "user", "content": prompt}],
        temperature=0.3
    )
    ai_report = response.choices[0].message.content
    
    # 4. 生成 HTML
    news_links_html = """
    <div style='margin-top: 30px;'>
        <details>
            <summary style='cursor:pointer; padding:15px; background:#161b22; border:1px solid #30363d; border-radius:8px; color:#c9d1d9; font-weight:bold;'>
                📂 查看今日原始新聞摘要 (原始訊息收集區)
            </summary>
            <div style='padding:15px; background:#0d1117; border:1px solid #30363d; border-top:none; border-radius:0 0 8px 8px;'>
                <ul style='list-style-type: none; padding-left: 0;'>
    """
    for n in raw_news:
        news_links_html += f"<li style='margin-bottom:10px; border-bottom:1px solid #21262d; padding-bottom:5px;'><a href='{n['link']}' target='_blank' style='color:#58a6ff; text-decoration:none;'>{n['title']}</a></li>"
    news_links_html += "</ul></div></details></div>"

    html_report = markdown.markdown(ai_report, extensions=['nl2br'])
    full_html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
        <style>
            body {{ background-color: #0d1117; color: #c9d1d9; max-width: 1000px; margin: 0 auto; padding: 20px; }}
            .markdown-body {{ background: transparent !important; color: inherit !important; }}
            .cards-container {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }}
            .stock-card {{ background: #ffffff; border-radius: 10px; padding: 15px; color: #1f2328; }}
            .inst-banner {{ background: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-top: 4px solid {"#f39c12" if is_after_market else "#3498db"}; }}
            .stock-name {{ font-weight: bold; color: #0969da; }}
        </style>
    </head>
    <body class="markdown-body">
        <h1>💹 AI 代理人：台股{analysis_mode}</h1>
        <div class="inst-banner">
            <strong>📊 籌碼監控：</strong> {inst_text} <br>
            <small>📅 更新時間：{time_str}</small>
        </div>
        <div class="cards-container">{stock_cards_html}</div>
        <hr>
        {html_report}
        {news_links_html}
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(full_html)
    manage_memory({"time": time_str, "index": stock_summary.get("加權指數", {}).get("price"), "summary": ai_report[:100]})
    print(f"--- 除錯版報告生成完成 ---")

except Exception as e:
    print(f"錯誤分析: {traceback.format_exc()}")
