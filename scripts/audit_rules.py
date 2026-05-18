#!/usr/bin/env python3
"""
Novel Craft — 規則引擎審計腳本
用途：對章節正文執行確定性的規則檢查（不需要 LLM），涵蓋：
  1. 字數統計與達標檢查
  2. 去 AI 味標記詞檢測（維度 20-23）
  3. 高疲勞詞檢測
  4. 禁忌句式檢測
  5. 段落節奏分析

使用方式：
  python3 scripts/audit_rules.py chapters/ch001.md --target-words 4000
  python3 scripts/audit_rules.py chapters/ch001.md --genre xuanhuan --target-words 5000
"""

import sys
import re
import json
import statistics
from pathlib import Path
from collections import Counter

# ============================================================
# 1. 標記詞與規則定義
# ============================================================

# 驚訝標記詞（每 3000 字 ≤ 1 次）
SURPRISE_MARKERS = ["仿佛", "彷彿", "忽然", "竟", "竟然", "猛地", "猛然", "不禁", "宛如"]

# 套話詞（密度 ≤ 3 次/千字）
HEDGE_WORDS = ["似乎", "可能", "或許", "大概", "某種程度上", "一定程度上", "在某種意義上"]

# 公式化轉折詞（同一詞 ≤ 2 次）
TRANSITION_WORDS = ["然而", "不過", "與此同時", "另一方面", "儘管如此", "盡管如此", "話雖如此", "但值得注意的是"]

# 禁止句式
FORBIDDEN_PATTERNS = [
    (r"不是[^，。！？\n]{1,20}而是", "禁止「不是……而是……」句式"),
    # 破折號改為密度制，見 check_dash_density()
    (r"核心動機|信息邊界|信息落差|核心風險|利益最大化|當前處境", "禁止分析報告式語言"),
    (r"核心动机|信息边界|信息落差|核心风险|利益最大化|当前处境", "禁止分析報告式語言（簡體）"),
]

# 題材專屬高疲勞詞
GENRE_FATIGUE_WORDS = {
    "xuanhuan": ["冷笑", "蝼蚁", "螻蟻", "倒吸涼氣", "倒吸凉气", "瞳孔驟縮", "瞳孔骤缩",
                 "不可置信", "轟然炸裂", "轰然炸裂", "滿場死寂", "满场死寂", "難以置信", "难以置信"],
    "xianxia": ["冷笑", "蝼蚁", "螻蟻", "道心", "心魔", "劫雷", "天道", "氣運", "气运",
                "倒吸涼氣", "倒吸凉气", "瞳孔驟縮", "瞳孔骤缩"],
    "urban": ["眼神一冷", "嘴角上揚", "嘴角上扬", "淡淡一笑", "微微一笑", "嗤笑一聲", "嗤笑一声"],
    "horror": ["毛骨悚然", "不寒而慄", "不寒而栗", "頭皮發麻", "头皮发麻", "遍體生寒", "遍体生寒"],
}


def count_chars(text: str) -> int:
    """計算中文字數（排除空白和標點的純字數）"""
    # 移除 Markdown 標題和格式符號
    clean = re.sub(r'^#+\s.*$', '', text, flags=re.MULTILINE)
    clean = re.sub(r'[#*_`~\[\]()>|]', '', clean)
    # 計算非空白字元數
    return len(re.sub(r'\s', '', clean))


def count_words_mixed(text: str) -> int:
    """混合語言字數：中文按字數，英文按詞數"""
    clean = re.sub(r'^#+\s.*$', '', text, flags=re.MULTILINE)
    clean = re.sub(r'[#*_`~\[\]()>|]', '', clean)
    # 中文字數
    cn_chars = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', clean))
    # 英文詞數
    en_words = len(re.findall(r'[a-zA-Z]+', clean))
    return cn_chars + en_words


