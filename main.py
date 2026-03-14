import os
import yfinance as yf
import openai
from datetime import datetime

# 設定 OpenAI API Key
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_stock_data():
    # 抓取台積電與加權指數 (台股代號後要加 .TW)
    tickers = {"2330": "2330.TW", "加權指數": "^TWII"}
    report_data = {}
    
    for name, ticker in tickers.items():
        data = yf.Ticker(ticker).history(period="2d")
        if len(data) >= 2:
            close_price = round(data['Close'].iloc[-1], 2)
            change = round(data['Close'].iloc[-1] - data['Close'].iloc[-2], 2)
            report_data[name] = {"price": close_price, "change": change}
    return report_data

def generate_ai_report(data):
    # 這裡讓 AI 根據真實數據寫報告
    prompt = f"你是台灣股市專家。根據以下數據寫一份簡短報告：{data}。請包含大盤走勢與對台積電的看法，使用繁體中文。"
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# 執行流程
try:
    stock_info = get_stock_data()
    ai_analysis = generate_ai_report(stock_info)
    
    # 寫入 index.md
    with open("index.md", "w", encoding="utf-8") as f:
        f.write(f"# 台灣股市每日 AI 分析報告 ({datetime.now().strftime('%Y-%m-%d')})\n\n")
        f.write(ai_analysis)
        f.write("\n\n---\n*數據來源：Yahoo Finance & OpenAI*")
    print("報告更新成功！")
except Exception as e:
    print(f"發生錯誤: {e}")
