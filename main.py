import os
import yfinance as yf
from openai import OpenAI
import requests
import traceback
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import markdown
import json
import time

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
        history = history[-42:]
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=4)
    return history

def get_institutional_investors():
    """進化版：具備自動重試機制與數據狀態判定"""
    url = "https://api.cnyes.com/media/api/v1/investor/total"
    for i in range(3):
        try:
            r = requests.get(url, timeout=10)
            items = r.json().get('items', {})
            f_buy = round(items.get('foreign', 0) / 100000000, 2)
            t_buy = round(items.get('trust', 0) / 100000000, 2)
            d_buy = round(items.get('dealer', 0) / 100000000, 2)
            total = round(f_buy + t_buy + d_buy, 2)
            
            if total == 0:
                status = "⚠️ 盤中監控 (當日結算未出)"
                is_final = False
            else:
                status = "✅ 數據已結算"
                is_final = True
            
            text = f"{status} 外資:{f_buy}億 | 投信:{t_buy}億 | 自營:{d_buy}億 | 合計:{total}億"
            return text, {"total": total, "is_final": is_final}
        except:
            if i < 2: time.sleep(5)
            continue
    return "📡 數據源暫時更新中", {"total": 0, "is_final": False}

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

def get_filtered_news_data():
    """依據指定關鍵字過濾新聞 (包含您新增的 美債、AI Agent、籌碼)"""
    news_list = []
    # 定義 12 組關鍵字
    keywords = [
        "台積電", "AI", "NVDA", "輝達", "殖利率", 
        "黃金", "房地產", "股匯", "ETF", "美債", 
        "AI Agent", "籌碼"
    ]
    try:
        # 增加抓取上限至 40 則，確保過濾後仍有足夠資訊量
        r = requests.get("https://api.cnyes.com/media/api/v1/newslist/category/tw_stock?limit=40", timeout=10)
        items = r.json()['items']['data']
        for item in items:
            title = item['title']
            # 只要標題包含任一關鍵字（不分大小寫）即收入
            if any(kw.lower() in title.lower() for kw in keywords):
                news_list.append({"title": title, "link": f"https://news.cnyes.com/news/id/{item['newsId']}"})
    except: pass
    return news_list

try:
    print("--- 啟動精準關鍵字擴充版 AI Agent ---")
    tw_now = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_now.strftime('%Y-%m-%d %H:%M:%S')
    current_hour_min = tw_now.strftime('%H:%M')

    past_history = manage_memory()
    inst_text, inst_data = get_institutional_investors()
    stock_cards_html, stock_summary = get_detailed_stock_info()
    raw_news = get_filtered_news_data()
    news_titles = [n['title'] for n in raw_news]

    is_after_market_time = "14:30" <= current_hour_min <= "23:59"
    final_mode = "【盤後籌碼定調模式】" if (is_after_market_time and inst_data['is_final']) else "【盤中動態監控模式】"
    
    prompt = f"""
    任務：你是台股分析 Agent。模式：{final_mode}。
    【重要】：若籌碼合計為 0，代表數據真空期，請專注分析權值股(台積電、鴻海)與指數的技術背離與 RSI 變化。
    【歷史記憶】：{json.dumps(past_history[-3:], ensure_ascii=False)}
    【三大法人籌碼】：{inst_text}
    【即時報價】：{json.dumps(stock_summary, ensure_ascii=False)}
    【篩選關鍵新聞】：{news_titles[:15]}

    輸出格式 Markdown：
    ## 🧠 {final_mode} 核心策略
    ## 🔍 異常警示：出貨 vs 承接
    ## 🎯 下一階段觀察點
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "你是一位專業 CFO 顧問，擅長分析量價背離與籌碼異常。"},
                  {"role": "user", "content": prompt}],
        temperature=0.3
    )
    ai_report = response.choices[0].message.content
    
    # 新聞 HTML 生成 (亮色主題)
    news_links_html = f"""
    <div style='margin-top: 30px;'>
        <details>
            <summary style='cursor:pointer; padding:15px; background:#f1f8ff; border:1px solid #0969da; border-radius:8px; color:#0969da; font-weight:bold;'>
                📂 查看今日「精準過濾」新聞摘要 (關鍵字：台積電/AI/美債/ETF/籌碼/輝達...)
            </summary>
            <div style='padding:15px; border:1px solid #d0d7de; border-top:none; border-radius:0 0 8px 8px; background:#ffffff;'>
                <ul style='list-style-type: none; padding-left: 0;'>
    """
    for n in raw_news:
        news_links_html += f"<li style='margin-bottom:10px; border-bottom:1px solid #d0d7de; padding-bottom:5px;'><a href='{n['link']}' target='_blank' style='color:#0969da; text-decoration:none;'>{n['title']}</a></li>"
    
    if not raw_news:
        news_links_html += "<li>今日暫無符合關鍵字之重要新聞。</li>"
        
    news_links_html += "</ul></div></details></div>"

    html_report = markdown.markdown(ai_report, extensions=['nl2br'])
    
    # 整合完整亮色 HTML
    full_html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
        <style>
            body {{ background-color: #ffffff; color: #1f2328; max-width: 1000px; margin: 0 auto; padding: 20px; font-family: -apple-system, sans-serif; }}
            .markdown-body {{ background: transparent !important; color: #1f2328 !important; }}
            .cards-container {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }}
            .stock-card {{ background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 10px; padding: 15px; color: #1f2328; }}
            .inst-banner {{ background: #ffffff; border: 2px solid {"#f39c12" if inst_data['is_final'] else "#0969da"}; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
            .stock-name {{ font-weight: bold; color: #0969da; }}
        </style>
    </head>
    <body class="markdown-body">
        <h1>💹 AI 代理人：台股策略報告</h1>
        <div class="inst-banner">
            <strong>📊 籌碼動態：</strong> {inst_text} <br>
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
    print(f"--- 關鍵字擴充版報告生成完成 (亮色/關鍵字過濾) ---")

except Exception as e:
    print(f"ERROR: {traceback.format_exc()}")
