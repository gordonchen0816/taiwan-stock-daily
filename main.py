import os
import yfinance as yf
from openai import OpenAI  # 最新版語法
import requests
import random
import traceback
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# 配置 OpenAI 最新版 Client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_real_news_titles():
    url = f"https://news.google.com/rss/search?q=股市+經濟+台灣&hl=zh-TW&gl=TW&ceid=TW:zh-Hant&t={random.random()}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, features="xml")
        items = soup.find_all('item', limit=15)
        titles = [item.title.text for item in items]
        return "\n".join(titles) if titles else "目前無新聞標題"
    except Exception as e:
        return f"新聞抓取失敗: {e}"

def get_stock_data():
    tks = {"加權指數": "^TWII", "台積電": "2330.TW", "鴻海": "2317.TW"}
    res = ""
    for name, code in tks.items():
        try:
            d = yf.download(code, period="5d", interval="1d", progress=False)
            if not d.empty:
                # 修正警告：改用 .item() 確保取得單一數值
                curr = round(float(d['Close'].iloc[-1].item()), 2)
                prev = round(float(d['Close'].iloc[-2].item()), 2)
                diff = round(curr - prev, 2)
                pct = round((diff / prev) * 100, 2)
                res += f"{name}: {curr} ({diff}, {pct}%)\n"
        except Exception as e:
            res += f"{name}: 獲取失敗({e})\n"
    return res

try:
    print("--- 開始執行腳本 (OpenAI v1.0+) ---")
    tw_time = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_time.strftime('%Y-%m-%d %H:%M:%S')
    
    raw_news = get_real_news_titles()
    stocks = get_stock_data()
    
    # 使用 OpenAI 最新版呼叫方式
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "你是一位專業的台灣財經分析師。"},
            {"role": "user", "content": f"請對比新聞：{raw_news}\n並根據數據：{stocks} 寫一份報告。格式：### 📌 十大新聞交叉比對結果\n### 📈 個股現況與大盤分析"}
        ],
        temperature=0.3
    )
    content = response.choices[0].message.content

    with open("index.md", "w", encoding="utf-8") as f:
        f.write(f"# 📊 台灣股市 AI 精選情報\n")
        f.write(f"> **更新時間：{time_str}**\n\n")
        f.write(content)
        f.write(f"\n\n---\n*驗證碼: {random.randint(100, 999)}*")
    
    print("--- 執行成功！檔案已寫入 index.md ---")

except Exception as e:
    print("--- 執行出錯 ---")
    print(traceback.format_exc())
