#!/usr/bin/env python3
"""
MUSE Daily Report Generator & Email Sender
Dr. Chen 私人投組日報自動化
"""

import os
import json
import smtplib
import traceback
import yfinance as yf
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ─────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent
POS_FILE  = BASE_DIR / "muse" / "positions.json"
TW_TZ     = timedelta(hours=8)
NOW_TW    = datetime.utcnow() + TW_TZ
DATE_STR  = NOW_TW.strftime("%Y/%m/%d")
DATE_FILE = NOW_TW.strftime("%Y%m%d")
WEEKDAY   = NOW_TW.weekday()          # 0=Mon … 6=Sun


# ─────────────────────────────────────────────
#  Skip weekends
# ─────────────────────────────────────────────
if WEEKDAY >= 5:
    print(f"[INFO] 今日 {DATE_STR} 為假日，跳過發送")
    raise SystemExit(0)


# ─────────────────────────────────────────────
#  Load positions
# ─────────────────────────────────────────────
with open(POS_FILE, encoding="utf-8") as f:
    cfg = json.load(f)

h      = cfg["holdings"]
cash   = cfg["cash"]
params = cfg["muse_params"]
email_cfg = cfg["email"]


# ─────────────────────────────────────────────
#  Fetch prices via yfinance
# ─────────────────────────────────────────────
TICKERS = {
    "2330": "2330.TW",
    "2383": "2383.TW",
    "NVDA": "NVDA",
    "MU":   "MU",
    "TWII": "^TWII",
    "FX":   "TWD=X",          # USD/TWD
    "3481": "3481.TW",
    "SOX":  "^SOX",
}

def fetch_price(symbol: str) -> dict:
    try:
        d = yf.download(symbol, period="5d", interval="1d",
                        progress=False, auto_adjust=True)
        if d.empty:
            return {"price": None, "prev": None, "chg": None, "pct": None}
        price = round(float(d["Close"].iloc[-1].item()), 2)
        prev  = round(float(d["Close"].iloc[-2].item()), 2) if len(d) >= 2 else price
        chg   = round(price - prev, 2)
        pct   = round(chg / prev * 100, 2) if prev else 0
        return {"price": price, "prev": prev, "chg": chg, "pct": pct}
    except Exception as e:
        print(f"[WARN] {symbol} 抓取失敗: {e}")
        return {"price": None, "prev": None, "chg": None, "pct": None}

print("[INFO] 抓取即時股價…")
prices = {k: fetch_price(v) for k, v in TICKERS.items()}

def p(key):
    return prices[key]["price"]

# fallback: if market closed / holiday, use last known
def safe(key, fallback):
    return p(key) if p(key) else fallback

tsm_price  = safe("2330", 2510)
tl_price   = safe("2383", 5825)
nvda_price = safe("NVDA", 210.69)
mu_price   = safe("MU",   1133.99)
fx         = safe("FX",   31.7)
twii       = safe("TWII", None)
sox_price  = safe("SOX",  None)
innolux    = safe("3481", None)


# ─────────────────────────────────────────────
#  Calculate NAV + Boundaries
# ─────────────────────────────────────────────
tsm_shares = h["2330"]["shares"]; tsm_cost = h["2330"]["cost_twd"]
tl_shares  = h["2383"]["shares"]; tl_cost  = h["2383"]["cost_twd"]
nvda_shares= h["NVDA"]["shares"]; nvda_cost= h["NVDA"]["cost_usd"]
mu_shares  = h["MU"]["shares"];   mu_cost  = h["MU"]["cost_usd"]
twd_cash   = cash["twd"]
usd_cash   = cash["usd"]

tsm_mv   = tsm_price  * tsm_shares
tl_mv    = tl_price   * tl_shares
nvda_mv  = nvda_price * nvda_shares * fx
mu_mv    = mu_price   * mu_shares   * fx
cash_twd = twd_cash   + usd_cash    * fx
tw_stock = tsm_mv + tl_mv
us_stock = nvda_mv + mu_mv
total_nav= tw_stock + us_stock + cash_twd

