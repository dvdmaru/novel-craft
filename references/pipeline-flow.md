# Pipeline 流程詳細定義

## 完整管線狀態機

```
[INIT] → [ARCHITECT] → [WRITER] → [AUDITOR] → ─┬─ passed → [PUBLISH]
                                                  │
                                                  └─ failed → [REVISER] → [RE-AUDIT] → ─┬─ passed → [PUBLISH]
                                                                                          │
                                                                                          └─ failed → [NEEDS-REVIEW]
```

## 各階段詳細定義

### 1. ARCHITECT 階段

**輸入**：
- story-bible.md
- volume-outline.md
- book-rules.md
- 最近 2 章的 chapter-summaries

**輸出**：
- 目標章節的詳細大綱（200-300 字）
- 本章衝突定義
- 預期伏筆操作（新增/推進/回收）
- 建議的章節類型

**Architect Prompt 核心要點**：
- 遵循黃金三章法則：前 3 章必須建立衝突、展示主角魅力、給出明確目標
- 節奏控制：依題材規則的節奏要求安排章節類型（如玄幻：三章內必有反饋）
- 伏筆管理：每 5 章至少回收 1 個伏筆，每 3 章至少推進 1 個伏筆
- 爽點分配：依題材的 satisfactionTypes 均勻分布

### 2. WRITER 階段

**輸入**（WriteChapterInput）：
- 所有 state/ 文件（7 份真相文件）
- 最近 2-3 章正文
- story-bible.md + volume-outline.md + book-rules.md
- Architect 的章節大綱
- 題材規則（genre-*.md）
- 寫作規則（writer-rules.md）
- 風格指紋（如有）

**執行流程**：
1. 載入上下文
2. 執行 PRE_WRITE_CHECK（六步走人物心理分析）
3. 撰寫正文
4. 執行 POST_SETTLEMENT（數值結算）
5. 更新所有真相文件

**輸出**（WriteChapterOutput）：
- 正文
- 更新的 7 份真相文件
- PRE_WRITE_CHECK + POST_SETTLEMENT

**關鍵限制**：
- 嚴格遵守 writer-rules.md 中的所有鐵律
- 正文中禁止出現 hook_id、賬本式數據
- 六步走術語僅限 PRE_WRITE_CHECK 內部使用
- 每段至少帶來一項新信息、態度變化或利益變化

### 3. AUDITOR 階段

**輸入**：
- 章節正文
- 所有 state/ 文件
- audit-dimensions.md
- anti-ai-rules.md
- 題材規則

**執行流程**：
1. 根據題材的 auditDimensions 確定啟用的維度
2. 條件維度啟用檢查：
   - 維度 4（戰力崩壞）：僅當 powerScaling=true
   - 維度 5（數值檢查）：僅當 numericalSystem=true
   - 維度 12（年代考據）：僅當 eraResearch=true
3. 先執行規則引擎維度（20-23）：
   - 維度 20：計算各段落字數的變異係數（CV = σ/μ），CV < 0.15 → warning
   - 維度 21：統計套話詞出現次數 / (總字數/1000)，> 3 → warning
   - 維度 22：統計每個轉折詞的出現次數，同詞 ≥ 3 → warning
   - 維度 23：檢測連續句子前 2 字是否相同，≥ 3 句 → info
4. 再執行 LLM 審計維度（1-19, 24-26）
5. 合併結果，生成審計報告

**輸出**（AuditResult）：
- passed: boolean（無 critical 問題即為 true）
- issues: 問題清單（每項含 severity/category/description/suggestion）
- summary: 一段式總結

**嚴重度分級**：
- **critical**：必須修復才能發布（OOC、設定衝突、戰力崩壞、信息越界）
- **warning**：建議修復（詞彙疲勞、節奏問題、AI 痕跡）
- **info**：提醒注意（列表式結構、輕微重複）

### 4. REVISER 階段

**輸入**（ReviseInput）：
- 章節正文
- 審計 issues 清單
- 所有 state/ 文件
- 修訂模式

**四種修訂模式**：

| 模式 | 適用場景 | 修改範圍 |
|------|---------|---------|
| polish | 僅有 warning/info | 字句微調，不改結構 |
| rewrite | 有 critical 但 < 3 個 | 重寫問題段落，保持框架 |
| rework | 有 critical 且 ≥ 3 個 | 全章重構，可調情節 |
| anti-detect | AI 痕跡問題為主 | 深度重組句式和節奏 |

**輸出**（ReviseOutput）：
- revisedContent：修訂後的正文
- fixedIssues：逐條說明每個 issue 如何修正
- 更新的 state/ 文件（如果修訂改變了情節）

### 5. PUBLISH 階段

1. 最終版本寫入 `chapters/ch{NNN}.md`
2. 更新所有 state/ 文件
3. 在 `snapshots/ch{NNN}/` 建立快照（包含所有 7 份真相文件的副本）
4. 向用戶展示摘要

## 品質門（Quality Gates）

| 設定 | 預設值 | 說明 |
|------|--------|------|
| maxAuditRetries | 2 | 最多審計重試次數 |
| pauseAfterConsecutiveFailures | 3 | 連續失敗多少次後暫停管線 |
| retryTemperatureStep | 0.1 | 每次重試時創造性微增 |

## 真相文件更新規則

| 文件 | 更新方式 | 說明 |
|------|---------|------|
| current-state.md | 完全覆蓋 | 新章節寫入後以新狀態覆蓋 |
| particle-ledger.md | 完全覆蓋 | 包含所有章節的賬本記錄 |
| pending-hooks.md | 完全覆蓋 | 更新伏筆狀態（open/progressing/resolved） |
| chapter-summaries.md | 追加 | 在末尾追加新章節摘要行 |
| subplot-board.md | 完全覆蓋 | 更新所有支線進度 |
| emotional-arcs.md | 完全覆蓋 | 更新所有角色情緒軌跡 |
| character-matrix.md | 完全覆蓋 | 更新角色關係和信息邊界 |

## 快照與回滾

每章完成後自動建立快照：
```
snapshots/ch{NNN}/
├── current-state.md
├── particle-ledger.md
├── pending-hooks.md
├── chapter-summaries.md
├── subplot-board.md
├── emotional-arcs.md
└── character-matrix.md
```

回滾操作：
1. 讀取目標章節的快照
2. 用快照覆蓋 state/ 下所有文件
3. 刪除回滾點之後的章節文件
4. 更新章節索引
