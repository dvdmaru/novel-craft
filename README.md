# Novel Craft

多 Agent 協作小說寫作系統，靈感來自 InkOS。透過 5 個 Agent 角色（雷達 / 建築師 / 寫手 / 審計員 / 修訂者）協作完成長篇小說創作。

支援題材：玄幻、仙俠、都市、恐怖。內建 7 份真相文件長期記憶、26 維度連續性審計、去 AI 味機制。

## 安裝

打包為 Cowork Skill。將整個目錄放到 Cowork Skills 目錄即可：

```
{cowork-skills-dir}/novel-craft/
├── SKILL.md             # Skill 主檔（含描述 / 流程 / 觸發詞）
├── references/          # 參考文件（規則 / 維度 / 題材）
├── scripts/             # 審計腳本（Python + shell）
└── assets/templates/    # 範本（story-bible / book-rules）
```

## 主要結構

- **SKILL.md** — 系統主檔，含 5 Agent 角色定義 / 完整工作流 / 觸發詞清單
- **references/**
  - `writer-rules.md` / `anti-ai-rules.md` — 寫手規則 + 去 AI 味
  - `audit-dimensions.md` — 26 維度連續性審計清單
  - `genre-{xuanhuan,xianxia,urban,horror}.md` — 4 題材專屬規則
  - `state-schemas.md` — 真相文件 schema
  - `pipeline-flow.md` — 5 Agent 協作 pipeline
- **scripts/**
  - `audit_rules.py` — 規則層審計
  - `audit_consistency.py` — 連續性審計
  - `verify_state.sh` — 真相文件狀態驗證
- **assets/templates/**
  - `story-bible-template.md` — 真相文件範本
  - `book-rules-template.md` — 書設定規則範本

## 觸發

當使用者提到「寫小說」「創作小說」「續寫章節」「小說寫作」「novel writing」「write a novel」「story writing」「寫故事」「創建新書」「審計章節」「修訂章節」「novel-craft」時觸發。

## License

MIT.
