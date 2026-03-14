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

def get_news_pool(limit=40):
    """
    抓取一個大的新聞池，再進行後續分類，這比單獨搜尋來源更穩定
    """
    url = f"https://news.google.com/rss/search?q=股市+經濟+台灣+台股&hl=zh-TW&gl=TW&ceid=TW:zh-Hant&t={random.random()}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    pool = []
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, features="xml")
        items = soup.find_all('item', limit=limit)
        for item in items:
            title = item.title.text
            # 儲存標題與原始來源
            pool.append(title)
        return pool
    except:
        return []

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
            res += f"{name}: 失敗\n"
    return res

try:
    print("--- 啟動 AI 財經主編 (混合過濾模式) ---")
    tw_time = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_time.strftime('%Y-%m-%d %H:%M:%S')
    
    # 抓取大新聞池
    news_pool = get_news_pool(50)
    stocks = get_stock_data()
    
    # 這裡不讓 Python 分類，直接把整包交給 AI 分類，AI 的模糊比對能力更強
    prompt = f"""
    任務：你是專業財經主編。請從以下『新聞池』中，依照要求分類並進行交叉比對。

    【今日原始新聞池】：
    {news_pool}

    【最新股市數據】：
    {stocks}

    指令：
    1. 分類：從新聞池中找出：
       - 最像『經濟日報』風格的 5 則新聞。
       - 最像『Yahoo/工商/其它綜合財經』風格的 5 則新聞。
       - 剩餘新聞中挑選 5 則最重大的作為『Google RSS 綜合』。
    2. 交叉比對：找出最重要的『三個新聞交集焦點』。
    3. 嚴格格式輸出：

    ### 📰 今日各報頭條摘要
    #### 🏦 財經綜合焦點 (5則)
    - (列出 5 則)
    #### 📖 經濟日報精選 (5則)
    - (列出 5 則)
    #### 🌐 Google RSS 熱門 (5則)
    - (列出 5 則)

    ### 📌 三大媒體焦點交集 (真正重複報導的事件)
    - [焦點 1]：描述並說明原因。
    - [焦點 2]：描述並說明原因。
    - [焦點 3]：描述並說明原因。

    ### 📈 個股現況與大盤分析
    - 數據：{stocks}
    - 評論：(請針對數據給予具體的操作建議)
    """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "你是一位專業的台灣財經編輯。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    content = response.choices[0].message.content

    with open("index.md", "w", encoding="utf-8") as f:
        f.write(f"# 📊 台灣股市 AI 精選情報\n")
        f.write(f"> **最後更新時間：{time_str}** (台北時間)\n\n")
        f.write(content)
        f.write(f"\n\n---\n*數據來源：Google News 混合池, Yahoo Finance*")
    
    print(f"--- 報告更新成功！ ---")

except Exception as e:
    print(f"執行出錯: {traceback.format_exc()}")
