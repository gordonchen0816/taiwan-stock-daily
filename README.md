# 📊 台股每日彙整

每天自動抓取台灣股市數據，用 GPT-4o-mini 產生繁體中文彙整報告，透過 GitHub Pages 展示。

## 功能

- 📈 大盤指數（加權、櫃買）
- 🏦 三大法人買賣超（外資、投信、自營）
- 🔍 個股技術指標（RSI、SMA7/20）
- 📰 多來源財經新聞（工商、經濟日報、MoneyDJ、鉅亨）
- 🤖 GPT-4o-mini 繁體中文條列式彙整報告
- 🕖 每個交易日 07:30 自動執行（GitHub Actions）

## 快速開始

### 步驟一：Fork / Clone 這個 Repo

```bash
git clone https://github.com/你的帳號/taiwan-stock-daily.git
cd taiwan-stock-daily
```

### 步驟二：取得 OpenAI API Key

1. 前往 https://platform.openai.com/
2. 登入 → 右上角頭像 → **API Keys**
3. 點「Create new secret key」
4. 複製產生的 Key（格式：`sk-...`）

### 步驟三：設定 GitHub Secrets

1. 進入你的 Repo → **Settings** → **Secrets and variables** → **Actions**
2. 點「New repository secret」
3. Name：`OPENAI_API_KEY`，Value：貼上你的 Key
4. 儲存

### 步驟四：啟用 GitHub Pages

1. Repo → **Settings** → **Pages**
2. Source 選「Deploy from a branch」
3. Branch 選 `main`，資料夾選 `/docs`
4. 儲存後等 1-2 分鐘，網址會出現在頁面上

### 步驟五：手動觸發測試

1. Repo → **Actions** → **Taiwan Stock Daily Digest**
2. 點「Run workflow」→「Run workflow」
3. 等待執行完成，重新整理你的 GitHub Pages 網址

## 自訂個股清單

編輯 `scripts/fetch_market.py` 第 18 行：

```python
WATCH_LIST = ["2330", "2317", "2454", "2412", "2881"]
#              台積電   鴻海    聯發科   中華電   富邦金
```

## 本機測試

```bash
pip install -r requirements.txt
export OPENAI_API_KEY="sk-你的key"
python scripts/main.py
```

## 專案結構

```
├── scripts/
│   ├── main.py             # 主程式（串接所有模組）
│   ├── fetch_news.py       # 新聞 RSS 爬蟲
│   ├── fetch_market.py     # 大盤、個股、法人數據
│   ├── generate_report.py  # GPT 報告產生器
│   └── cleanup.py          # 清理舊資料
├── data/                   # 每日 JSON（自動產生）
├── docs/
│   ├── index.html          # GitHub Pages 前端
│   ├── latest.json         # 最新一天資料
│   └── index_list.json     # 日期索引（翻頁用）
└── .github/workflows/
    └── daily.yml           # GitHub Actions 排程
```

## 資料來源

- 大盤指數：[TWSE 官方 API](https://www.twse.com.tw/)（免費）
- 法人買賣超：[TWSE T86](https://www.twse.com.tw/fund/T86)（免費）
- 新聞：工商時報、經濟日報、MoneyDJ、鉅亨網（RSS）
- AI 報告：OpenAI GPT-4o-mini