B = cash_twd / total_nav
C = (tsm_mv + tl_mv + nvda_mv) / total_nav
D = cash_twd / ((tw_stock + us_stock) * 0.20)
E = (tsm_price / params["eps_base"] - params["pe_mean"]) / params["pe_std"]

def pnl_twd(curr, cost, shares, is_usd=False):
    if is_usd:
        return (curr - cost) * shares * fx
    return (curr - cost) * shares

def ret_pct(curr, cost):
    return (curr - cost) / cost * 100

tsm_pl  = pnl_twd(tsm_price,  tsm_cost,  tsm_shares)
tl_pl   = pnl_twd(tl_price,   tl_cost,   tl_shares)
nvda_pl = pnl_twd(nvda_price, nvda_cost, nvda_shares, is_usd=True)
mu_pl   = pnl_twd(mu_price,   mu_cost,   mu_shares,   is_usd=True)
total_pl= tsm_pl + tl_pl + nvda_pl + mu_pl

# ─────────────────────────────────────────────
#  Mandate check
# ─────────────────────────────────────────────
mandates_violated = []
if B < params["b_threshold"]:
    mandates_violated.append(f"B={B:.1%}（門檻{params['b_threshold']:.0%}）禁止買入")
if C > params["c_threshold"]:
    mandates_violated.append(f"C={C:.1%}（門檻{params['c_threshold']:.0%}）禁止AI鏈加碼")
if D < params["d_threshold"]:
    mandates_violated.append(f"D={D:.3f}（門檻{params['d_threshold']:.1f}）尾部覆蓋不足")

def status_icon(ok): return "🟢" if ok else "🔴"
def watch_icon(ok):  return "🟡" if ok else "🔴"

B_ok = B >= params["b_threshold"]
C_ok = C <= params["c_threshold"]
D_ok = D >= params["d_threshold"]
E_ok = E <= params["e_threshold"]

def chg_str(key, decimals=2):
    d = prices[key]
    if d["chg"] is None:
        return "—"
    sign = "+" if d["chg"] >= 0 else ""
    return f"{sign}{d['chg']:.{decimals}f} ({sign}{d['pct']:.2f}%)"

def lamp_class(key):
    d = prices[key]
    if d["pct"] is None:
        return "flat"
    pct = d["pct"]
    if pct >= 9.5:  return "limit-up"
    if pct > 0:     return "up"
    if pct <= -9.5: return "limit-down"
    if pct < 0:     return "down"
    return "flat"

# ─────────────────────────────────────────────
#  CFO Verdict
# ─────────────────────────────────────────────
if not B_ok and not D_ok:
    cfo_cmd = f"禁止買入。持倉不動。等待2383≥{params['target_2383']:,}停利解鎖B+D雙紅。"
    cfo_next = f"2383 → {params['target_2383']:,} 停利 | 07/16 台積電法說"
elif not B_ok:
    cfo_cmd = f"邊界B跌破門檻，禁止買入。持倉不動。"
    cfo_next = f"等待B恢復 ≥ 15%"
else:
    cfo_cmd = f"邊界正常。依決策樹監控觸發點。"
    cfo_next = f"2330短線目標 {params['target_short_2330']:,}"


# ─────────────────────────────────────────────
#  Generate HTML
# ─────────────────────────────────────────────

def fmt_num(n, decimals=0):
    if n is None:
        return "—"
    fmt = f"{{:,.{decimals}f}}"
    return fmt.format(n)

def fmt_pnl(n):
    if n is None: return "—"
    sign = "+" if n >= 0 else ""
    return f"{sign}{n:,.0f}"

LAMP_CSS = {
    "limit-up":   ("#E05252", "漲停🔴"),
    "up":         ("#E87A6E", "上漲"),
    "flat":       ("#6B7280", "平盤"),
    "down":       ("#4E8FC4", "下跌"),
    "limit-down": ("#2E6FA3", "跌停🔵"),
}

