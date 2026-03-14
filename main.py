import os
import yfinance as yf
from openai import OpenAI
import requests
import random
import traceback
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# 配置 OpenAI Client (適用於 openai>=1.0.0 版本)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_real_news_titles():
    # 使用 Google News RSS 抓取，確保涵蓋三大報及 Yahoo 的財經標題
    url = f"https://news.google.com/rss/search?q=股市+經濟+台灣&hl=zh-TW&gl=TW&ceid=TW:zh-Hant&t={random.random()}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, features="xml")
        items = soup.find_all('item', limit=30) # 抓取 30 則作為交叉比對樣本
        titles = [item.title.text for item in items]
        return "\n".join(titles) if titles else "目前無新聞標題"
    except Exception as e:
        return f"新聞抓取失敗: {e}"

def get_stock_data():
    # 抓取大盤及重點個股數據
    tks = {"加權指數": "^TWII", "台積電": "2330.TW", "鴻海": "2317.TW"}
    res = ""
    for name, code in tks.items():
        try:
            d = yf.download(code, period="5d", interval="1d", progress=False)
            if not d.empty:
                # 使用 .item() 解決 float 警告
                curr = round(float(d['Close'].iloc[-1].item()), 2)
                prev = round(float(d['Close'].iloc[-2].item()), 2)
                diff = round(curr - prev, 2)
                pct = round((diff / prev) * 100, 2)
                res += f"{name}: {curr} (漲跌: {diff}, 幅度: {pct}%)\n"
        except Exception as e:
            res += f"{name}: 獲取失敗({e})\n"
    return res

try:
    print("--- 啟動 AI 財經主編模式 ---")
    # 設定台北時間 (UTC+8)
    tw_time = datetime.utcnow() + timedelta(hours=8)
    time_str = tw_time.strftime('%Y-%m-%d %H:%M:%S')
    
    # 執行數據抓取
    raw_news = get_real_news_titles()
    stocks = get_stock_data()
    
    # 執行嚴格交叉比對指令
    prompt = f"""
    任務：你是專業財經主編，正在進行『三大財經媒體（工商時報、經濟日報、Yahoo財經）』的頭條交叉比對。
    
    【原始新聞標題集】：
    {raw_news}
    
    【最新股市數據】：
    {stocks}

    指令：
    1. 交叉比對：請從標題集中，找出被不同媒體重複報導、或提及 2 次以上的『核心焦點新聞』。
    2. 排除雜訊：若該新聞僅由單一媒體報導且非重大政經事件，請忽略。不要羅列所有新聞，只要真正的交集。
    3. 嚴格格式輸出：
       ### 📌 三大媒體焦點交集
       - [事件名稱]：說明為何它是今日各家媒體的共識焦點。
       
       ### 📈 個股現況與大盤分析
       - 針對數據 {stocks} 進行分析，給予專業評論與今日操作建議。
    """
    
    # 呼叫 OpenAI API
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "你是一位嚴謹的台灣股市分析專家，擅長過濾雜訊，只找出真正的市場共識。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2 # 降低隨機性
    )
    content = response.choices[0].message.content

    # 強制覆蓋寫入 index.md
    with open("index.md", "w", encoding="utf-8") as f:
        f.write(f"# 📊 台灣股市 AI 精選情報\n")
        f.write(f"> **最後更新時間：{time_str}** (台北時間)\n\n")
        f.write(content)
        f.write(f"\n\n---\n*本報告由 AI 自動生成。驗證序號: {random.randint(1000, 9999)}*")
    
    print(f"--- 執行成功！已生成 index.md，時間：{time_str} ---")

except Exception as e:
    print("--- 執行失敗 ---")
    print(traceback.format_exc())
