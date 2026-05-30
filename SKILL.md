---
name: novel-craft
description: 長篇小說（網文：玄幻／仙俠／都市／恐怖等）的寫→審→改協作管線，含跨章狀態記憶與連續性審計。用於開新書、規劃大綱、撰寫或續寫章節、審計或修訂既有章節、查看書籍狀態與回滾；在小說專案目錄中即使只說「繼續寫」「下一章」「審一下」也應觸發。
---

# Novel Craft — 多 Agent 協作小說寫作系統

## 【重要】文件路徑說明

本 Skill 的所有參考文件、腳本、範本都位於 **SKILL.md 同級目錄下**，而非用戶的小說專案目錄。

當 Cowork 載入此 Skill 時，會顯示形如：
```
Base directory for this skill: /sessions/.../skills/novel-craft
```

**必須用這個路徑（以下稱 `{SKILL_DIR}`）來定位所有內部資源**：
- 參考文件：`{SKILL_DIR}/references/writer-rules.md` 等
- 審計腳本：`{SKILL_DIR}/scripts/audit_rules.py`
- 範本：`{SKILL_DIR}/assets/templates/`

**不要在小說專案目錄下尋找 references/ 或 scripts/**——它們只存在於 Skill 安裝目錄中。

小說專案目錄（用戶選定或在工作目錄下創建的，如 `藏鋒/`）只包含：
- `story-bible.md`、`volume-outline.md`、`book-rules.md`
- `state/`（7 份真相文件）
- `chapters/`（章節正文）
- `snapshots/`（快照）

## 系統概述

Novel Craft 是一套以 **寫→審→改** 閉環為核心的長篇小說 AI 協作工具。在 Cowork 環境中，Claude 自身就是 LLM 引擎——不需要外部 API——透過角色切換模擬五個專職 Agent 的協作。

核心創新：
- **7 份真相文件**追蹤世界狀態，解決 LLM 上下文窗口不足導致的角色失憶、設定崩壞問題
- **27 維度連續性審計**，其中 4 個維度為純規則引擎（不額外消耗 Token），維度 27（地理真實性）為真實世界地理題材的條件維度
- **去 AI 味鐵律**，用標記詞限頻等硬規則壓制 LLM 的典型文風
- **題材規則三層分離**（通用 → 題材 → 單本書），高度可配置

支援語言：繁體中文、簡體中文、英文。

## 命令一覽

| 命令 | 功能 | 主導 Agent |
|------|------|-----------|
| `create` | 創建新書專案 | Architect |
| `outline` | 生成/更新大綱 | Architect |
| `write` | 寫下一章（完整管線） | Writer → Auditor → Reviser |
| `draft` | 僅寫初稿（不審計） | Writer |
| `audit [章節] [--debate]` | 審計指定章節（`--debate` 強制觸發對立辯論） | Auditor |
| `revise [章節] [模式]` | 修訂章節 | Reviser |
| `status` | 查看書籍狀態 | Radar |
| `rewind [章節]` | 回滾到指定章節快照 | — |
| `archive` | 卷結束時歸檔壓縮 state 文件 | Radar |

## 執行指令

### CREATE：創建新書

1. 詢問用戶：書名、題材（xuanhuan/xianxia/urban/horror/other，支援混合如 `urban+horror`）、目標語言（繁中/簡中/英文）、主角設定、核心衝突概念
2. 讀取對應題材規則：`{SKILL_DIR}/references/genre-{題材}.md`（混合題材則逐一讀取多份，如 genre-urban.md + genre-horror.md）
3. 讀取狀態文件格式：`{SKILL_DIR}/references/state-schemas.md`
4. 在工作目錄中建立以下結構：

```
{book-name}/
├── story-bible.md          # 世界觀聖經（由 Architect 生成）
├── volume-outline.md       # 卷綱
├── book-rules.md           # 本書規則
├── state/
│   ├── current-state.md    # 當前狀態卡
│   ├── particle-ledger.md  # 資源賬本
│   ├── pending-hooks.md    # 伏筆池
│   ├── chapter-summaries.md
│   ├── subplot-board.md
│   ├── emotional-arcs.md
│   └── character-matrix.md
├── chapters/
└── snapshots/
```

5. 切換為 **Architect Agent**，生成：
   - story-bible.md：世界觀、勢力、地理、魔法/科技體系
   - volume-outline.md：卷綱（黃金三章法則——前3章必須建立衝突、展示主角魅力、給出明確目標）
   - book-rules.md：主角人設鎖（personalityLock）、行為約束、數值上限、禁忌清單
   - 初始化所有 state/ 文件（按 state-schemas.md 的格式）
6. 向用戶確認設定，允許修改後定稿

### WRITE：寫下一章（完整管線）

這是核心操作，執行順序如下：

**Step 0 — 載入階段（每章必做，不可省略）**
每次寫新章節前，必須重新讀取以下文件到上下文中。這是跨章記憶的核心——Context window 不會保留前幾章的細節，所以必須每次重新載入。

必須使用 Read 工具依序讀取。注意區分兩個目錄：
- **小說目錄**（用戶的專案目錄，如 `藏鋒/`）：book-rules、outline、state、chapters
- **Skill 目錄**（`{SKILL_DIR}`，即本 SKILL.md 所在的目錄）：references、scripts

從**小說目錄**讀取：
1. `book-rules.md`（確認字數目標、人設鎖、禁忌）
2. `volume-outline.md`（確認本章大綱）
3. `state/current-state.md`（角色當前狀態）
4. `state/particle-ledger.md`（資源賬本）
5. `state/pending-hooks.md`（伏筆池）
6. `state/chapter-summaries.md`（前章摘要）
7. `state/subplot-board.md`（支線進度）
8. `state/emotional-arcs.md`（情感弧線）
9. `state/character-matrix.md`（角色關係與信息邊界）
10. 最近 2 章正文（`chapters/ch{N-1}.md` 和 `chapters/ch{N-2}.md`）

從**Skill 目錄**讀取：
11. `{SKILL_DIR}/references/writer-rules.md`（寫作規則）
12. `{SKILL_DIR}/references/genre-{題材}.md`（題材規則，混合題材則逐一讀取，如 genre-urban.md + genre-horror.md）

如果任何 state 文件不存在或為空，必須先告知用戶並初始化。

**Step 1 — 寫前準備**
- 從 book-rules.md 讀取目標字數（預設 4000-6000）
- 確認本章類型（從 volume-outline 或上一章結尾推斷）
- 確認待回收的伏筆（從 pending-hooks.md）
- 確認角色信息邊界（從 character-matrix.md，防止信息越界）

**Step 1b — 場景字數預分配（提高首稿字數命中率的關鍵步驟）**
根據大綱和本章類型，將目標字數拆解分配到每個場景段落。此步驟在 PRE_WRITE_CHECK 表格之後、正文之前輸出，格式如下：

```
=== WORD_BUDGET ===
目標總字數：{N} 字

| # | 場景/段落 | 類型 | 預估字數 | 佔比 |
|---|----------|------|---------|------|
| 1 | 開場（承接上章結尾） | 過渡 | 400 | 8% |
| 2 | 場景A：XXX | 對話+動作 | 1200 | 25% |
| 3 | 場景B：XXX | 心理+環境 | 800 | 17% |
| 4 | 場景C：XXX | 衝突/高潮 | 1500 | 31% |
| 5 | 收尾（伏筆+懸念） | 過渡 | 900 | 19% |
| 合計 | | | 4800 | 100% |

注意：合計必須 ≥ 目標字數，建議預分配為目標的 105-110% 作為緩衝。
```

寫作過程中對照此分配表，確保每個場景段落接近預估字數。若某段寫完明顯不足，當場擴充而非留到事後補。

**Step 2 — Writer Agent 寫初稿（分步模式）**

寫作管線採用**明確分步模式**，每一步聚焦一件事，避免單次輸出過長導致截斷或品質下降。

**Step 2a — 寫前檢查（輸出 PRE_WRITE_CHECK + WORD_BUDGET）**
- 讀取完整寫作規則：`{SKILL_DIR}/references/writer-rules.md`
- 執行六步走人物心理分析
- 輸出以下內容後暫停，等用戶確認再繼續：

```
=== PRE_WRITE_CHECK ===
| 檢查項 | 本章記錄 | 備註 |
|--------|----------|------|
| 上下文範圍 | 第X章至第Y章 / 狀態卡 / 設定文件 | |
| 當前錨點 | 地點 / 對手 / 收益目標 | 錨點必須具體 |
| 當前資源總量 | X | 與賬本一致 |
| 本章預計增量 | +X（來源） | 無增量寫 +0 |
| 待回收伏筆 | Hook-A / Hook-B | 與伏筆池一致 |
| 本章衝突 | 一句話概括 | |
| 章節類型 | [類型] | |
| 風險掃描 | OOC/信息越界/設定衝突/戰力崩壞/節奏/詞彙疲勞/視角一致性 | |

=== WORD_BUDGET ===
（場景字數預分配表，見 Step 1b 的格式。合計必須 ≥ 目標字數的 105%。）
```

用戶確認（或說「繼續」「ok」）後，進入 Step 2b。

**Step 2b — 撰寫正文（輸出 CHAPTER_CONTENT + OOC_SELF_CHECK）**

**【字數硬性要求 — 不可違反】**
正文字數必須達到 book-rules.md 中設定的目標（預設 4000-6000 字）。這是硬性下限，不是建議值。

**【逐段計數機制 — 防止 LLM 自然收束導致字數不足】**
不要等全章寫完才計數。每完成一個場景段落後：
1. 將已寫內容存入 `chapters/ch{NNN}.md`（首段用 Write，後續段落用追加）
2. 用 `wc -m chapters/ch{NNN}.md` 計算已寫字數
3. 與 WORD_BUDGET 的累計預估字數對照
4. 若落後超過 15%，**當場擴充該段落**（加對話、加五感描寫、加心理活動），不要「之後再補」
5. 確認追上進度後再寫下一段

這是對抗 LLM 天然偏短傾向的核心機制。如果跳過逐段計數，幾乎必然需要二次擴充。

輸出格式：
```
=== CHAPTER_TITLE ===
（章節標題，不含「第X章」前綴）

=== CHAPTER_CONTENT ===
（正文。逐段寫作、逐段計數，不要等全章寫完才檢查字數。）
```

全章寫完後，最終確認：
```bash
wc -m chapters/ch{NNN}.md
```
若仍不達標則補充後重新存檔。

**Step 2c — OOC 自檢 + 結算（輸出 OOC_SELF_CHECK + POST_SETTLEMENT）**

正文確認達標後，執行 OOC 自檢和資源結算：
```
=== OOC_SELF_CHECK ===
| 檢查項 | 通過? | 違規描述（若有） |
|--------|-------|-----------------|
| 主角行為是否符合 book-rules.md 的 personalityLock？ | ✅/❌ | |
| 主角是否暴露了超出 character-matrix.md 信息邊界的知識？ | ✅/❌ | |
| 配角是否為推動主角而降智（明顯不合理的決策）？ | ✅/❌ | |
| 沉默型角色是否在非必要情況下主動暴露實力/秘密？ | ✅/❌ | |
| 反派是否因劇情需要而放棄最優策略（戰力崩壞）？ | ✅/❌ | |
| 角色對話語氣是否符合其身份和當前情緒？ | ✅/❌ | |
| 是否有角色突然獲得未交代來源的能力/物品/信息？ | ✅/❌ | |

若有任何 ❌，必須先修正正文再繼續。

=== POST_SETTLEMENT ===
| 結算項 | 本章記錄 | 備註 |
|--------|----------|------|
| 資源賬本 | 期初X / 增量+Y / 期末Z | 無增量寫 +0 |
| 重要資源 | 資源名 -> 貢獻+Y（依據） | 無寫「無」 |
| 伏筆變動 | 新增/回收/延後 Hook | 同步更新伏筆池 |
```

**Step 2d — 更新 State 文件（分層頻率，減少 Tool Call 消耗）**

7 份 state 文件分為兩層，按不同頻率更新：

**每章必更新（3 份，核心狀態）**：
- `state/current-state.md`（完全覆蓋）
- `state/chapter-summaries.md`（追加本章摘要到末尾）
- `state/pending-hooks.md`（完全覆蓋，僅含已埋伏筆）

**每 3 章更新一次（4 份，輔助狀態）**：
- `state/particle-ledger.md`（完全覆蓋）
- `state/subplot-board.md`（完全覆蓋）
- `state/emotional-arcs.md`（完全覆蓋）
- `state/character-matrix.md`（完全覆蓋）

判斷規則：如果當前章節號能被 3 整除（ch003、ch006、ch009...），或本章有重大事件（角色死亡、新角色登場、支線轉折、資源重大變動），則更新全部 7 份。否則只更新 3 份核心。

不要在對話中輸出完整的 UPDATED_* 區塊，直接用 Write/Edit 工具寫入檔案。每個文件寫入後簡短確認（如「✓ current-state.md 已更新」）。

**Step 3 — 驗證與快照**

3a. **狀態更新完整性驗證（不可省略）**：
更新完所有 state 文件後，必須執行以下驗證。這是為了防止 LLM 敷衍輸出或遺漏區塊（實測中 character-matrix.md 在第 5 章後停止正確更新）。

驗證方式：執行自動化驗證腳本：
```bash
bash {SKILL_DIR}/scripts/verify_state.sh snapshots/ch{上一章號}
```
如果 Skill 腳本不可用，也可手動逐一檢查 7 份 state 文件的修改時間和行數。

驗證規則：
- 如果本章應更新的 state 文件（見 Step 2d）修改時間不是本次寫作期間，代表漏更新 → 回頭用 Write/Edit 重新寫入該文件
- **character-matrix.md 特別檢查**：行數必須 ≥ 上一章快照的行數（角色關係只增不減，除非有角色死亡）。如果行數反而減少，代表更新時遺漏了角色 → 必須修正
- **pending-hooks.md 特別檢查**：如果本章有「回收伏筆」但文件中對應 Hook 狀態未變 → 必須修正

3b. **建立快照（必須執行）**：
```bash
mkdir -p snapshots/ch{NNN}
cp state/current-state.md snapshots/ch{NNN}/
cp state/particle-ledger.md snapshots/ch{NNN}/
cp state/pending-hooks.md snapshots/ch{NNN}/
cp state/chapter-summaries.md snapshots/ch{NNN}/
cp state/subplot-board.md snapshots/ch{NNN}/
cp state/emotional-arcs.md snapshots/ch{NNN}/
cp state/character-matrix.md snapshots/ch{NNN}/
```

**Step 4 — 規則引擎審計（Python 腳本）**

先執行確定性的規則引擎檢查（不消耗 LLM Token）：
```bash
python3 {SKILL_DIR}/scripts/audit_rules.py chapters/ch{NNN}.md --target-words {目標字數} --genre {題材}
# 混合題材範例：--genre urban+horror
# 對話區免檢列表結構：加 --ignore-in-dialogue
```

這個腳本會自動檢查：
- 字數是否達標（< 90% → critical）
- 段落等長（CV < 0.15 → warning）
- 套話詞密度（> 3/千字 → warning）
- 公式化轉折（同一詞 ≥ 3 次 → warning）
- 列表式結構（連續 ≥ 3 句同開頭 → info）
- 驚訝標記詞密度（> 1/3000字 → warning）
- 禁忌句式（「不是…而是…」、破折號過度使用、報告式語言 → critical）
- 題材高疲勞詞重複
- 同一意象連續渲染

若腳本回傳 critical（exit code 1），必須先修復 critical issues 再進入 LLM 審計。
若字數不足，回到 Step 2 擴充正文。

**Step 5 — LLM 審計（Auditor Agent）**

規則引擎通過後，讀取以下參考文件執行 LLM 審計：
- `{SKILL_DIR}/references/audit-dimensions.md`
- `{SKILL_DIR}/references/anti-ai-rules.md`

LLM 負責檢查規則引擎無法判斷的維度（1-19, 24-26）：OOC、時間線、設定衝突、信息越界、利益鏈斷裂、配角降智、台詞失真、流水帳等。

輸出審計報告：
```
| 維度 | 嚴重度 | 問題描述 | 修復建議 |
|------|--------|---------|---------|
```

- 判定結果：passed（無 critical）或 failed（有 critical）

**Step 5b — 對立辯論（Adversarial Debate，借鏡 TradingAgents 多空辯論機制）**

審計報告產出後，啟動「讀者辯護人 vs. 作者辯護人」辯論，防止審計盲區和群體思維：

1. **讀者辯護人（Reader Advocate）**：站在目標讀者的角度質疑——
   - 這段我看得懂嗎？節奏會不會太慢讓我想跳過？
   - 伏筆太隱晦還是太明顯？感情線是否做作？
   - 角色動機是否令人信服？我會繼續追讀嗎？

2. **作者辯護人（Author Advocate）**：站在創作意圖的角度辯護——
   - 這段慢節奏是刻意的（為後續爆發鋪墊）嗎？
   - 所謂「AI 味」是否其實是作者的個人風格？
   - 審計員指出的「問題」是否其實是有意為之的敘事手法？

3. **辯論規則**：
   - 最多 **2 輪** 來回（控制 Token 成本）
   - 雙方必須引用具體段落和維度編號，不可空泛議論
   - 辯論焦點限定在審計報告中 **warning 級別以上** 的 issues（info 級不辯論）
   - 若雙方對某個 issue 持相反結論，由 Claude 以「最終裁判」身份裁定，裁定理由必須寫入報告

4. **辯論產出**：在原審計報告上追加一欄「辯論結論」：
   - ✅ **維持**（confirmed）：讀者辯護人認同這確實是問題
   - 🔄 **降級**（downgraded）：作者辯護人成功辯護，嚴重度下調一級
   - ❌ **撤銷**（dismissed）：作者辯護人充分論證為刻意手法，移除此 issue
   - ⬆️ **升級**（escalated）：讀者辯護人提出審計員未發現的額外問題

5. **觸發條件**（為節約 Token，非每章必跑）：
   - 審計報告含 ≥ 2 個 warning 級以上 issues → 自動觸發
   - 使用者執行 `audit` 命令且加上 `--debate` 旗標 → 強制觸發
   - 審計結果為 passed 且 warning = 0 → 跳過辯論

**Step 6 — Reviser Agent 修訂（若審計未通過）**
- 讀取規則引擎 + LLM 審計報告中的 issues
- 根據問題嚴重度選擇模式：
  - 僅 warning/info → `polish`（微調字句）
  - 有 critical 但 < 3 個 → `rewrite`（重寫問題段落）
  - 有 critical 且 ≥ 3 個 → `rework`（全章重構）
  - AI 痕跡問題為主 → `anti-detect`（深度去 AI 味）
- 修訂後重新執行 Step 4（規則引擎）和 Step 5（LLM 審計）
- 若二次審計仍未通過，標記為 needs-review 並通知用戶

**Step 7 — 發布**
- 最終版本存入 chapters/ch{NNN}.md
- 再次更新所有 state/ 文件（與 Step 2d 相同流程，確保最終版的狀態被記錄）
- 再次建立快照（與 Step 3b 相同流程，覆蓋先前的快照，確保快照是最終版）
- 向用戶展示：章節標題、字數、審計結果摘要、關鍵伏筆動態

### AUDIT：獨立審計

1. 讀取指定章節正文
2. 讀取所有 state/ 文件
3. 執行與 WRITE Step 4–5b 相同的審計流程（規則引擎 → LLM 審計 → 視條件對立辯論；`--debate` 強制辯論）
4. 輸出完整審計報告

### REVISE：修訂章節

修訂模式：
- **polish**：字句微調，保持原意和結構不變
- **rewrite**：重寫有問題的段落，保持章節框架
- **rework**：全章重構，可調整情節走向
- **anti-detect**：深度重組句式、替換標記詞、調整段落節奏，專注消除 AI 痕跡

### STATUS：查看狀態

切換為 **Radar Agent**，讀取並彙報：
- 總章節數、總字數、最近更新時間
- 活躍伏筆數量及預期回收章節
- 支線進度概覽
- 角色情感弧線摘要
- 待處理的審計問題

### REWIND：回滾

1. 讀取 snapshots/ch{NNN}/ 中的快照
2. 用快照內容覆蓋 state/ 下所有文件
3. 刪除回滾點之後的章節文件
4. 向用戶確認回滾完成

### ARCHIVE：卷結束歸檔壓縮

每卷結束時（約 10-12 章）執行此命令，防止 state 文件無限膨脹導致 Context window 超載。

**歸檔流程**：

1. **建立卷歸檔目錄**：
```bash
mkdir -p archives/vol{N}
```

2. **壓縮 emotional-arcs.md**：
   - 將當前完整版備份到 `archives/vol{N}/emotional-arcs-full.md`
   - 只保留「最近 5 章 + 全部強度 ≥ 8 的高潮節拍」
   - 在文件頂部加註：`<!-- 完整歷史見 archives/vol{N}/emotional-arcs-full.md -->`

3. **壓縮 chapter-summaries.md**：
   - 將當前完整版備份到 `archives/vol{N}/chapter-summaries-full.md`
   - 早期章節（非最近 5 章）壓縮為一行摘要
   - 最近 5 章保留完整摘要

4. **精簡 character-matrix.md**：
   - 將已死亡或已退場角色的條目移到 `archives/vol{N}/retired-characters.md`
   - 只保留活躍角色的完整記錄

5. **歸檔已回收伏筆**：
   - 將 pending-hooks.md 中狀態為「已回收」的伏筆移到 `archives/vol{N}/resolved-hooks.md`
   - pending-hooks.md 只保留活躍和待回收的伏筆

6. **清理快照**：
   - 保留本卷最後一章的快照和最近 3 章的快照
   - 其餘快照移到 `archives/vol{N}/snapshots/`

7. **向用戶報告**：壓縮前後的文件大小對比、歸檔了哪些內容

## 7 份真相文件

| 文件 | 用途 | 更新頻率 |
|------|------|---------|
| current-state.md | 角色位置、關係、已知資訊 | 每章覆蓋 |
| particle-ledger.md | 資源賬本（物品消耗、衰減追蹤） | 每 3 章或重大事件時覆蓋 |
| pending-hooks.md | 未閉合伏筆與承諾 | 每章覆蓋 |
| chapter-summaries.md | 章節摘要 | 每章追加 |
| subplot-board.md | 支線進度板 | 每 3 章或重大事件時覆蓋 |
| emotional-arcs.md | 角色情緒軌跡 | 每 3 章或重大事件時覆蓋 |
| character-matrix.md | 角色交互矩陣與信息邊界 | 每 3 章或重大事件時覆蓋 |

詳細格式與模板範例見 `{SKILL_DIR}/references/state-schemas.md`

## 27 維度審計（摘要）

**LLM 審計維度（1-19, 24-26）**：
1-OOC / 2-時間線 / 3-設定衝突 / 4-戰力崩壞* / 5-數值檢查* / 6-伏筆 / 7-節奏 / 8-文風 / 9-信息越界 / 10-詞彙疲勞 / 11-利益鏈斷裂 / 12-年代考據* / 13-配角降智 / 14-配角工具人化 / 15-爽點虛化 / 16-台詞失真 / 17-流水帳 / 18-知識庫污染 / 19-視角一致性 / 24-支線停滯 / 25-弧線平坦 / 26-節奏單調

**規則引擎維度（20-23）**：
20-段落等長 / 21-套話密度 / 22-公式化轉折 / 23-列表式結構

**條件維度（需題材配置啟用）**：4-戰力崩壞 / 5-數值檢查 / 12-年代考據 / **27-地理真實性**（`realWorldGeography=true`，真實世界地理的移動 / 路線 / 偵查 / 抵達新地點章查證地理事實；見 `references/geography-verify.md`）

（*及條件維度需題材配置啟用）

詳見 `{SKILL_DIR}/references/audit-dimensions.md`

## 去 AI 味核心規則

- 驚訝標記詞（仿佛/忽然/竟然/猛地/不禁/宛如）≤ 每 3000 字 1 次
- 套話詞（似乎/可能/或許）密度 ≤ 3 次/千字
- 禁止分析報告式語言（核心動機、信息邊界、利益最大化等）
- 禁止「不是……而是……」句式
- 破折號「——」限量：每千字 ≤ 2 次（3–5 次警告，> 5 次嚴重，同 `audit_rules.py`）
- 同一意象禁止連續渲染超過兩輪
- 敘述者永遠不替讀者下結論

詳見 `{SKILL_DIR}/references/anti-ai-rules.md`

## 題材規則三層結構

**第 1 層：通用規則**（所有題材共用的 25 條基礎創作規則，定義在 writer-rules.md 中）

**第 2 層：題材規則**（各題材特有的章節類型、高疲勞詞、審計維度、節奏規則、禁忌）
- 玄幻：`references/genre-xuanhuan.md`
- 仙俠：`references/genre-xianxia.md`
- 都市：`references/genre-urban.md`
- 恐怖：`references/genre-horror.md`

**第 3 層：書籍規則**（book-rules.md，每本書的主角人設鎖、數值上限、自定義禁令）

## 品質門機制

- 最多審計重試 2 次（第一次 Reviser 修訂後重新審計）
- 連續 3 章審計失敗 → 暫停管線，通知用戶介入
- 所有狀態變更都有快照可回滾

## 參考文件索引

| 文件 | 內容 | 何時讀取 |
|------|------|---------|
| `{SKILL_DIR}/references/writer-rules.md` | Writer Agent 完整寫作規則（25條基礎 + 技法 + 輸出格式） | 執行 write/draft 時 |
| `{SKILL_DIR}/references/audit-dimensions.md` | 27 維度審計完整定義 | 執行 audit 時 |
| `{SKILL_DIR}/references/geography-verify.md` | 維度 27 地理真實性 SOP（路線真相卡 + 工具綁定） | realWorldGeography 移動章 audit / 寫作前 |
| `{SKILL_DIR}/references/anti-ai-rules.md` | 去 AI 味完整規則與標記詞清單 | 執行 audit/revise 時 |
| `{SKILL_DIR}/references/state-schemas.md` | 7 份真相文件的格式與模板 | 執行 create 時 |
| `{SKILL_DIR}/references/genre-*.md` | 各題材專屬規則 | 依書籍題材讀取 |

---

**版本**：1.3.0 | **架構靈感**：InkOS | **更新日期**：2026-03-19