def check_surprise_markers(text: str, char_count: int) -> list:
    """檢查驚訝標記詞密度：每 3000 字 ≤ 1 次"""
    issues = []
    total_count = 0
    details = []
    for word in SURPRISE_MARKERS:
        count = len(re.findall(word, text))
        if count > 0:
            total_count += count
            details.append(f"{word}×{count}")

    allowed = max(1, char_count // 3000)
    if total_count > allowed:
        issues.append({
            "dimension": 10,
            "dimension_name": "詞彙疲勞（驚訝標記詞）",
            "severity": "warning",
            "description": f"驚訝標記詞共 {total_count} 次（{', '.join(details)}），每 3000 字允許 {allowed} 次",
            "suggestion": "用具體動作或感官描寫替代標記詞"
        })
    return issues


def check_hedge_words(text: str, char_count: int) -> list:
    """檢查套話詞密度：≤ 3 次/千字"""
    issues = []
    total_count = 0
    details = []
    for word in HEDGE_WORDS:
        count = len(re.findall(word, text))
        if count > 0:
            total_count += count
            details.append(f"{word}×{count}")

    density = total_count / max(1, char_count / 1000)
    if density > 3:
        issues.append({
            "dimension": 21,
            "dimension_name": "套話密度",
            "severity": "warning",
            "description": f"套話詞密度 {density:.1f} 次/千字（{', '.join(details)}），閾值為 3 次/千字",
            "suggestion": "用確定性敘述替代模糊表達"
        })
    return issues


def check_transition_words(text: str) -> list:
    """檢查公式化轉折詞：同一詞 ≤ 2 次"""
    issues = []
    for word in TRANSITION_WORDS:
        count = len(re.findall(word, text))
        if count >= 3:
            issues.append({
                "dimension": 22,
                "dimension_name": "公式化轉折",
                "severity": "warning",
                "description": f"轉折詞「{word}」出現 {count} 次，閾值為 2 次",
                "suggestion": "用情節自然轉折替代；或換用不同的過渡手法（動作切入、時間跳躍、視角切換）"
            })
    return issues


def check_paragraph_uniformity(text: str) -> list:
    """維度 20：段落等長檢查（CV < 0.15 → warning）"""
    issues = []
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip() and not p.strip().startswith('#')]
    if len(paragraphs) < 3:
        return issues

    lengths = [len(p) for p in paragraphs]
    mean_len = statistics.mean(lengths)
    if mean_len == 0:
        return issues
    stdev = statistics.stdev(lengths) if len(lengths) > 1 else 0
    cv = stdev / mean_len

    if cv < 0.15:
        issues.append({
            "dimension": 20,
            "dimension_name": "段落等長",
            "severity": "warning",
            "description": f"段落長度變異係數 CV={cv:.3f}（閾值 0.15），段落長度過於均勻（AI 特徵）",
            "suggestion": f"增加段落長度差異。當前段落長度：最短 {min(lengths)} 字、最長 {max(lengths)} 字、平均 {mean_len:.0f} 字"
        })
    return issues


def check_list_structure(text: str) -> list:
    """維度 23：列表式結構檢查（連續 ≥ 3 句前 2 字相同 → info）"""
    issues = []
    sentences = re.split(r'[。！？\n]', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) >= 4]

    consecutive = 1
    for i in range(1, len(sentences)):
        if sentences[i][:2] == sentences[i-1][:2]:
            consecutive += 1
            if consecutive >= 3:
                issues.append({
                    "dimension": 23,
                    "dimension_name": "列表式結構",
                    "severity": "info",
                    "description": f"連續 {consecutive} 句以「{sentences[i][:2]}」開頭（第 {i-consecutive+2}-{i+1} 句）",
                    "suggestion": "變換句式開頭，用不同主語、時間詞、動作詞開頭"
                })
        else:
            consecutive = 1
    return issues


def check_forbidden_patterns(text: str) -> list:
    """檢查禁止句式"""
    issues = []
    for pattern, description in FORBIDDEN_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            issues.append({
                "dimension": "禁忌句式",
                "dimension_name": description,
                "severity": "critical",
                "description": f"發現 {len(matches)} 處違規：{description}",
                "suggestion": f"匹配內容：{'、'.join(matches[:3])}"
            })
    return issues


