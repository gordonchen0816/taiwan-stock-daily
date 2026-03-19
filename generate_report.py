import os
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


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