def lamp_html(key):
    lc = lamp_class(key)
    color, label = LAMP_CSS.get(lc, ("#6B7280", "—"))
    return f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{color};margin-right:4px;vertical-align:middle;box-shadow:0 0 5px {color};"></span>{label}'

def boundary_chip(label, value_str, threshold_str, ok, watch=False):
    if ok:
        color = "#3FB97A"; bg = "rgba(63,185,122,0.08)"; border = "rgba(63,185,122,0.35)"
        icon = "🟢"
    elif watch:
        color = "#C9A855"; bg = "rgba(201,168,85,0.08)"; border = "rgba(201,168,85,0.35)"
        icon = "🟡"
    else:
        color = "#E05252"; bg = "rgba(224,82,82,0.08)"; border = "rgba(224,82,82,0.35)"
        icon = "🔴"
    return f"""
    <div style="flex:1;background:{bg};border:1px solid {border};border-radius:6px;padding:10px;text-align:center;">
        <div style="font-family:monospace;font-size:10px;color:#6B7280;letter-spacing:1px;margin-bottom:4px;">{label}</div>
        <div style="font-family:monospace;font-size:20px;font-weight:700;color:{color};line-height:1;">{value_str}</div>
        <div style="font-family:monospace;font-size:9px;color:#6B7280;margin-top:3px;">門檻 {threshold_str} {icon}</div>
    </div>"""

# Mandate alert bar
mandate_html = ""
if mandates_violated:
    items = " &nbsp;|&nbsp; ".join(mandates_violated)
    mandate_html = f"""
    <div style="background:rgba(224,82,82,0.08);border:1px solid rgba(224,82,82,0.4);
                border-radius:5px;padding:8px 14px;font-family:monospace;font-size:11px;
                color:#E05252;margin-bottom:10px;">
        🔴 <strong>決策禁區觸發</strong>：{items}
    </div>"""

# Stock rows
def stock_row(code, name, price_val, cost_val, shares, pl_val, ret, chg_key, is_usd=False):
    cost_str = f"USD {cost_val:.2f}" if is_usd else f"TWD {cost_val:,.2f}"
    ret_color = "#3FB97A" if ret >= 0 else "#E05252"
    pl_color  = "#3FB97A" if pl_val >= 0 else "#E05252"
    return f"""
    <tr style="border-bottom:1px solid #1C2030;">
        <td style="padding:6px 10px;font-family:monospace;color:#C9A855;font-weight:700;">{code}</td>
        <td style="padding:6px 10px;color:#8B9498;">{name}</td>
        <td style="padding:6px 10px;font-family:monospace;font-weight:700;">{fmt_num(price_val,2 if is_usd else 0)}</td>
        <td style="padding:6px 10px;font-family:monospace;">{lamp_html(code)}</td>
        <td style="padding:6px 10px;font-family:monospace;color:{ret_color};font-weight:600;">{ret:+.1f}%</td>
        <td style="padding:6px 10px;font-family:monospace;color:{pl_color};">{fmt_pnl(pl_val)}</td>
        <td style="padding:6px 10px;font-family:monospace;color:#6B7280;font-size:10px;">{cost_str} × {shares}股</td>
    </tr>"""

twii_str = f"{fmt_num(twii)} ({chg_str('TWII',0)})" if twii else "—"
sox_str  = f"{fmt_num(sox_price,0)} ({chg_str('SOX',0)})" if sox_price else "—"
inn_str  = f"{fmt_num(innolux,0)} ({chg_str('3481',0)})" if innolux else f"66 (6/22收盤)"

alert_color = "#E05252" if mandates_violated else "#3FB97A"
alert_label = f"⚠️ {len(mandates_violated)}條禁令觸發" if mandates_violated else "✅ 無禁令"