def check_genre_fatigue(text: str, genre: str) -> list:
    """檢查題材專屬高疲勞詞"""
    issues = []
    fatigue_words = GENRE_FATIGUE_WORDS.get(genre, [])
    found = []
    for word in fatigue_words:
        count = len(re.findall(word, text))
        if count >= 2:
            found.append(f"{word}×{count}")
    if found:
        issues.append({
            "dimension": 10,
            "dimension_name": "詞彙疲勞（題材高頻詞）",
            "severity": "warning",
            "description": f"高疲勞詞重複：{', '.join(found)}",
            "suggestion": "用具體描寫替代套路用語"
        })
    return issues


def check_repetition(text: str) -> list:
    """檢查同一意象連續渲染超過兩輪"""
    issues = []
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

    for i in range(2, len(paragraphs)):
        # 提取每段的名詞/關鍵詞（簡化版：取 2 字以上重複的詞）
        words_prev2 = set(re.findall(r'[\u4e00-\u9fff]{2,4}', paragraphs[i-2]))
        words_prev1 = set(re.findall(r'[\u4e00-\u9fff]{2,4}', paragraphs[i-1]))
        words_curr = set(re.findall(r'[\u4e00-\u9fff]{2,4}', paragraphs[i]))

        # 三段共有的詞（排除常見虛詞）
        common_stopwords = {"的是", "了的", "一個", "一个", "這個", "这个", "那個", "那个",
                           "什麼", "什么", "沒有", "没有", "不是", "自己", "已經", "已经",
                           "可以", "因為", "因为", "所以", "但是", "如果", "就是", "他們",
                           "他们", "她們", "她们", "我們", "我们", "這裡", "这里", "那裡", "那里"}
        shared = (words_prev2 & words_prev1 & words_curr) - common_stopwords
        if len(shared) >= 3:
            issues.append({
                "dimension": "意象重複",
                "dimension_name": "同一意象連續渲染",
                "severity": "info",
                "description": f"段落 {i-1}-{i+1} 連續三段出現相同意象：{', '.join(list(shared)[:5])}",
                "suggestion": "第三次出現相同意象域時，必須切換到新信息或新動作"
            })
    return issues


def check_dialogue_ratio(text: str) -> list:
    """檢查對話比例：正常範圍 20%-60%"""
    issues = []
    # 匹配中文對話（「」或""括起來的內容）
    dialogues = re.findall(r'[「「"][^」」"]*[」」"]', text)
    dialogue_chars = sum(len(d) for d in dialogues)
    total_chars = len(re.sub(r'\s', '', text))
    if total_chars == 0:
        return issues
    ratio = dialogue_chars / total_chars
    if ratio < 0.1:
        issues.append({
            "dimension": "對話比例",
            "dimension_name": "對話過少",
            "severity": "warning",
            "description": f"對話佔比 {ratio*100:.1f}%（正常 20%-60%），場景可能偏向大段敘述",
            "suggestion": "增加角色互動和對話，用對話推動情節而非純敘述"
        })
    elif ratio > 0.7:
        issues.append({
            "dimension": "對話比例",
            "dimension_name": "對話過多",
            "severity": "info",
            "description": f"對話佔比 {ratio*100:.1f}%（正常 20%-60%），可能缺乏環境和心理描寫",
            "suggestion": "在對話間插入動作、表情、環境描寫，避免劇本感"
        })
    return issues


def check_scene_transitions(text: str) -> list:
    """檢查場景切換：是否有明確的轉場標記"""
    issues = []
    # 檢測分隔線 ---
    separators = len(re.findall(r'\n---\n', text))
    # 檢測時間跳躍標記
    time_jumps = len(re.findall(r'(翌日|次日|三天後|三天后|幾天後|几天后|一個月後|一个月后|片刻後|片刻后|半個時辰|半个时辰|不多時|不多时)', text))
    # 檢測空行分段（連續兩個以上空行）
    double_breaks = len(re.findall(r'\n\n\n', text))

    total_transitions = separators + time_jumps + double_breaks
    # 計算段落數來估算是否需要場景切換
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip() and not p.strip().startswith('#')]
    if len(paragraphs) > 15 and total_transitions == 0:
        issues.append({
            "dimension": "場景切換",
            "dimension_name": "缺少場景轉場標記",
            "severity": "info",
            "description": f"全章 {len(paragraphs)} 段落，但未檢測到場景切換標記（分隔線、時間跳躍詞）",
            "suggestion": "如果本章包含多個場景，用 --- 分隔線或時間跳躍詞明確標記轉場"
        })
    return issues


