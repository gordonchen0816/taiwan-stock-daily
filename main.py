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

def get_news_via_rss(query, limit=5):
    """
    透過 Google News RSS 路由抓取特定來源或主題的新聞
    """
    url = f"https://news.google.com/rss/search?q={query}+股市+經濟&hl=zh-TW&gl=TW&ceid=TW:zh-Hant&t={random.random()}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    titles = []
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, features="xml")
        items = soup.find_all('item', limit=limit)
        for item in items:
            # 清理標題，移除來源後綴
            t = item.title.text.split(' - ')[0]
            titles.append(t)
        # 如果抓不夠，填補空位
        while len(titles) < limit:
            titles.append("目前無更多相關重大報導")
        return titles
    except Exception as e:
        return [f"抓取失敗: {str(e)}"] * limit

def get_stock_data():
    """抓取大盤及重點個股數據"""
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
                res += f"{name}: {curr} (漲跌: {diff}, 幅度: {pct}%)\n"
        except:
            res += f"{name}: 數據獲取失敗\n"
    return res

try:
    print("--- 啟動 AI 財經主編 (Yahoo/經濟/Google 模式) ---")
    
    tw_time = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_time.strftime('%Y-%m-%d %H:%M:%S')
    
    # 分別抓取三大來源
    print("正在抓取 Yahoo 財經新聞...")
    yahoo_news = get_news_via_rss('source:"Yahoo股市"', 5)
    
    print("正在抓取 經濟日報新聞...")
    money_news = get_news_via_rss('source:"經濟日報"', 5)
    
    print("正在抓取 Google 綜合熱點...")
    google_news = get_news_via_rss('台灣股市', 5)
    
    stocks = get_stock_data()
    
    # 構建 AI 嚴格指令
    prompt = f"""
    任務：你是專業財經主編。請根據以下新聞來源，整理出今日頭條並進行交叉比對。

    【Yahoo 財經頭條】：
    {yahoo_news}

    【經濟日報頭條】：
    {money_news}

    【Google RSS 綜合熱點】：
    {google_news}

    指令：
    1. 交叉比對：請從以上 15 則標題中，找出最重要的『三個新聞交集頭條』。
    2. 格式：請嚴格依照以下格式輸出。

    ### 📰 今日各報頭條摘要
    #### 🏦 Yahoo 財經 (5則)
    - {yahoo_news[0]}
    - {yahoo_news[1]}
    - {yahoo_news[2]}
    - {yahoo_news[3]}
    - {yahoo_news[4]}

    #### 📖 經濟日報 (5則)
    - {money_news[0]}
    - {money_news[1]}
    - {money_news[2]}
    - {money_news[3]}
    - {money_news[4]}

    #### 🌐 Google RSS 綜合 (5則)
    - {google_news[0]}
    - {google_news[1]}
    - {google_news[2]}
    - {google_news[3]}
    - {google_news[4]}

    ### 📌 三大媒體焦點交集 (真正重複報導的事件)
    - [焦點 1]：描述並說明原因。
    - [焦點 2]：描述並說明原因。
    - [焦點 3]：描述並說明原因。

    ### 📈 個股現況與大盤分析
    - 針對最新數據 {stocks} 進行專業評論，並給予投資建議。
    """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "你是一位嚴謹的台灣財經分析專家。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    content = response.choices[0].message.content

    # 寫入 index.md
    with open("index.md", "w", encoding="utf-8") as f:
        f.write(f"# 📊 台灣股市 AI 精選情報\n")
        f.write(f"> **最後更新時間：{time_str}** (台北時間)\n\n")
        f.write(content)
        f.write(f"\n\n---\n*數據來源：Yahoo Finance, 經濟日報, Google RSS*")
    
    print(f"--- 報告更新成功！時間：{time_str} ---")

except Exception as e:
    print("--- 執行出錯 ---")
    print(traceback.format_exc())
