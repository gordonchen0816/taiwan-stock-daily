import os
import yfinance as yf
import openai
import requests
import random
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

openai.api_key = os.getenv("OPENAI_API_KEY")

def get_real_news_titles():
    # 網址加入隨機數防止快取
    url = f"https://news.google.com/rss/search?q=股市+經濟+台灣&hl=zh-TW&gl=TW&ceid=TW:zh-Hant&nocache={random.random()}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    titles = []
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, features="xml")
        items = soup.find_all('item', limit=20)
        for item in items:
            titles.append(item.title.text)
        return "\n".join(titles) if titles else "新聞源暫時無資料"
    except:
        return "新聞抓取失敗"

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
    tw_time = datetime.utcnow() + timedelta(hours=8)
    # 這裡加入秒數，確保 index.md 內容每次都不同
    time_str = tw_time.strftime('%Y-%m-%d %H:%M:%S')
    
    raw_news = get_real_news_titles()
    stocks = get_stock_data()
    
    prompt = f"""
    任務：你是專業財經主編。請根據標題進行交叉比對，找出『工商、經濟、Yahoo』都在關注的焦點。
    【新聞來源標題】：{raw_news}
    【個股數據】：{stocks}
    格式：
    ### 📌 十大新聞交叉比對結果
    ### 📈 個股現況與大盤分析
    """
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    content = response.choices[0].message.content

    # 強制生成 index.md
    with open("index.md", "w", encoding="utf-8") as f:
        f.write(f"# 📊 台灣股市 AI 精選情報\n")
        f.write(f"> **最後更新時間：{time_str}**\n\n") # 這一行保證內容絕對會變
        f.write(content)
        f.write(f"\n\n---\n*流水號: {random.randint(1000, 9999)}*")
    
    print(f"Successfully generated index.md at {time_str}")

except Exception as e:
    print(f"Error: {e}")