def check_character_name_consistency(text: str) -> list:
    """檢查角色稱呼一致性：同一角色是否被多種方式稱呼"""
    issues = []
    # 提取所有可能的人名（連續 2-3 個中文字，出現在「他/她/我」附近或對話標記前後）
    # 簡化版：找到所有重複出現的 2-3 字中文詞，看是否有近似變體
    names = re.findall(r'(?:[\u4e00-\u9fff]{2,4})(?=道|說|说|笑道|嘆道|叹道|冷笑|怒道|問|问)', text)
    name_counter = Counter(names)
    # 找出只出現 1 次的「稱呼+道」，可能是不一致的稱呼
    rare_names = [n for n, c in name_counter.items() if c == 1 and len(n) >= 2]
    frequent_names = [n for n, c in name_counter.items() if c >= 3]

    if rare_names and frequent_names:
        # 檢查罕見稱呼是否是頻繁稱呼的變體（共享至少一個字）
        for rare in rare_names:
            for freq in frequent_names:
                shared = set(rare) & set(freq)
                if shared and rare != freq and len(rare) == len(freq):
                    issues.append({
                        "dimension": "稱呼一致性",
                        "dimension_name": "角色稱呼可能不一致",
                        "severity": "info",
                        "description": f"「{rare}」只出現 1 次，但「{freq}」出現多次，可能是同一角色的不同稱呼",
                        "suggestion": f"確認「{rare}」和「{freq}」是否為同一人，統一稱呼方式"
                    })
    return issues


def check_dash_density(text: str, char_count: int) -> list:
    """破折號密度制：每千字 ≤ 2 次 OK，3-5 次 WARNING，>5 次 CRITICAL"""
    issues = []
    # 匹配連續破折號（—— 或 ──）
    dash_count = len(re.findall(r'——|──', text))
    density = dash_count / max(1, char_count / 1000)

    if density > 5:
        issues.append({
            "dimension": "禁忌句式",
            "dimension_name": "破折號過度使用",
            "severity": "critical",
            "description": f"破折號密度 {density:.1f} 次/千字（{dash_count} 次），超過 5 次/千字閾值",
            "suggestion": "大量減少破折號使用，改用逗號、分號或分句"
        })
    elif density > 3:
        issues.append({
            "dimension": "禁忌句式",
            "dimension_name": "破折號偏多",
            "severity": "warning",
            "description": f"破折號密度 {density:.1f} 次/千字（{dash_count} 次），建議控制在 2 次/千字以內",
            "suggestion": "適當減少破折號，部分改用其他標點或句式"
        })
    return issues


def strip_dialogue(text: str) -> str:
    """移除對話區的內容（用於列表式結構檢查等需要排除對話的場景）"""
    # 移除「」和""括起來的對話內容
    cleaned = re.sub(r'[「「"][^」」"]*[」」"]', '', text)
    return cleaned


