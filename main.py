import os
import yfinance as yf
import openai
import requests
import random
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# OpenAI API Key
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_real_news_titles():
    # 使用 Google News RSS 抓取台灣財經新聞標題
    url = f"https://news.google.com/rss/search?q=股市+經濟+台灣&hl=zh-TW&gl=TW&ceid=TW:zh-Hant&t={random.random()}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    titles = []
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, features="xml")
        items = soup.find_all('item', limit=20)
        for item in items:
            titles.append(item.title.text)
        return "\n".join(titles) if titles else "目前無新聞標題可供比對"
    except Exception as e:
        return f"新聞抓取發生錯誤: {e}"

def get_stock_data():
    tks = {"加權指數": "^TWII", "台積電": "2330.TW", "鴻海": "2317.TW"}
    res = ""
    for name, code in tks.items():
        try:
            d = yf.download(code, period="2d", interval="1d", progress=False)
            if not d.empty:
                curr = round(float(d['Close'].iloc[-1]), 2)
                prev = round(float(d['Close'].iloc[-2]), 2)
                diff = round(curr - prev, 2)
                pct = round((diff / prev) * 100, 2)
                res += f"{name}: {curr} (漲跌 {diff}, 幅度 {pct}%)\n"
        except:
            res += f"{name}: 數據取得失敗\n"
    return res

try:
    # 取得台北時間
    tw_time = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_time.strftime('%Y-%m-%d %H:%M:%S')
    
    raw_news = get_real_news_titles()
    stocks = get_stock_data()
    
    prompt = f"""
    任務：你是專業財經主編。請針對以下新聞標題進行交叉比對，找出『工商時報』、『經濟日報』、『Yahoo財經』都在關注的焦點。

    【新聞標題集】：
    {raw_news}

    【最新股市數據】：
    {stocks}

    請嚴格按照以下格式輸出：
    ### 📌 十大新聞交叉比對結果
    (請條列出 3-5 項三家媒體共同關注的重點新聞)

    ### 📈 個股現況與大盤分析
    (針對提供數據給予專業評論)
    """
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    content = response.choices[0].message.content

    # 寫入 index.md
    with open("index.md", "w", encoding="utf-8") as f:
        f.write(f"# 📊 台灣股市 AI 精選情報\n")
        f.write(f"> **最後更新時間：{time_str}**\n\n")
        f.write(content)
        f.write(f"\n\n---\n*流水認證碼: {random.randint(100000, 999999)}*")
    
    print(f"成功更新檔案: {time_str}")

except Exception as e:
    print(f"執行出錯: {e}")
