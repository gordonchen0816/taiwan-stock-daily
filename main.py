import os
import yfinance as yf
from openai import OpenAI
import requests
import random
import traceback
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# 配置 OpenAI Client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_news_by_source(url, limit=5):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    titles = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 根據常見財經媒體結構抓取標題 (這部分採通用策略，若媒體改版需微調)
        if "ctee" in url: # 工商時報
            items = soup.find_all(['h3', 'h4'], limit=limit+5)
        elif "money.udn" in url: # 經濟日報
            items = soup.find_all(['h3', 'h4', 'a'], limit=limit+10)
        else: # Google RSS
            soup = BeautifulSoup(response.content, features="xml")
            items = soup.find_all('item', limit=limit)
            return [item.title.text for item in items]

        for item in items:
            t = item.get_text().strip()
            if len(t) > 10 and t not in titles:
                titles.append(t)
            if len(titles) >= limit: break
        return titles
    except:
        return ["無法取得該媒體頭條"]

def get_stock_data():
    tks = {"加權指數": "^TWII", "台積電": "2330.TW", "鴻海": "2317.TW"}
    res = ""
    for name, code in tks.items():
        try:
            d = yf.download(code, period="5d", interval="1d", progress=False)
            if not d.empty:
                curr = round(float(d['Close'].iloc[-1].item()), 2)
                prev = round(float(d['Close'].iloc[-2].item()), 2)
                diff = round(curr - prev, 2)
                pct = round((diff / prev) * 100, 2)
                res += f"{name}: {curr} ({diff}, {pct}%)\n"
        except:
            res += f"{name}: 數據獲取失敗\n"
    return res

try:
    print("--- 啟動 AI 財經主編 (多源比對模式) ---")
    tw_time = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_time.strftime('%Y-%m-%d %H:%M:%S')
    
    # 1. 分別抓取各家新聞
    ctee_news = get_news_by_source("https://www.ctee.com.tw/livenews/aj") # 工商
    money_news = get_news_by_source("https://money.udn.com/money/index") # 經濟
    google_news = get_news_by_source("https://news.google.com/rss/search?q=股市+經濟+台灣&hl=zh-TW&gl=TW&ceid=TW:zh-Hant") # Google
    
    stocks = get_stock_data()
    
    # 2. 構建 AI 指令
    prompt = f"""
    任務：你是專業財經主編。請根據以下新聞來源，整理出今日頭條並進行交叉比對。

    【工商時報頭條】：
    {ctee_news}

    【經濟日報頭條】：
    {money_news}

    【Google RSS 綜合頭條】：
    {google_news}

    【最新股市數據】：
    {stocks}

    請嚴格依照以下格式輸出：
    
    ### 📰 今日各報頭條摘要
    #### 🏦 工商時報 (5則)
    (請列出 5 則)
    #### 📖 經濟日報 (5則)
    (請列出 5 則)
    #### 🌐 Google RSS (5則)
    (請列出 5 則)

    ### 📌 三大媒體焦點交集 (真正重複報導的事件)
    (請從以上 15 則中比對，找出最重要的 3 個共同焦點，並說明原因。)

    ### 📈 個股現況與大盤分析
    (針對數據 {stocks} 給予專業評論與建議。)
    """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "你是一位嚴謹的台灣財經分析專家，擅長彙整多方資訊。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    content = response.choices[0].message.content

    # 3. 寫入 index.md
    with open("index.md", "w", encoding="utf-8") as f:
        f.write(f"# 📊 台灣股市 AI 精選情報 ({time_str})\n\n")
        f.write(content)
        f.write(f"\n\n---\n*更新時間：{time_str} | 數據來源：工商、經濟、Yahoo、Google*")
    
    print(f"--- 報告更新成功！時間：{time_str} ---")

except Exception as e:
    print("--- 執行出錯 ---")
    print(traceback.format_exc())
