import os
import yfinance as yf
import openai
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# 設定 OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_real_news_titles():
    # 使用 Google News RSS 抓取台灣財經新聞標題，這比直接爬 Yahoo 更穩
    url = "https://news.google.com/rss/search?q=股市+經濟+台灣&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    headers = {'User-Agent': 'Mozilla/5.0'}
    titles = []
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, features="xml")
        items = soup.find_all('item', limit=20) # 抓 20 則確保夠多
        for item in items:
            titles.append(item.title.text)
        return "\n".join(titles)
    except Exception as e:
        return f"新聞抓取失敗: {str(e)}"

def get_stock_data():
    tks = {"加權指數": "^TWII", "台積電": "2330.TW", "鴻海": "2317.TW"}
    res = ""
    for name, code in tks.items():
        try:
            d = yf.Ticker(code).history(period="2d")
            if not d.empty:
                curr = round(d['Close'].iloc[-1], 2)
                prev = d['Close'].iloc[-2]
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
    
    # 嚴格規範 AI 輸出格式
    prompt = f"""
    任務說明：
    你是一位專業的財經編輯。請根據以下提供的最新標題進行交叉比對，並針對個股進行分析。

    資料 1 - 最新新聞標題：
    {raw_news}

    資料 2 - 股市數據：
    {stocks}

    請嚴格按照以下格式輸出：

    ### 📌 十大新聞交叉比對結果
    (請從標題中分析出『工商時報』、『經濟日報』與『Yahoo財經』共同關注的焦點。請列出最重要的 3-5 項交集重點，並用條列式呈現，不要說廢話。)

    ### 📈 個股現況與大盤分析
    (根據提供的數據分析當前市場狀態與個股強弱，最後給予一段專業建議。)
    """
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5 # 讓 AI 輸出更穩定
    )
    content = response.choices[0].message.content

    with open("index.md", "w", encoding="utf-8") as f:
        f.write(f"# 📊 台灣股市 AI 精選情報 ({time_str})\n\n")
        f.write(content)
        f.write(f"\n\n---\n*數據更新時間：{time_str} | 爬蟲來源：Google News RSS, Yahoo Finance*")

    print("報告產出成功")

except Exception as e:
    print(f"錯誤: {e}")