EMAIL_HTML = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>MUSE日報 {DATE_STR}</title>
</head>
<body style="margin:0;padding:0;background:#0A0D13;color:#DEDCd6;font-family:'Noto Sans TC',Arial,sans-serif;font-size:13px;">
<div style="max-width:900px;margin:0 auto;padding:0;">

  <!-- ══ HEADER ══ -->
  <div style="background:#0F1319;border-bottom:2px solid #C9A855;padding:16px 24px;display:flex;justify-content:space-between;align-items:center;">
    <div>
      <div style="font-family:monospace;font-size:10px;color:#6B7280;letter-spacing:3px;margin-bottom:4px;">MUSE · DAILY REPORT · DR. CHEN CONFIDENTIAL</div>
      <div style="font-family:monospace;font-size:24px;font-weight:700;color:#C9A855;letter-spacing:2px;">MUSE DAILY</div>
      <div style="font-family:monospace;font-size:10px;color:#6B7280;margin-top:4px;">{DATE_STR} &nbsp;盤後更新 &nbsp;|&nbsp; 自動生成</div>
    </div>
    <div style="text-align:center;">
      <div style="font-family:monospace;font-size:10px;color:#6B7280;letter-spacing:2px;margin-bottom:4px;">TOTAL NAV</div>
      <div style="font-family:monospace;font-size:28px;font-weight:700;color:#DEDCd6;">{fmt_num(total_nav)}</div>
      <div style="font-family:monospace;font-size:12px;color:#3FB97A;font-weight:600;">總浮盈 {fmt_pnl(total_pl)} TWD</div>
    </div>
    <div style="text-align:right;">
      <div style="font-family:monospace;font-size:10px;background:#C9A855;color:#0A0D13;padding:3px 10px;border-radius:3px;font-weight:700;margin-bottom:6px;display:inline-block;">FILES v2.7</div><br>
      <div style="font-family:monospace;font-size:10px;color:{alert_color};">{alert_label}</div>
      <div style="font-family:monospace;font-size:10px;color:#6B7280;margin-top:4px;">EPS 140元鎖定至 07/16</div>
    </div>
  </div>

  <!-- ══ 區塊一：持股現況 ══ -->
  <div style="background:#0E1219;border-left:4px solid #4A7FA5;padding:0;">
    <div style="background:linear-gradient(90deg,rgba(74,127,165,0.2) 0%,transparent 60%);padding:10px 18px;border-bottom:1px solid #1C2030;">
      <span style="font-family:monospace;font-size:11px;color:#4A7FA5;letter-spacing:2px;font-weight:700;">01</span>
      <span style="font-size:17px;font-weight:900;color:#7BB5D8;margin-left:10px;">持股現況 · 天條 · CFO裁決</span>
      <span style="font-family:monospace;font-size:10px;color:#6B7280;margin-left:12px;">Position Status · Mandates · CFO Verdict</span>
    </div>
    <div style="padding:12px 18px;">
      {mandate_html}

      <!-- 持倉表 -->
      <table style="width:100%;border-collapse:collapse;margin-bottom:12px;">
        <thead>
          <tr style="border-bottom:1px solid #242A36;">
            <th style="font-family:monospace;font-size:9px;color:#6B7280;padding:4px 10px;text-align:left;letter-spacing:1px;">標的</th>
            <th style="font-family:monospace;font-size:9px;color:#6B7280;padding:4px 10px;text-align:left;">名稱</th>
            <th style="font-family:monospace;font-size:9px;color:#6B7280;padding:4px 10px;text-align:left;">現價</th>
            <th style="font-family:monospace;font-size:9px;color:#6B7280;padding:4px 10px;text-align:left;">今日</th>
            <th style="font-family:monospace;font-size:9px;color:#6B7280;padding:4px 10px;text-align:left;">浮盈率</th>
            <th style="font-family:monospace;font-size:9px;color:#6B7280;padding:4px 10px;text-align:left;">浮盈(TWD)</th>
            <th style="font-family:monospace;font-size:9px;color:#6B7280;padding:4px 10px;text-align:left;">成本 × 股數</th>
          </tr>
        </thead>
        <tbody>
          {stock_row("2330","台積電",tsm_price,tsm_cost,tsm_shares,tsm_pl,ret_pct(tsm_price,tsm_cost),"2330")}
          {stock_row("2383","台光電",tl_price,tl_cost,tl_shares,tl_pl,ret_pct(tl_price,tl_cost),"2383")}
          {stock_row("NVDA","NVIDIA",nvda_price,nvda_cost,nvda_shares,nvda_pl,ret_pct(nvda_price,nvda_cost),"NVDA",is_usd=True)}
          {stock_row("MU","美光科技",mu_price,mu_cost,mu_shares,mu_pl,ret_pct(mu_price,mu_cost),"MU",is_usd=True)}
        </tbody>
      </table>

      <!-- 邊界 -->
      <div style="display:flex;gap:8px;margin-bottom:12px;">
        {boundary_chip("B · 流動性",    f"{B:.1%}", "≥15%", B_ok)}
        {boundary_chip("C · AI集中度",  f"{C:.1%}", "≤75%", C_ok, watch=C>0.70)}
        {boundary_chip("D · 尾部覆蓋",  f"{D:.3f}", "≥1.2", D_ok)}
        {boundary_chip("E · 估值位階",  f"{E:+.3f}σ","≤+2.0σ", E_ok)}
      </div>

      <!-- 決策樹 -->
      <div style="background:#0C0F16;border:1px solid #242A36;border-radius:5px;padding:10px 14px;font-family:monospace;font-size:10px;margin-bottom:10px;">
        <div style="color:#6B7280;font-size:9px;letter-spacing:1px;border-bottom:1px solid #1C2030;padding-bottom:4px;margin-bottom:6px;">DECISION TREE · {DATE_STR}</div>
        <div style="padding:3px 0;border-bottom:1px dashed #1C2030;"><span style="color:#6B7280;display:inline-block;width:200px;">IF 2330 &gt; {params['target_short_2330']:,}</span> → 評估軌道B 25股停利 &nbsp;<span>⬜</span></div>
        <div style="padding:3px 0;border-bottom:1px dashed #1C2030;color:#3FB97A;"><span style="color:#6B7280;display:inline-block;width:200px;">IF 2383 ≥ {params['target_2383']:,}</span> → <strong>停利65股 → 解鎖B+D（優先！）</strong> ⬜</div>
        <div style="padding:3px 0;border-bottom:1px dashed #1C2030;color:#E05252;"><span style="color:#6B7280;display:inline-block;width:200px;">IF 2383 &lt; {params['stop_loss_2383']:,}</span> → 天條5立即執行（65股）⬜</div>
        <div style="padding:3px 0;border-bottom:1px dashed #1C2030;color:#E05252;"><span style="color:#6B7280;display:inline-block;width:200px;">IF MU &lt; {params['stop_loss_mu']:,}</span> → 天條1執行（23股）⬜</div>
        <div style="padding:3px 0;"><span style="color:#6B7280;display:inline-block;width:200px;">ELSE</span> <span style="color:#3FB97A;">→ 持倉不動，等待觸發點 ✅</span></div>
      </div>

      <!-- CFO -->
      <div style="border:1px solid #C9A855;background:#1A1508;border-radius:5px;padding:10px 16px;display:flex;gap:12px;align-items:center;">
        <div style="font-family:monospace;font-size:9px;color:#7A6230;letter-spacing:2px;flex-shrink:0;">CFO<br>裁決</div>
        <div style="font-family:monospace;font-size:13px;font-weight:700;color:#C9A855;flex:1;">{cfo_cmd}</div>
        <div style="font-family:monospace;font-size:9px;color:#6B7280;flex-shrink:0;text-align:right;line-height:1.8;">{cfo_next}</div>
      </div>
    </div>
  </div>

  <!-- ══ 區塊二：市場熱度 ══ -->
  <div style="background:#101620;border-left:4px solid #5A8F6A;padding:0;border-top:1px solid #1C2030;">
    <div style="background:linear-gradient(90deg,rgba(90,143,106,0.2) 0%,transparent 60%);padding:10px 18px;border-bottom:1px solid #1C2030;">
      <span style="font-family:monospace;font-size:11px;color:#5A8F6A;letter-spacing:2px;font-weight:700;">02</span>
      <span style="font-size:17px;font-weight:900;color:#7DC49A;margin-left:10px;">市場熱度 · 大盤指數 · 熱點個股</span>
      <span style="font-family:monospace;font-size:10px;color:#6B7280;margin-left:12px;">Market Heat · Index · SOX · ADR</span>
    </div>
    <div style="padding:12px 18px;">
      <!-- 指標 grid -->
      <div style="display:flex;gap:8px;margin-bottom:12px;">
        <div style="flex:1;background:#0C0F16;border:1px solid #1C2030;border-radius:5px;padding:10px;text-align:center;">
          <div style="font-family:monospace;font-size:9px;color:#6B7280;letter-spacing:1px;margin-bottom:4px;">台股加權指數</div>
          <div style="font-family:monospace;font-size:20px;font-weight:700;color:#E87A6E;">{fmt_num(twii,0) if twii else "—"}</div>
          <div style="font-family:monospace;font-size:10px;color:#E87A6E;">{chg_str("TWII",0)}</div>
        </div>
        <div style="flex:1;background:#0C0F16;border:1px solid #1C2030;border-radius:5px;padding:10px;text-align:center;">
          <div style="font-family:monospace;font-size:9px;color:#6B7280;letter-spacing:1px;margin-bottom:4px;">費半 SOX</div>
          <div style="font-family:monospace;font-size:20px;font-weight:700;color:#E87A6E;">{fmt_num(sox_price,0) if sox_price else "14,342"}</div>
          <div style="font-family:monospace;font-size:10px;color:#6B7280;">{chg_str("SOX",0) if sox_price else "6/18收盤"}</div>
        </div>
        <div style="flex:1;background:#0C0F16;border:1px solid #1C2030;border-radius:5px;padding:10px;text-align:center;">
          <div style="font-family:monospace;font-size:9px;color:#6B7280;letter-spacing:1px;margin-bottom:4px;">USD/TWD 匯率</div>
          <div style="font-family:monospace;font-size:20px;font-weight:700;color:#DEDCd6;">{fx:.2f}</div>
          <div style="font-family:monospace;font-size:10px;color:#6B7280;">即時匯率</div>
        </div>
        <div style="flex:1;background:#0C0F16;border:1px solid rgba(201,168,85,0.3);border-radius:5px;padding:10px;text-align:center;">
          <div style="font-family:monospace;font-size:9px;color:#6B7280;letter-spacing:1px;margin-bottom:4px;">群創 3481（對照）</div>
          <div style="font-family:monospace;font-size:20px;font-weight:700;color:#6B7280;">{fmt_num(innolux,0) if innolux else "66"}</div>
          <div style="font-family:monospace;font-size:10px;color:#6B7280;">L17 封測生態圈追蹤</div>
        </div>
      </div>
      <div style="font-family:monospace;font-size:10px;color:#6B7280;background:#0C0F16;border:1px solid #1C2030;border-radius:5px;padding:8px 12px;">
        ⚠️ 群創(3481) 為L17 TSMC+Amkor封測協議對照觀察標的，非持倉。 &nbsp;|&nbsp; 台指期正常交易日請確認正/逆價差方向。
      </div>
    </div>
  </div>

  <!-- ══ 區塊三：底層邏輯 ══ -->
  <div style="background:#111520;border-left:4px solid #8A6FC9;padding:0;border-top:1px solid #1C2030;">
    <div style="background:linear-gradient(90deg,rgba(138,111,201,0.2) 0%,transparent 60%);padding:10px 18px;border-bottom:1px solid #1C2030;">
      <span style="font-family:monospace;font-size:11px;color:#8A6FC9;letter-spacing:2px;font-weight:700;">03</span>
      <span style="font-size:17px;font-weight:900;color:#B09AE0;margin-left:10px;">底層邏輯 · L編號動態 · EPS估值引擎</span>
      <span style="font-family:monospace;font-size:10px;color:#6B7280;margin-left:12px;">Underlying Logic · L-Triggers · Valuation Engine</span>
    </div>
    <div style="padding:12px 18px;">
      <!-- Z-score -->
      <div style="background:#0C0F16;border:1px solid #1C2030;border-radius:5px;padding:12px 16px;display:flex;gap:16px;align-items:center;margin-bottom:10px;">
        <div>
          <div style="font-family:monospace;font-size:9px;color:#6B7280;letter-spacing:1.5px;margin-bottom:2px;">EPS估值引擎 · 2330台積電</div>
          <div style="font-family:monospace;font-size:36px;font-weight:700;color:#3FB97A;line-height:1;">{E:+.3f}</div>
          <div style="font-family:monospace;font-size:9px;color:#6B7280;">(現價{tsm_price}÷EPS{params['eps_base']} − {params['pe_mean']}) ÷ {params['pe_std']}</div>
        </div>
        <div style="font-family:monospace;font-size:11px;background:#3FB97A;color:#0A0D13;padding:4px 12px;border-radius:3px;font-weight:700;flex-shrink:0;">
          {"極便宜 → 強持有" if E < -1.5 else "便宜 → 持有" if E < 0 else "合理 → 準備停利思維" if E < 1.5 else "偏貴 → 評估減碼"}
        </div>
        <div style="font-family:monospace;font-size:10px;color:#6B7280;flex:1;line-height:2;">
          短線目標 <span style="color:#DEDCd6;">{params['target_short_2330']:,}</span> (Z={((params['target_short_2330']/params['eps_base']-params['pe_mean'])/params['pe_std']):+.3f})<br>
          長線目標 <span style="color:#DEDCd6;">{params['target_long_2330']:,}</span> (Z={((params['target_long_2330']/params['eps_base']-params['pe_mean'])/params['pe_std']):+.3f})<br>
          警戒減碼 <span style="color:#DEDCd6;">3,750</span> (Z=+1.500)
        </div>
        <div style="font-family:monospace;font-size:9px;color:#6B7280;text-align:right;line-height:1.8;">
          EPS 140元鎖定<br>至 07/16 法說<br>───<br>若EPS上修150<br>→ 短線 3,000<br>→ 長線 3,375
        </div>
      </div>

      <!-- L Cards -->
      {''.join([f"""
      <div style="background:#0C0F16;border:1px solid #242A36;border-radius:5px;padding:9px 12px;margin-bottom:8px;">
        <div style="margin-bottom:4px;">
          <span style="font-family:monospace;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;background:rgba(138,111,201,0.15);border:1px solid rgba(138,111,201,0.4);color:#B09AE0;margin-right:8px;">{tag}</span>
          <span style="font-size:11px;color:#DEDCd6;">{title}</span>
        </div>
        <div style="font-size:10px;color:#6B7280;border-left:2px solid #242A36;padding-left:8px;line-height:1.7;">{chain}</div>
      </div>""" for tag, title, chain in [
        ("L11", "2383 台光電 ←→ PCB/CCL材料鏈",
         "AI伺服器需求↑ → CCL/玻纖布材料緊俏 → 南亞/楠梓電為先行信號 → 台光電ABF載板需求強化 → 目標7,000，浮盈47%~65%停利區"),
        ("L1~L4", "2330 台積電 ←→ AI晶片代工定價權",
         "費半SOX領先指標 → TSM ADR先行反映 → 台積電定價護城河 → EPS 140元基準持續有效至07/16法說"),
        ("L17 ★新增", "TSMC + Amkor 10年封測協議（6/18）",
         "TSMC與Amkor簽訂10年封測長期合作 → CoWoS/SoIC先進封裝產能確定性↑ → 供應鏈整合深化 → 對照標的：群創(3481)追蹤封測生態圈擴散效應"),
      ]])}
    </div>
  </div>

  <!-- ══ 區塊四：待確認 ══ -->
  <div style="background:#131015;border-left:4px solid #C9855A;padding:0;border-top:1px solid #1C2030;">
    <div style="background:linear-gradient(90deg,rgba(201,133,90,0.2) 0%,transparent 60%);padding:10px 18px;border-bottom:1px solid #1C2030;">
      <span style="font-family:monospace;font-size:11px;color:#C9855A;letter-spacing:2px;font-weight:700;">04</span>
      <span style="font-size:17px;font-weight:900;color:#D9A07A;margin-left:10px;">待確認事項 · 下次對話優先處理</span>
      <span style="font-family:monospace;font-size:10px;color:#6B7280;margin-left:12px;">Pending Actions · Next Session Priority</span>
    </div>
    <div style="padding:12px 18px;">
      <div style="background:#1A1508;border:1px solid rgba(201,168,85,0.35);border-radius:5px;padding:10px 14px;">
        <div style="font-family:monospace;font-size:9px;color:#7A6230;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:8px;">⚠️ Pending Confirmation</div>
        <div style="font-family:monospace;font-size:10px;color:#8B9498;line-height:2.0;">
          <span style="color:#C9A855;">1.</span> 07/16 台積電Q2法說 → EPS確認方向：維持140元（短線{params['target_short_2330']:,}/長線{params['target_long_2330']:,}）或上修150元（短線3,000/長線3,375）<br>
          <span style="color:#C9A855;">2.</span> 群創(3481) L17追蹤 → 確認是否納入分析對照標的，觀察封測生態圈擴散<br>
          <span style="color:#C9A855;">3.</span> 2383目標{params['target_2383']:,}動態 → 達標即停利65股 → 解鎖B(→19%) + D(→1.47) 雙紅轉綠<br>
          <span style="color:#C9A855;">4.</span> 邊界B={B:.1%} 距門檻15%差距 {(0.15-B):.1%}，優先關注持倉停利解鎖路徑
        </div>
      </div>
    </div>
  </div>

  <!-- FOOTER -->
  <div style="background:#0F1319;border-top:1px solid #1C2030;padding:10px 24px;display:flex;justify-content:space-between;font-family:monospace;font-size:9px;color:#6B7280;letter-spacing:1px;">
    <div>MUSE v3.0 · Daily Edition | FILES v2.7 | L17新增 | 群創3481對照加入</div>
    <div>Generated: {NOW_TW.strftime("%Y-%m-%d %H:%M")} TWD | NAV {fmt_num(total_nav)} TWD</div>
  </div>

