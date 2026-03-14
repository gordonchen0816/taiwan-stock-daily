import os
import openai

openai.api_key = os.environ.get("OPENAI_API_KEY")

def _fmt_institutional(inst):
    if not inst:
        return "（今日無法人資料）"
    def arrow(v): return f"+{v:,}" if v > 0 else f"{v:,}"
    return (
        f"外資：{arrow(inst.get('foreign_net', 0))} 張　"
        f"投信：{arrow(inst.get('trust_net', 0))} 張　"
        f"自營：{arrow(inst.get('dealer_net', 0))} 張　"
        f"合計：{arrow(inst.get('total_net', 0))} 張"
    )

def _fmt_index(index):
    lines = []
    if "TAIEX" in index:
        t = index["TAIEX"]
        lines.append(f"加權指數：{t['close']:,.0f}　漲跌：{t['change']}")
    if "OTC" in index:
        o = index["OTC"]
        lines.append(f"櫃買指數：{o['close']}")
    return "\n".join(lines) if lines else "（無大盤資料）"

def _fmt_stocks(stocks):
    lines = []
    for s in stocks:
        if "error" in s:
            continue
        lines.append(
            f"{s['stock_id']}｜收盤 {s['close']}　RSI {s['RSI14']}　"
            f"SMA7 {s['SMA7']} / SMA20 {s['SMA20']}"
        )
    return "\n".join(lines) if lines else "（無個股資料）"

def generate_report(news, market):
    news_text = "\n".join(
        [f"・[{n['source']}] {n['title']}" for n in news[:15]]
    )
    prompt = f"""你是一位專業的台灣股市分析助理。請根據以下資訊，用繁體中文產出今日台股每日彙整報告。格式要求：條列式、簡潔有力。

【大盤指數】
{_fmt_index(market.get('index', {}))}

【三大法人買賣超】
{_fmt_institutional(market.get('institutional', {}))}

【個股技術面快照】
{_fmt_stocks(market.get('stocks', []))}

【今日財經新聞標題】
{news_text}

請按以下結構輸出（使用 Markdown）：
## 📈 大盤總覽
## 📰 新聞重點摘要
## 🔍 個股技術面速覽
## ⚠️ 今日需注意"""

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1200,
    )
    return response.choices[0].message.content
