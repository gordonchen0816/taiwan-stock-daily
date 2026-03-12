"""
主程式：串接所有模組，產生每日 JSON 資料檔
執行方式：python scripts/main.py
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# 確保可以 import 同層模組
sys.path.insert(0, str(Path(__file__).parent))

from fetch_news    import fetch_news
from fetch_market  import fetch_all_market_data
from generate_report import generate_report
from cleanup       import cleanup_old_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
DOCS_DIR = Path(__file__).parent.parent / "docs"


def main():
    today = datetime.today().strftime("%Y-%m-%d")
    logger.info(f"🚀 開始執行：{today}")

    # 1. 抓新聞
    logger.info("── 步驟 1：抓取財經新聞")
    news = fetch_news()

    # 2. 抓市場數據
    logger.info("── 步驟 2：抓取市場數據")
    market = fetch_all_market_data()

    # 3. 產 GPT 報告
    logger.info("── 步驟 3：產生 AI 彙整報告")
    report_md = generate_report(news, market)

    # 4. 組合輸出 JSON
    output = {
        "date":    today,
        "news":    news,
        "market":  market,
        "report":  report_md,
    }

    # 5. 寫入 data/YYYY-MM-DD.json
    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / f"{today}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    logger.info(f"✅ 資料已寫入：{out_path}")

    # 6. 更新 docs/latest.json（前端讀這個）
    DOCS_DIR.mkdir(exist_ok=True)
    latest_path = DOCS_DIR / "latest.json"
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 7. 更新日期索引（前端翻頁用）
    index_path = DOCS_DIR / "index_list.json"
    index = []
    if index_path.exists():
        with open(index_path) as f:
            index = json.load(f)
    if today not in index:
        index.insert(0, today)
        index = index[:180]  # 最多保留 180 筆
    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)

    # 8. 清理舊資料
    logger.info("── 步驟 4：清理舊資料")
    cleanup_old_data(days=180)

    logger.info("🎉 全部完成！")


if __name__ == "__main__":
    main()
