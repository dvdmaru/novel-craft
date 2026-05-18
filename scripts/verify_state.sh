#!/bin/bash
# Novel Craft — State 文件驗證腳本
# 用途：一行指令完成行數檢查 + 修改時間檢查 + character-matrix 行數不減檢查
# 使用方式：bash scripts/verify_state.sh [上一章快照目錄]
# 例如：bash scripts/verify_state.sh snapshots/ch005

STATE_DIR="state"
PREV_SNAPSHOT="${1:-}"

echo ""
echo "============================================"
echo "  Novel Craft State 文件驗證"
echo "============================================"

PASS=true
FILES=(current-state.md particle-ledger.md pending-hooks.md chapter-summaries.md subplot-board.md emotional-arcs.md character-matrix.md)

echo ""
echo "  [1/3] 文件存在性與行數"
echo "  ------------------------------------"
for f in "${FILES[@]}"; do
    if [ -f "$STATE_DIR/$f" ]; then
        lines=$(wc -l < "$STATE_DIR/$f" | tr -d ' ')
        # macOS stat 和 Linux stat 語法不同
        mod_time=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$STATE_DIR/$f" 2>/dev/null || stat -c "%y" "$STATE_DIR/$f" 2>/dev/null | cut -d. -f1)
        printf "  ✓ %-25s %4s lines | %s\n" "$f" "$lines" "$mod_time"
    else
        printf "  ✗ %-25s MISSING!\n" "$f"
        PASS=false
    fi
done

echo ""
echo "  [2/3] 修改時間檢查（應在最近 30 分鐘內）"
echo "  ------------------------------------"
NOW=$(date +%s)
for f in "${FILES[@]}"; do
    if [ -f "$STATE_DIR/$f" ]; then
        # macOS
        MOD=$(stat -f "%m" "$STATE_DIR/$f" 2>/dev/null || stat -c "%Y" "$STATE_DIR/$f" 2>/dev/null)
        DIFF=$(( NOW - MOD ))
        if [ "$DIFF" -gt 1800 ]; then
            printf "  ⚠ %-25s 最後修改在 %d 分鐘前（可能未更新）\n" "$f" "$(( DIFF / 60 ))"
        else
            printf "  ✓ %-25s %d 分鐘前更新\n" "$f" "$(( DIFF / 60 ))"
        fi
    fi
done

echo ""
echo "  [3/3] character-matrix 行數不減檢查"
echo "  ------------------------------------"
if [ -n "$PREV_SNAPSHOT" ] && [ -f "$PREV_SNAPSHOT/character-matrix.md" ]; then
    PREV_LINES=$(wc -l < "$PREV_SNAPSHOT/character-matrix.md" | tr -d ' ')
    CURR_LINES=$(wc -l < "$STATE_DIR/character-matrix.md" | tr -d ' ')
    if [ "$CURR_LINES" -lt "$PREV_LINES" ]; then
        echo "  ✗ character-matrix.md 行數從 $PREV_LINES 減少到 $CURR_LINES（可能遺漏角色）"
        PASS=false
    else
        echo "  ✓ character-matrix.md: $PREV_LINES → $CURR_LINES 行（OK）"
    fi
else
    echo "  ⊘ 未提供上一章快照目錄，跳過行數比較"
fi

echo ""
echo "============================================"
if [ "$PASS" = true ]; then
    echo "  結果：✅ ALL PASSED"
else
    echo "  結果：❌ ISSUES FOUND — 請檢查上方標記"
fi
echo "============================================"
echo ""
