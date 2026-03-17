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
    """記憶中樞：保留約 3.5 天的滾動紀錄"""
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
    """抓取籌碼並判斷數據狀態"""
    try:
        url = "https://api.cnyes.com/media/api/v1/investor/total"
        r = requests.get(url, timeout=10)
        d = r.json()['items']
        f_buy = round(d.get('foreign', 0) / 100000000, 2)
        t_buy = round(d.get('trust', 0) / 100000000, 2)
        d_buy = round(d.get('dealer', 0) / 100000000, 2)
        total = round(f_buy + t_buy + d_buy, 2)
        
        status = "【今日結算完成】" if total != 0 else "【盤中：沿用前一交易日籌碼】"
        text = f"{status} 外資:{f_buy}億 | 投信:{t_buy}億 | 自營:{d_buy}億 | 合計:{total}億"
        data = {"total": total, "is_final": total != 0}
        return text, data
    except:
        return "籌碼數據連線異常", {}

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
    """獲取包含連結的新聞清單 (收集區來源：鉅亨網)"""
    news_list = []
    try:
        r = requests.get("https://api.cnyes.com/media/api/v1/newslist/category/tw_stock?limit=20", timeout=10)
        items = r.json()['items']['data']
        for item in items:
            news_list.append({
                "title": item['title'],
                "link": f"https://news.cnyes.com/news/id/{item['newsId']}"
            })
    except:
        print("抓取新聞資料異常")
    return news_list

try:
    print("--- 啟動具備新聞追蹤功能之 AI Agent ---")
    tw_now = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_now.strftime('%Y-%m-%d %H:%M:%S')
    current_hour_min = tw_now.strftime('%H:%M')

    # 1. 數據採集
    past_history = manage_memory()
    inst_text, inst_data = get_institutional_investors()
    stock_cards_html, stock_summary = get_detailed_stock_info()
    raw_news = get_raw_news_data()
    news_titles = [n['title'] for n in raw_news]

    # 2. 模式判斷
    is_after_market = "14:30" <= current_hour_min <= "23:59"
    analysis_mode = "【盤後籌碼定調模式】" if is_after_market else "【盤中動態監控模式】"
    
    # 3. AI Agent 診斷思考
    prompt = f"""
    任務：你是台股 AI 代理人，現在進入 {analysis_mode}。台北時間 {current_hour_min}。
    【歷史記憶】：{json.dumps(past_history[-3:], ensure_ascii=False)}
    【三大法人籌碼】：{inst_text}
    【即時報價】：{json.dumps(stock_summary, ensure_ascii=False)}
    【最新新聞】：{news_titles[:20]}

    請依據「背離分析」與「CFO 交易風險」邏輯輸出 Markdown：
    ## 🧠 {analysis_mode} 核心策略
    ## 🔍 異常警示：出貨 vs 承接
    ## 🎯 下一階段觀察點
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": f"你是一位專業的 CFO 顧問。現在是台北時間 {current_hour_min}。"},
                  {"role": "user", "content": prompt}],
        temperature=0.3
    )
    ai_report = response.choices[0].message.content
    
    # 4. 建立新聞摘要區的 HTML (收集區摺疊選單)
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

    # 5. 生成最終網頁 (整合消化與收集)
    html_report = markdown.markdown(ai_report, extensions=['nl2br'])
    full_html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
        <style>
            body {{ background-color: #0d1117; color: #c9d1d9; max-width: 1000px; margin: 0 auto; padding: 20px; font-family: -apple-system, system-ui, sans-serif; }}
            .markdown-body {{ background: transparent !important; color: inherit !important; }}
            .cards-container {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }}
            .stock-card {{ background: #ffffff; border-radius: 10px; padding: 15px; color: #1f2328; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            .inst-banner {{ background: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-top: 4px solid {"#f39c12" if is_after_market else "#3498db"}; }}
            .stock-name {{ font-weight: bold; color: #0969da; border-bottom: 1px solid #eaecef; margin-bottom: 5px; }}
            .stock-price {{ font-size: 1.4em; font-weight: bold; }}
            a:hover {{ text-decoration: underline !important; }}
        </style>
    </head>
    <body class="markdown-body">
        <h1>💹 AI 代理人：台股{analysis_mode}</h1>
        <div class="inst-banner">
            <strong>📊 籌碼監控：</strong> {inst_text} <br>
            <small>📅 更新時間：{time_str} | 狀態：{'✅ 數據已結算' if is_after_market else '⏳ 盤中即時監控'}</small>
        </div>
        <div class="cards-container">{stock_cards_html}</div>
        <hr>
        {html_report}
        {news_links_html}
        <br><br>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(full_html)
    
    # 存儲記憶
    manage_memory({"time": time_str, "index": stock_summary.get("加權指數", {}).get("price"), "summary": ai_report[:100]})
    print(f"--- 報告生成完成，包含新聞摘要區 (成功插入網頁) ---")

except Exception as e:
    print(f"錯誤: {traceback.format_exc()}")
