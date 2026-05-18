#!/usr/bin/env python3
"""
Novel Craft — 跨章一致性審計腳本
用途：掃描所有章節，檢查跨章的數字、稱呼、時間線一致性。
      彌補單章 audit_rules.py 無法發現的跨章 bug。

使用方式：
  python3 scripts/audit_consistency.py chapters/
  python3 scripts/audit_consistency.py chapters/ --story-bible story-bible.md
"""

import sys
import re
import json
from pathlib import Path
from collections import Counter, defaultdict


def load_chapters(chapters_dir: str) -> list:
    """載入所有章節，按章節號排序"""
    chapter_dir = Path(chapters_dir)
    chapters = []
    for f in sorted(chapter_dir.glob("ch*.md")):
        num_match = re.search(r'ch(\d+)', f.name)
        if num_match:
            chapters.append({
                "file": str(f),
                "number": int(num_match.group(1)),
                "text": f.read_text(encoding='utf-8')
            })
    return chapters


def check_name_consistency(chapters: list) -> list:
    """檢查角色稱呼在全書中是否一致"""
    issues = []
    # 收集每章的「名字+道/說」模式
    global_names = Counter()
    chapter_names = {}

    for ch in chapters:
        names = re.findall(r'([\u4e00-\u9fff]{2,4})(?=道|說|说|笑道|嘆道|叹道|冷笑|怒道|問|问)', ch["text"])
        chapter_names[ch["number"]] = Counter(names)
        global_names.update(names)

    # 找出全書只出現 1-2 次的稱呼，可能是筆誤
    frequent = {n for n, c in global_names.items() if c >= 5}
    rare = {n for n, c in global_names.items() if c <= 2}

    for r in rare:
        for f in frequent:
            if len(r) == len(f) and len(set(r) & set(f)) >= 1 and r != f:
                # 找出罕見稱呼出現在哪一章
                ch_nums = [ch["number"] for ch in chapters if r in chapter_names[ch["number"]]]
                issues.append({
                    "type": "name_inconsistency",
                    "severity": "warning",
                    "description": f"「{r}」僅出現 {global_names[r]} 次（第 {ch_nums} 章），但「{f}」出現 {global_names[f]} 次，可能是同一角色",
                    "suggestion": f"確認「{r}」和「{f}」是否為同一人"
                })
    return issues


def check_time_continuity(chapters: list) -> list:
    """檢查時間標記是否連貫（Day X、星期、日期）"""
    issues = []
    time_markers = []

    for ch in chapters:
        # 匹配各種時間標記
        days = re.findall(r'第(\d+)天|Day\s*(\d+)', ch["text"])
        weekdays = re.findall(r'(星期[一二三四五六日天]|週[一二三四五六日天]|周[一二三四五六日天])', ch["text"])
        dates = re.findall(r'(\d{1,2}月\d{1,2}[日號号])', ch["text"])

        if days or weekdays or dates:
            time_markers.append({
                "chapter": ch["number"],
                "days": days,
                "weekdays": weekdays,
                "dates": dates
            })

    # 檢查 Day X 是否遞增
    prev_day = 0
    for tm in time_markers:
        for d in tm["days"]:
            day_num = int(d[0] or d[1])
            if day_num < prev_day and day_num != 1:  # 允許回到 Day 1（新卷）
                issues.append({
                    "type": "time_regression",
                    "severity": "warning",
                    "description": f"第 {tm['chapter']} 章出現 Day {day_num}，但之前已到 Day {prev_day}（時間倒退）",
                    "suggestion": "確認時間線是否正確，是否為回憶場景"
                })
            prev_day = max(prev_day, day_num)

    return issues


def check_number_consistency(chapters: list) -> list:
    """檢查數字描述的一致性（人數、距離、金額等關鍵數字）"""
    issues = []
    # 收集各章中出現的「X人」「X個人」等人數描述
    chapter_counts = {}

    for ch in chapters:
        counts = re.findall(r'(\d+)\s*(?:人|個人|个人|名|位)', ch["text"])
        if counts:
            chapter_counts[ch["number"]] = [int(c) for c in counts]

    # 檢查相鄰章節的人數是否有突然跳變（不含增減事件）
    prev_ch = None
    prev_counts = None
    for ch_num in sorted(chapter_counts.keys()):
        if prev_counts is not None:
            curr = set(chapter_counts[ch_num])
            prev = set(prev_counts)
            # 如果前後章都提到某個人數，但數字不同且差異大，標記
            for c in curr:
                for p in prev:
                    if abs(c - p) == 1 and c > 3 and p > 3:
                        issues.append({
                            "type": "number_drift",
                            "severity": "info",
                            "description": f"第 {prev_ch} 章提到 {p} 人，第 {ch_num} 章變為 {c} 人（±1 偏移）",
                            "suggestion": "確認人數變化是否有對應的劇情事件（有人加入/離開/死亡）"
                        })
        prev_ch = ch_num
        prev_counts = chapter_counts[ch_num]

    return issues


def run_consistency_audit(chapters_dir: str) -> dict:
    """執行完整的跨章一致性審計"""
    chapters = load_chapters(chapters_dir)

    if not chapters:
        return {"error": f"在 {chapters_dir} 中未找到任何章節文件（ch*.md）"}

    all_issues = []
    all_issues.extend(check_name_consistency(chapters))
    all_issues.extend(check_time_continuity(chapters))
    all_issues.extend(check_number_consistency(chapters))

    warning_count = sum(1 for i in all_issues if i["severity"] == "warning")
    info_count = sum(1 for i in all_issues if i["severity"] == "info")

    return {
        "chapters_scanned": len(chapters),
        "chapter_range": f"ch{chapters[0]['number']:03d} - ch{chapters[-1]['number']:03d}",
        "summary": {
            "warning": warning_count,
            "info": info_count,
            "total": len(all_issues)
        },
        "issues": all_issues
    }


def print_report(result: dict):
    """印出跨章一致性報告"""
    if "error" in result:
        print(f"錯誤：{result['error']}")
        return

    print(f"\n{'='*60}")
    print(f"  Novel Craft 跨章一致性審計報告")
    print(f"{'='*60}")
    print(f"  掃描範圍：{result['chapters_scanned']} 章（{result['chapter_range']}）")
    print(f"  問題：{result['summary']['warning']} warning / {result['summary']['info']} info")
    print(f"{'='*60}\n")

    if not result['issues']:
        print("  無問題！跨章一致性檢查通過。\n")
        return

    for i, issue in enumerate(result['issues'], 1):
        icon = {"warning": "🟡", "info": "🔵"}.get(issue["severity"], "⚪")
        print(f"  {icon} [{issue['severity'].upper()}] {issue['type']}")
        print(f"     {issue['description']}")
        print(f"     → {issue['suggestion']}")
        print()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Novel Craft 跨章一致性審計")
    parser.add_argument("chapters_dir", help="章節目錄路徑（如 chapters/）")
    parser.add_argument("--json", action="store_true", help="輸出 JSON 格式")
    args = parser.parse_args()

    result = run_consistency_audit(args.chapters_dir)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_report(result)
