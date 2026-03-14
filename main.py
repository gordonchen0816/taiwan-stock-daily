import os
import yfinance as yf
import openai
from datetime import datetime

# 設定
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_data():
    # 抓取真實數據
    tks = {"加權指數": "^TWII", "台積電": "2330.TW", "鴻海": "2317.TW"}
    res = {}
    for name, code in tks.items():
        d = yf.Ticker(code).history(period="2d")
        res[name] = round(d['Close'].iloc[-1], 2)
    return res

try:
    data = get_data()
    prompt = f"你是台股專家，請根據數據 {data} 寫一份 200 字內的繁體中文分析。"
    
    # 呼叫 AI
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    content = response.choices[0].message.content

    # 寫入檔案
    with open("index.md", "w", encoding="utf-8") as f:
        f.write(f"# AI 股市日報 ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n")
        f.write(content)
except Exception as e:
    print(f"Error: {e}")
