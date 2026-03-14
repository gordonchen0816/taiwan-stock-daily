import os
import yfinance as yf
import openai
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# OpenAI 配置
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_real_news_titles():
    # 使用 Google News RSS 抓取台灣財經新聞標題
    url = "https://news.google.com/rss/search?q=股市+經濟+台灣&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
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
    time_str = tw_time.strftime('%Y-%m-%d %H:%M')
    
    raw_news = get_real_news_titles()
    stocks = get_stock_data()
    
    prompt = f"""
    任務：你是專業財經主編。請根據標題進行交叉比對，找出『工商、經濟、Yahoo』都在關注的焦點。

    【新聞標題集】：
    {raw_news}

    【個股數據】：
    {stocks}

    請嚴格按照以下格式輸出：
    ### 📌 十大新聞交叉比對結果
    (請列出 3-5 項各大媒體重疊關注的焦點)

    ### 📈 個股現況與大盤分析
    (分析數據並給予專業建議)
    """
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    content = response.choices[0].message.content

    # 強制生成 index.md
    with open("index.md", "w", encoding="utf-8") as f:
        f.write(f"# 📊 台灣股市 AI 精選情報 ({time_str})\n\n")
        f.write(content)
        f.write(f"\n\n---\n*更新時間：{time_str} | 數據來源：Google News, Yahoo Finance*")
    
    print("Successfully generated index.md")

except Exception as e:
    print(f"Error: {e}")
