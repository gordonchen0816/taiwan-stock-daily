import os
from generate_report import generate_report

def main():
    mock_news = [
        {"source": "工商時報", "title": "台積電法說會優於預期"},
        {"source": "經濟日報", "title": "外資反手回補台股 200 億"}
    ]
    
    mock_market = {
        "index": {
            "TAIEX": {"close": 23500, "change": "+150"},
            "OTC": {"close": 270}
        },
        "institutional": {
            "foreign_net": 1500, "trust_net": 200, "dealer_net": -50, "total_net": 1650
        },
        "stocks": [
            {"stock_id": "2330", "close": 1050, "RSI14": 65, "SMA7": 1020, "SMA20": 1000}
        ]
    }

    print("🚀 正在測試 OpenAI API 產生報告...")
    
    try:
        report = generate_report(mock_news, mock_market)
        with open("index.md", "w", encoding="utf-8") as f:
            f.write(report)
        print("✅ 測試成功！請查看資料夾中的 index.md 檔案。")
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")

if __name__ == "__main__":
    main()