def run_audit(filepath: str, target_words: int = 4000, genre: str = "xuanhuan",
              ignore_in_dialogue: bool = False) -> dict:
    """執行完整的規則引擎審計"""
    text = Path(filepath).read_text(encoding='utf-8')

    # 去掉 Markdown 標題行（# 第一章 xxx）
    content_lines = [l for l in text.split('\n') if not l.startswith('# ')]
    content = '\n'.join(content_lines)

    char_count = count_chars(content)
    word_count = count_words_mixed(content)

    all_issues = []

    # 字數檢查
    if char_count < target_words * 0.9:
        all_issues.append({
            "dimension": "字數",
            "dimension_name": "字數不足",
            "severity": "critical",
            "description": f"正文 {char_count} 字，目標 {target_words} 字（達成率 {char_count/target_words*100:.1f}%，低於 90% 閾值）",
            "suggestion": f"需補充約 {target_words - char_count} 字。擴充場景細節、對話、心理描寫、五感描寫"
        })
    elif char_count > target_words * 1.2:
        all_issues.append({
            "dimension": "字數",
            "dimension_name": "字數超標",
            "severity": "info",
            "description": f"正文 {char_count} 字，超過目標 {target_words} 字的 120%",
            "suggestion": "考慮分章或刪減冗餘"
        })

    # 決定用於結構檢查的文本（是否排除對話區）
    structure_text = strip_dialogue(content) if ignore_in_dialogue else content

    # 規則引擎維度 20-23（列表式結構用 structure_text）
    all_issues.extend(check_paragraph_uniformity(content))
    all_issues.extend(check_hedge_words(content, char_count))
    all_issues.extend(check_transition_words(content))
    all_issues.extend(check_list_structure(structure_text))  # C: 對話區免檢

    # 去 AI 味檢查
    all_issues.extend(check_surprise_markers(content, char_count))
    all_issues.extend(check_forbidden_patterns(content))
    all_issues.extend(check_dash_density(content, char_count))  # D: 破折號密度制

    # E: 混合題材支援（genre 可為 "urban+horror" 格式）
    genres = [g.strip() for g in genre.split('+')]
    for g in genres:
        all_issues.extend(check_genre_fatigue(content, g))
    all_issues.extend(check_repetition(content))

    # 新增檢查（v1.1）
    all_issues.extend(check_dialogue_ratio(content))
    all_issues.extend(check_scene_transitions(content))
    all_issues.extend(check_character_name_consistency(content))

    # 統計
    critical_count = sum(1 for i in all_issues if i["severity"] == "critical")
    warning_count = sum(1 for i in all_issues if i["severity"] == "warning")
    info_count = sum(1 for i in all_issues if i["severity"] == "info")
    passed = critical_count == 0

    result = {
        "file": filepath,
        "char_count": char_count,
        "word_count_mixed": word_count,
        "target_words": target_words,
        "achievement_rate": f"{char_count/target_words*100:.1f}%",
        "genre": genre,
        "passed": passed,
        "summary": {
            "critical": critical_count,
            "warning": warning_count,
            "info": info_count,
            "total": len(all_issues)
        },
        "issues": all_issues
    }
    return result


def print_report(result: dict):
    """印出人類可讀的審計報告"""
    print(f"\n{'='*60}")
    print(f"  Novel Craft 規則引擎審計報告")
    print(f"{'='*60}")
    print(f"  檔案：{result['file']}")
    print(f"  字數：{result['char_count']} 字（目標 {result['target_words']}，達成率 {result['achievement_rate']}）")
    print(f"  題材：{result['genre']}")
    print(f"  結果：{'✅ PASSED' if result['passed'] else '❌ FAILED'}")
    print(f"  問題：{result['summary']['critical']} critical / {result['summary']['warning']} warning / {result['summary']['info']} info")
    print(f"{'='*60}\n")

    if not result['issues']:
        print("  無問題！所有規則引擎檢查通過。\n")
        return

    for i, issue in enumerate(result['issues'], 1):
        severity_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(issue["severity"], "⚪")
        print(f"  {severity_icon} [{issue['severity'].upper()}] {issue['dimension_name']}")
        print(f"     {issue['description']}")
        print(f"     → {issue['suggestion']}")
        print()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Novel Craft 規則引擎審計")
    parser.add_argument("file", help="章節 Markdown 文件路徑")
    parser.add_argument("--target-words", type=int, default=4000, help="目標字數（預設 4000）")
    parser.add_argument("--genre", default="xuanhuan",
                       help="題材，支援混合模式如 urban+horror（預設 xuanhuan）")
    parser.add_argument("--ignore-in-dialogue", action="store_true",
                       help="在對話區（引號內）放寬列表式結構檢查")
    parser.add_argument("--json", action="store_true", help="輸出 JSON 格式")
    args = parser.parse_args()

    result = run_audit(args.file, args.target_words, args.genre, args.ignore_in_dialogue)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_report(result)

    sys.exit(0 if result["passed"] else 1)
