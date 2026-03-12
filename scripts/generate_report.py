"""
模組三：呼叫 GPT-4o-mini 產生繁體中文條列式每日台股彙整報告
"""

import os
from openai import OpenAI

client = OpenAI()  # 自動讀取環境變數 OPENAI_API_KEY


def _fmt_institutional(inst: dict) -> str:
    if not inst:
        return "（今日無法人資料）"
    def arrow(v): return f"+{v:,}" if v > 0 else f"{v:,}"
    return (
        f"外資：{arrow(inst.get('foreign_net', 0))} 張　"
        f"投信：{arrow(inst.get('trust_net', 0))} 張　"
        f"自營：{arrow(inst.get('dealer_net', 0))} 張　"
        f"合計：{arrow(inst.get('total_net', 0))} 張"
    )


def _fmt_index(index: dict) -> str:
    lines = []
    if "TAIEX" in index:
        t = index["TAIEX"]
        lines.append(f"加權指數：{t['close']:,.0f}　漲跌：{t['change']}")
    if "OTC" in index:
        o = index["OTC"]
        lines.append(f"櫃買指數：{o['close']}")
    return "\n".join(lines) if lines else "（無大盤資料）"


def _fmt_stocks(stocks: list) -> str:
    lines = []
    for s in stocks:
        if "error" in s:
            continue
        lines.append(
            f"{s['stock_id']}｜收盤 {s['close']}　RSI {s['RSI14']}　"
            f"SMA7 {s['SMA7']} / SMA20 {s['SMA20']}　"
            f"30日高 {s['high_30d']} / 低 {s['low_30d']}"
        )
    return "\n".join(lines) if lines else "（無個股資料）"


def generate_report(news: list, market: dict) -> str:
    """
    輸入新聞列表與市場數據，回傳繁體中文條列式報告字串。
    """
    news_text = "\n".join(
        [f"・[{n['source']}] {n['title']}" for n in news[:15]]
    )

    prompt = f"""
你是一位專業的台灣股市分析助理。
請根據以下資訊，用**繁體中文**產出今日台股每日彙整報告。
格式要求：條列式、簡潔有力、適合上班族在 5 分鐘內快速瀏覽。

---
【大盤指數】
{_fmt_index(market.get('index', {}))}

【三大法人買賣超】
{_fmt_institutional(market.get('institutional', {}))}

【個股技術面快照】
{_fmt_stocks(market.get('stocks', []))}

【今日財經新聞標題】
{news_text}
---

請按以下結構輸出（使用 Markdown）：

## 📈 大盤總覽
（簡述今日大盤表現與法人動向，2-3 行）

## 📰 新聞重點摘要
（條列 5 則最重要新聞，每則一行，含來源與一句話重點）

## 🔍 個股技術面速覽
（針對觀察清單中 RSI 或均線有訊號的個股，條列說明）

## ⚠️ 今日需注意
（潛在風險或值得留意的市場訊號，1-3 點）
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1200,
        temperature=0.4,
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    # 測試用假資料
    dummy_news = [
        {"source": "工商時報", "title": "台積電法說會釋利多，外資大買 5 萬張", "link": "", "published": ""},
        {"source": "經濟日報", "title": "Fed 暗示降息腳步放緩，亞股承壓", "link": "", "published": ""},
    ]
    dummy_market = {
        "index": {"TAIEX": {"close": 21500, "change": "+123.45"}},
        "institutional": {"foreign_net": 25000, "trust_net": -3000, "dealer_net": 1200, "total_net": 23200},
        "stocks": [
            {"stock_id": "2330", "close": 980, "RSI14": 62.3, "SMA7": 965, "SMA20": 950, "high_30d": 990, "low_30d": 910},
        ],
    }
    print(generate_report(dummy_news, dummy_market))
