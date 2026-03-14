# 📊 台灣股市 AI 精選情報 (Taiwan Stock AI Daily)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![OpenAI](https://img.shields.io/badge/AI-GPT--3.5-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Automation](https://img.shields.io/badge/workflow-GitHub%20Actions-orange.svg)

> **這是一個完全自動化的財經情報系統。透過 AI 助理，每 6 小時自動彙整全台重大財經新聞與台股即時數據，並生成動態網頁。**

## 🌐 專案成果預覽
* **即時報表網址**：[👉 點此查看我的 AI 財經報紙](https://gordonchen0816.github.io/taiwan-stock-daily/)
* **核心理念**：利用 AI 解決資訊過載，從海量新聞中過濾出真正的焦點交集。

---

## 🛠️ 技術架構 (SOP)

本專案由三大部分組成，實現了從數據抓取到網頁發布的全自動流水線：

### 1. 數據獲取 (Data Acquisition)
* **新聞池**：利用 `Requests` 與 `BeautifulSoup4` 爬取 Google News RSS，獲取包含工商時報、經濟日報、Yahoo 財經等超過 40 則即時頭條。
* **股市數據**：使用 `yfinance` 介接 Yahoo Finance API，獲取加權指數、台積電 (2330)、鴻海 (2317) 的即時漲跌幅與點數。

### 2. AI 核心分析 (AI Engine)
* **模型**：使用 OpenAI `gpt-3.5-turbo`。
* **任務**：AI 扮演「專業財經主編」，對混合新聞池進行分類、交叉比對，找出三大媒體共同關注的「焦點交集」，並給予專業的操作建議。

### 3. 自動化部署 (CI/CD)
* **環境**：基於 GitHub Actions 的雲端虛擬機。
* **排程**：設定 `Cron Job` 每 6 小時自動觸發一次（台灣時間 02:00, 08:00, 14:00, 20:00）。
* **輸出**：使用 `markdown` 套件將分析結果轉為 HTML，並透過 GitHub Pages 託管網頁。

---

## 🧑‍💻 如何解釋這個專案 (口語版)

1. **自動讀報**：程式每 6 小時會像實習生一樣，幫我把各大報紙的財經頭條全部抓回來。
2. **AI 主編**：AI 會閱讀這幾十則新聞，並告訴我「哪三件事是所有媒體都在關注的」，這就是所謂的『焦點交集』。
3. **動態發布**：分析完後，它會自己寫成 HTML 代碼，並推送到雲端，讓所有人透過一個網址就能看到即時更新的報紙。

---

## 🚀 如何使用本專案

如果你想打造屬於自己的 AI 報紙：
1. **Fork** 本專案。
2. 在 GitHub 設定中加入 `OPENAI_API_KEY` 的 **Secret**。
3. 開啟 **GitHub Pages** 功能。
4. 手動執行一次 **Actions**，你的專案就開始 24 小時運轉了！

---
*本專案僅供學術研究與個人參考，投資請謹慎評估風險。*
