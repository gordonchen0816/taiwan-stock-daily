import os
import yfinance as yf
from openai import OpenAI
import requests
import random
import traceback
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# 1. 配置 OpenAI Client (使用最新 v1.0+ 語法)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_news_via_rss(source_query, limit=5):
    """
    利用 Google News RSS 搜尋特定媒體的頭條
    這是最穩定不被擋的方法，能繞過官網的機器人偵測
    """
    url = f"https://news.google.com/rss/search?q={source_query}+股市+經濟&hl=zh-TW&gl=TW&ceid=TW:zh-Hant&t={random.random()}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    titles = []
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, features="xml")
        items = soup.find_all('item', limit=limit)
        for item in items:
            # 移除標題末端的來源標記 (例如: - 經濟日報)
            t = item.title.text.split(' - ')[0]
            titles.append(t)
        return titles if titles else ["目前無相關新聞報導"]
    except Exception as e:
        return [f"新聞抓取失敗: {str(e)}"]

def get_stock_data():
    """抓取大盤及重點個股數據"""
    tks = {"加權指數": "^TWII", "台積電": "2330.TW", "鴻海": "2317.TW"}
    res = ""
    for name, code in tks.items():
        try:
            # 抓取 5 天數據以防假日，取最新兩筆進行比對
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
    print("--- 啟動 AI 財經主編 (多源 RSS 模式) ---")
    
    # 設定台北時間 (UTC+8)
    tw_time = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_time.strftime('%Y-%m-%d %H:%M:%S')
    
    # 2. 分別抓取各報消息 (利用 Google RSS 路由)
    print("正在抓取工商時報新聞...")
    ctee_news = get_news_via_rss('source:"工商時報"', 5)
    
    print("正在抓取經濟日報新聞...")
    money_news = get_news_via_rss('source:"經濟日報"', 5)
    
    print("正在抓取 Google 綜合新聞...")
    google_news = get_news_via_rss('台灣股市', 5)
    
    print("正在抓取股價數據...")
    stocks = get_stock_data()
    
    # 3. 構建 AI 嚴格指令
    prompt = f"""
    任務：你是專業財經主編。請根據以下新聞來源，整理出今日頭條並進行交叉比對。

    【工商時報頭條列表】：
    {ctee_news}

    【經濟日報頭條列表】：
    {money_news}

    【Google RSS 綜合熱點列表】：
    {google_news}

    指令：
    1. 交叉比對：請從以上 15 則標題中，找出最重要的『三個新聞交集頭條』。
    2. 格式：請嚴格依照以下格式輸出，不要包含額外的閒聊。

    ### 📰 今日各報頭條摘要
    #### 🏦 工商時報 (5則)
    - {ctee_news[0] if len(ctee_news)>0 else ''}
    - {ctee_news[1] if len(ctee_news)>1 else ''}
    - {ctee_news[2] if len(ctee_news)>2 else ''}
    - {ctee_news[3] if len(ctee_news)>3 else ''}
    - {ctee_news[4] if len(ctee_news)>4 else ''}

    #### 📖 經濟日報 (5則)
    - {money_news[0] if len(money_news)>0 else ''}
    - {money_news[1] if len(money_news)>1 else ''}
    - {money_news[2] if len(money_news)>2 else ''}
    - {money_news[3] if len(money_news)>3 else ''}
    - {money_news[4] if len(money_news)>4 else ''}

    #### 🌐 Google RSS 綜合 (5則)
    - {google_news[0] if len(google_news)>0 else ''}
    - {google_news[1] if len(google_news)>1 else ''}
    - {google_news[2] if len(google_news)>2 else ''}
    - {google_news[3] if len(google_news)>3 else ''}
    - {google_news[4] if len(google_news)>4 else ''}

    ### 📌 三大媒體焦點交集 (真正重複報導的事件)
    - [交集焦點 1]：描述事件並說明為什麼各家都在報。
    - [交集焦點 2]：描述事件並說明為什麼各家都在報。
    - [交集焦點 3]：描述事件並說明為什麼各家都在報。

    ### 📈 個股現況與大盤分析
    - 針對最新數據 {stocks} 進行專業評論，並給予投資操作建議。
    """
    
    print("正在發送請求至 OpenAI...")
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "你是一位嚴謹的台灣財經分析專家。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    content = response.choices[0].message.content

    # 4. 寫入 index.md
    with open("index.md", "w", encoding="utf-8") as f:
        f.write(f"# 📊 台灣股市 AI 精選情報\n")
        f.write(f"> **最後更新時間：{time_str}** (台北時間)\n\n")
        f.write(content)
        f.write(f"\n\n---\n*數據來源：Google RSS (工商、經濟、Yahoo), Yahoo Finance*")
    
    print(f"--- 報告更新成功！時間：{time_str} ---")

except Exception as e:
    print("--- 執行出錯 ---")
    print(traceback.format_exc())
