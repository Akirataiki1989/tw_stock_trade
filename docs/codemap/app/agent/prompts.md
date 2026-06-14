# app/agent/prompts.py

## 用途

儲存 LangGraph Agent 中各個角色的提示詞模板。

## 提示詞列表

| 常數名 | 用途 | 特色 |
|------|------|------|
| `TECHNICAL_ANALYST` | 負責技術指標分析 | 關注均線、RSI、MACD 與 K 線型態。 |
| `SENTIMENT_ANALYST` | 負責市場情緒與籌碼 | 分析三大法人買賣超、融資融券與新聞情緒。 |
| `RISK_ANALYST` | 負責風險控制 | 評估大盤環境 (US Market) 與最大回撤風險。 |
| `BULL_RESEARCHER` | 辯論中的多方代表 | 尋找看多理由，針對分析師報告進行辯護。 |
| `BEAR_RESEARCHER` | 辯論中的空方代表 | 尋找看空理由，挑戰分析師的樂觀預期。 |
| `RESEARCH_MANAGER` | 決策仲裁與彙整 | 綜合辯論結果與分析師意見，給出最終執行建議。 |