</div>
</body>
</html>"""


# ─────────────────────────────────────────────
#  Send Email
# ─────────────────────────────────────────────
GMAIL_PASS = os.environ.get("GMAIL_APP_PASSWORD")
if not GMAIL_PASS:
    print("[ERROR] 缺少環境變數 GMAIL_APP_PASSWORD，請在 GitHub Secrets 設定")
    raise SystemExit(1)

to_addr   = email_cfg["to"]
from_addr = email_cfg["from"]

b_icon = "🔴" if not B_ok else "🟢"
c_icon = "🟡" if C > 0.70 else "🟢"
d_icon = "🔴" if not D_ok else "🟢"
subject = (
    f"MUSE日報 {DATE_STR} | NAV {fmt_num(total_nav)} | "
    f"B={B:.1%}{b_icon} C={C:.1%}{c_icon} D={D:.2f}{d_icon}"
)

msg = MIMEMultipart("alternative")
msg["Subject"] = subject
msg["From"]    = from_addr
msg["To"]      = to_addr
msg.attach(MIMEText(EMAIL_HTML, "html", "utf-8"))

print(f"[INFO] 發送至 {to_addr}…")
with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
    smtp.login(from_addr, GMAIL_PASS)
    smtp.sendmail(from_addr, to_addr, msg.as_string())

print(f"[OK] MUSE日報已發送 | {DATE_STR} | NAV {fmt_num(total_nav)}")
