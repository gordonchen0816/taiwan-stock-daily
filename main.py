import os
import yfinance as yf
import openai
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# 設定 OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_real_news():
    # 抓取 Yahoo 財經的新聞標題作為基礎原料
    headers = {'User-Agent': 'Mozilla/5.0'}
    url = "https://tw.stock.yahoo.com/news/"
    titles = []
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        # 抓取標題標籤 (Yahoo 的標籤結構)
        for h3 in soup.find_all('h3', limit=15):
            titles.append(h3.text.strip())
        return "\n".join(titles) if titles else "無法取得新聞標題"
    except:
        return "新聞抓取失敗"

def get_stock_data():
    tks = {"加權指數": "^TWII", "台積電": "2330.TW", "鴻海": "2317.TW"}
    res = {}
    for name, code in tks.items():
        try:
            d = yf.Ticker(code).history(period="2d")
            if not d.empty:
                curr = round(d['Close'].iloc[-1], 2)
                prev = d['Close'].iloc[-2]
                diff = round(curr - prev, 2)
                pct = round((diff / prev) * 100, 2)
                res[name] = f"價格: {curr}, 漲跌: {diff} ({pct}%)"
        except:
            res[name] = "數據暫不穩定"
    return res

try:
    tw_time = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_time.strftime('%Y-%m-%d %H:%M')
    
    stocks = get_stock_data()
    raw_news = get_real_news()
    
    prompt = f"""
    今天是 {time_str}。
    以下是從財經門戶抓取的最新標題：
    {raw_news}
    
    任務 1：請從上述標題中，找出『工商時報』、『經濟日報』、『Yahoo財經』都在關注的重大交集新聞（三家都有報的主題）。如果標題中看不出來源，請根據內容推論最重大的 1-2 則新聞。
    任務 2：針對以下個股數據進行評論：{stocks}。
    
    請用繁體中文回答，並保持專業分析師口吻。
    """
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    content = response.choices[0].message.content

    with open("index.md", "w", encoding="utf-8") as f:
        f.write(f"# 📊 台灣股市 AI 精選情報 ({time_str})\n\n")
        f.write(content)
        f.write(f"\n\n---\n*數據來源：Yahoo Finance, OpenAI | 抓取範圍：工商、經濟、Yahoo*")

    print("交集新聞分析完成")

except Exception as e:
    print(f"發生錯誤: {e}")
