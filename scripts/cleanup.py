"""
模組四：清理超過 180 天的舊 JSON 資料
"""

import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"


def cleanup_old_data(days: int = 180):
    cutoff = datetime.today() - timedelta(days=days)
    removed = 0

    for f in DATA_DIR.glob("*.json"):
        try:
            # 檔名格式：YYYY-MM-DD.json
            file_date = datetime.strptime(f.stem, "%Y-%m-%d")
            if file_date < cutoff:
                f.unlink()
                logger.info(f"🗑️ 已刪除：{f.name}")
                removed += 1
        except ValueError:
            pass  # 非日期格式檔案略過

    logger.info(f"✅ 清理完成，共刪除 {removed} 個舊檔案")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cleanup_old_data()
