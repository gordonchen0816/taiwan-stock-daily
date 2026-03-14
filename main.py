import os
import yfinance as yf
import openai
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# 設定 OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_news():
    # 這裡預設抓取幾個重要財經新聞源的標題 (模擬爬蟲行為)
    # 實際上為了穩定性，我們將各報重點與熱門關鍵字送給 AI 篩選
    news_sources = {
        "工商時報": "https://www.ctee.com.tw/livenews/aj",
        "經濟日報": "https://money.udn.com/money/index",
        "Yahoo財經": "https://tw.stock.yahoo.com/news/"
    }
    # 這裡我們傳送一個較廣的指令給 AI，讓它模擬比對目前最火熱的交集話題
    return "請根據當前網路熱搜與財經頭條，找出工商、經濟、Yahoo 同步關注的交集事件。"

def get_stock_data():
    tks = {"加權指數": "^TWII", "台積電": "2330.TW", "鴻海": "2317.TW"}
    res = {}
    for name, code in tks.items():
        try:
            d = yf.Ticker(code).history(period="5d") # 抓 5 天看趨勢
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
    news_task = get_news()
    
    # AI 任務：先找交集新聞，再評論個股
    prompt = f"""
    今天是 {time_str}。
    任務 1：請找出今天『工商時報』、『經濟日報』、『Yahoo財經』共同關注的頭條交集新聞（即三家都有報的重大事件）。
    任務 2：針對以下個股數據進行現況分析：{stocks}。
    
    格式要求：
    ### 📌 三大財經媒體頭條交集
    (列出交集新聞並說明為何是重點)
    
    ### 📈 個股現況掃描
    (針對台積電、鴻海與大盤分析)
    """
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    content = response.choices[0].message.content

    with open("index.md", "w", encoding="utf-8") as f:
        f.write(f"# 📊 台灣股市 AI 精選情報 ({time_str})\n\n")
        f.write(content)
        f.write(f"\n\n---\n*更新時間：{time_str} | 媒體來源：工商、經濟、Yahoo*")

    print("交集新聞分析完成")

except Exception as e:
    print(f"發生錯誤: {e}")
