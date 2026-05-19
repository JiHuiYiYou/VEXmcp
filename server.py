"""
VEX V5 C++ API MCP Server
Provides tools for Claude Code to look up VEX API reference when writing VEX robot code.
Loads vex_cpp_api.json (165 APIs crawled from api.vex.com) into memory.
"""

import json
import os
import re
from fastmcp import FastMCP

mcp = FastMCP("VEX API Reference")

# ── Load API data ────────────────────────────────────────────────────────────
DATA_FILE = os.path.join(os.path.dirname(__file__), "vex_cpp_api_v2.json")
with open(DATA_FILE, "r", encoding="utf-8") as f:
    API_DATA: list[dict] = json.load(f)

# ── Build indexes ────────────────────────────────────────────────────────────
_by_class: dict[str, list[dict]] = {}
_name_lower_map: dict[str, list[dict]] = {}
_all_names: list[str] = []

for api in API_DATA:
    cls = api.get("class", "")
    _by_class.setdefault(cls, []).append(api)

    name_lower = api["name"].lower()
    _name_lower_map.setdefault(name_lower, []).append(api)
    _all_names.append(api["name"])

ALL_CLASSES = sorted(_by_class.keys())

# ── Search aliases: map common terms to API names/classes ─────────────────────
_SEARCH_ALIASES: dict[str, list[str]] = {
    # Motors
    "电机": ["motor", "motor_group"],
    "马达": ["motor", "motor_group"],
    "spin": ["spin", "spinFor", "spinToPosition", "setVelocity", "isSpinning"],
    "转动": ["spin", "spinFor", "rotateTo", "rotateFor"],
    "转速": ["setVelocity", "velocity"],
    "停止": ["stop", "setStopping"],
    "制动": ["setStopping"],
    "完成": ["isDone"],
    "超时": ["setTimeout"],
    "转向": ["turnToHeading", "turnToRotation", "direction"],
    "位置": ["position", "setPosition"],
    "复位": ["resetPosition", "resetRotation"],
    # Controller
    "手柄": ["controller"],
    "遥控器": ["controller"],
    "按键": ["pressing", "released", "Button"],
    "按钮": ["pressing", "released", "Button"],
    "摇杆": ["Axis"],
    "axis": ["Axis"],
    # Sensors
    "传感器": ["accelerometer", "gyro", "distance", "vision", "optical", "rotation", "inertial", "gps"],
    "距离": ["distance"],
    "陀螺仪": ["gyro", "inertial"],
    "视觉": ["vision"],
    "光学": ["optical"],
    "旋转": ["rotation", "rotateTo", "rotateFor"],
    "编码器": ["rotation", "encoder"],
    "惯性": ["inertial"],
    "gps": ["gps"],
    # Pneumatics
    "气动": ["pneumatics", "digital_out"],
    "气缸": ["pneumatics", "digital_out"],
    # Brain
    "主控": ["brain"],
    "大脑": ["brain"],
    "端口": ["port", "triport"],
    # Competition
    "竞赛": ["competition"],
    "自动": ["autonomous"],
    "手动": ["usercontrol"],
    "初始化": ["pre_auton", "vexcodeInit"],
    # Display / Screen
    "屏幕": ["screen", "lcd"],
    "显示": ["screen", "lcd"],
    # Motor Groups / Drivetrain
    "底盘": ["motor_group", "drivetrain", "smartdrive"],
    "传动": ["motor_group", "drivetrain", "smartdrive"],
    "驱动": ["motor_group", "drivetrain", "smartdrive"],
    # Common methods
    "复位": ["resetRotation", "resetPosition", "reset"],
    "扭矩": ["setMaxTorque", "torque", "setMotorTorque"],
    "效率": ["setEfficiency"],
    "温度": ["temperature"],
    "电流": ["current"],
    "电压": ["voltage"],
    "功率": ["power"],
}


def _rank_api(api: dict, q: str) -> int:
    """Compute a relevance score for an API against a query. Higher = better."""
    score = 0
    name_l = api["name"].lower()
    cls_l = api["class"].lower()
    desc_l = api.get("description", "").lower()

    if q == name_l:
        score += 100  # exact name match
    elif q in name_l:
        score += 60   # partial name match
    if q == cls_l:
        score += 50   # exact class match
    elif q in cls_l:
        score += 30   # partial class match
    if q in desc_l:
        score += 10   # description match
    # prefer non-destructor results unless searching for ~
    if api.get("is_destructor") and "~" not in q and "析构" not in q:
        score -= 5

    return score


@mcp.tool
def search_vex_api(query: str) -> list[dict]:
    """【编写VEX代码时调用】搜索 VEX V5 C++ API。当用户需要控制电机、读取传感器、使用遥控器、操作气动装置、屏幕显示等任何VEX硬件编程相关场景时，调用此工具查找对应的API函数。支持中英文关键词，如"motor""电机""controller""手柄""sensor""传感器""spin""转速"等。返回匹配的API列表，包含名称(name)、类名(class)、签名(signatures)、描述(description)等。"""
    q = query.lower().strip()
    scored: dict[int, dict] = {}  # id(api) -> (score, api)

    def add(api, base_score=0):
        key = id(api)
        if key in scored:
            scored[key] = (max(scored[key][0], base_score), api) # type: ignore
        else:
            scored[key] = (base_score, api) # type: ignore

    # 1. Expand aliases: check if query maps to known terms
    search_terms = [q]
    if q in _SEARCH_ALIASES:
        search_terms.extend(_SEARCH_ALIASES[q])

    for term in search_terms:
        t = term.lower()
        # 2. Name matching
        for name_lower, apis in _name_lower_map.items():
            if t == name_lower:
                for api in apis:
                    add(api, 100)
            elif t in name_lower:
                for api in apis:
                    add(api, 60)

        # 3. Class matching
        for cls, apis in _by_class.items():
            if t == cls.lower():
                for api in apis:
                    add(api, 50)
            elif t in cls.lower():
                for api in apis:
                    add(api, 30)

        # 4. Description matching
        for api in API_DATA:
            desc = api.get("description", "").lower()
            if t in desc:
                add(api, 10)

        # 5. Parameter type matching (e.g., search "int32_t" finds APIs using it)
        for api in API_DATA:
            for param in api.get("parameters", []):
                if t in param.get("type", "").lower() or t in param.get("name", "").lower():
                    add(api, 5)
                    break

    # Sort by score descending, then prefer original query match, then name
    def sort_key(item):
        score, api = item
        name_l = api["name"].lower()
        # Bonus: name starts with original query
        orig_match = 1 if name_l.startswith(q) else 0
        return (-score, -orig_match, name_l)
    results = sorted(scored.values(), key=sort_key)
    return [_format_api_brief(api) for _, api in results[:20]]


@mcp.tool
def get_vex_api_detail(name: str) -> dict | str:
    """【编写VEX代码时调用】获取指定VEX API的完整详细信息。当需要确认函数的确切参数类型、参数顺序、返回值类型，或查看官方示例代码时调用。传入API名称（大小写不敏感），如'spin'、'setVelocity'、'motor'、'pressing'等。返回完整签名、参数列表（含类型和说明）、返回值、示例代码、注意事项。"""
    q = name.lower().strip()

    if q in _name_lower_map:
        apis = _name_lower_map[q]
    else:
        apis = []
        for n, lst in _name_lower_map.items():
            if q in n:
                apis.extend(lst)

    if not apis:
        suggestions = [n for n in _all_names if q[:4] in n.lower()][:5]
        msg = f"未找到 API: '{name}'。"
        if suggestions:
            msg += f" 你是不是想找: {', '.join(suggestions)}"
        return msg

    if len(apis) > 1:
        return [_format_api_full(api) for api in apis] # type: ignore

    return _format_api_full(apis[0])


@mcp.tool
def list_vex_classes() -> list[dict]:
    """【编写VEX代码前调用】列出所有可用的 VEX V5 C++ API 类（共58个）。当不确定某个功能是否有对应API类，或想了解VEX支持哪些硬件/功能时调用。返回类名及每个类的方法数量。常用类：motor, controller, brain, drivetrain, vision, gps, pneumatics 等。"""
    return sorted(
        [{"class": cls, "api_count": len(apis)} for cls, apis in _by_class.items()],
        key=lambda x: x["class"].lower()
    )


# ── Class name aliases: map short/common names to full class names ─────────────
_CLASS_ALIASES = {
    "motor": "Motor and Motor Group",
    "motor_group": "Motor and Motor Group",
    "controller": "Controller",
    "brain": "Brain",
    "competition": "Competition",
    "drivetrain": "Drivetrain",
    "smartdrive": "smartdrive",
    "vision": "Vision Sensor",
    "gps": "GPS Sensor",
    "distance": "Distance Sensor",
    "accelerometer": "Accelerometer",
    "gyro": "Gyro Sensor",
    "inertial": "Inertial Sensor",
    "rotation": "Rotation Sensor",
    "optical": "Optical Sensor",
    "pneumatics": "Pneumatics",
    "bumper": "Bumper Switch",
    "limit": "Limit Switch",
    "encoder": "Encoder",
    "timer": "Timer",
    "screen": "Screen",
    "sd": "SDcard",
}


@mcp.tool
def list_vex_class_methods(class_name: str) -> list[dict] | str:
    """【编写VEX代码时调用】列出指定VEX类的所有方法（构造函数、成员函数、析构函数）。当需要了解某个类的完整API功能列表时调用。传入类名简写或全名（如'motor'→'Motor and Motor Group'），可用别名：motor, controller, brain, drivetrain, vision, gps, pneumatics, distance, inertial, rotation, optical, gyro, accelerometer, bumper, limit, encoder, timer, screen 等。"""
    q = class_name.lower().strip()

    # Resolve aliases first
    lookup = _CLASS_ALIASES.get(q, q).lower()

    # Prefer exact case-insensitive match
    for cls, apis in _by_class.items():
        if cls.lower() == lookup:
            sorted_apis = sorted(apis, key=lambda a: (
                0 if a.get("is_constructor") else (2 if a.get("is_destructor") else 1),
                a["name"].lower()
            ))
            return [_format_api_brief(api) for api in sorted_apis]

    # Fall back to substring match
    for cls, apis in _by_class.items():
        if lookup in cls.lower():
            sorted_apis = sorted(apis, key=lambda a: (
                0 if a.get("is_constructor") else (2 if a.get("is_destructor") else 1),
                a["name"].lower()
            ))
            return [_format_api_brief(api) for api in sorted_apis]

    suggestions = [c for c in ALL_CLASSES if q[:3] in c.lower()][:5]
    msg = f"未找到类: '{class_name}'。"
    if suggestions:
        msg += f" 可用的类: {', '.join(suggestions)}"
    return msg


def _format_api_brief(api: dict) -> dict:
    return {
        "name": api["name"],
        "class": api["class"],
        "signatures": api["signatures"],
        "description": api["description"],
        "is_constructor": api.get("is_constructor", False),
        "is_destructor": api.get("is_destructor", False),
        "url": api["url"],
    }


def _format_api_full(api: dict) -> dict:
    return {
        "name": api["name"],
        "class": api["class"],
        "page_title": api["page_title"],
        "signatures": api["signatures"],
        "description": api["description"],
        "parameters": api["parameters"],
        "return_value": api["return_value"],
        "notes": api["notes"],
        "examples": api["examples"],
        "is_constructor": api.get("is_constructor", False),
        "is_destructor": api.get("is_destructor", False),
        "url": api["url"],
    }


# ── Game Rules ─────────────────────────────────────────────────────────────────
_RULES_DIR = os.path.join(os.path.dirname(__file__), "赛季规则")
_RULES_FILE_CN = os.path.join(_RULES_DIR, "V5RC 26-27 OVERRIDE-0.1 CN.md")
_RULES_FILE_EN = os.path.join(_RULES_DIR, "override-0.1-game-manual.md")

_rule_paragraphs: list[dict] = []  # [{text, source, rule_ids, is_qrg}]
_rules_indexed: bool = False


def _clean_rule_text(text: str) -> str:
    """Remove PDF→Markdown conversion noise from rule text."""
    # Remove form feeds (they can appear mid-line)
    text = text.replace("\f", "")

    # ── Protect section markers that get merged into copyright lines ──
    # In the EN file, "Quick Reference Guide" and "Section N" often appear
    # on the same line as the copyright/version noise after \f removal.
    # Split them onto separate lines before the noise removal pass.
    for marker in [
        "Quick Reference Guide",
        "Table of Contents",
        "Changelog",
        "Prefix",
        "Scoring Rules",
        "Specific Game Rules",
        "Safety Rules",
        "General Rules",
        "General Game Rules",
        "Robot Skills Challenge Rules",
        "Inspection Rules",
        "Tournament Rules",
        "VEX U Game Rules",
        "VEX U Robot Skills Challenge Rules",
        "VEX U Tournament Rules",
        "VEX U Robot Rules",
        "Field Overview",
        "Glossary of Terms",
        "Rule Violations",
        "Team Classifications",
    ]:
        text = re.sub(
            rf"({re.escape(marker)})",
            rf"\n\1\n",
            text,
        )

    # Re-split Section headings that got merged
    text = re.sub(r"(Section\s+\d[\s\w\d-]*)", r"\n\1\n", text)

    # ── EN combined header: "VEX V5 Robotics Competition Override - Game ManualCopyright ..."
    text = re.sub(
        r"VEX V5 Robotics Competition Override\s*[-–]\s*Game[\s]*Manual\s*Copyright.{0,80}?(?:\n|$)",
        "\n", text
    )

    # ── CN copyright + version block (two lines)
    text = re.sub(
        r"Copyright 2026, VEX Robotics Inc\.?\s*\n\s*第 0\.\d 版\s*[-–]\s*\d{4} 年 \d+ 月 \d+ 日发布",
        "", text
    )
    # CN standalone version line
    text = re.sub(r"第 0\.\d 版\s*[-–]\s*\d{4} 年 \d+ 月 \d+ 日发布", "", text)
    # CN vexrobotics.com noise line (may have copyright on same line)
    text = re.sub(
        r"^\s*(?:Copyright 2026, VEX Robotics In[c]?\.?\s*)?vexrobotics\.com\s*$",
        "", text, flags=re.MULTILINE
    )
    # Any copyright line (CN may have "In" without trailing "c.")
    text = re.sub(
        r"^\s*Copyright 2026, VEX Robotics In[c]?\.?\s*$",
        "", text, flags=re.MULTILINE
    )

    # ── EN standalone noise lines
    text = re.sub(r"^Game Manual$", "", text, flags=re.MULTILINE)
    text = re.sub(
        r"^Version 0\.\d\s*[-–]\s*\w+\s+\d+,\s+\d+(?:Quick Reference Guide)?\s*$",
        "", text, flags=re.MULTILINE
    )
    text = re.sub(r"^Version 0\.\d$", "", text, flags=re.MULTILINE)

    # Fix broken URLs (space in URL, or broken across lines)
    text = re.sub(r"(https?://\S+)[ \t]+(\S+)", r"\1\2", text)
    text = re.sub(r"(https?://\S+)\n\s*(\S+)", r"\1\2", text)

    # Remove standalone page numbers (arabic and roman)
    lines = text.split("\n")
    filtered = []
    prev_blank = True
    for i, line in enumerate(lines):
        stripped = line.strip()
        next_blank = (i + 1 >= len(lines)) or not lines[i + 1].strip()

        # Arabic page numbers (1-999) – isolated, surrounded by blanks
        if stripped and re.match(r"^\d{1,3}$", stripped):
            if prev_blank and next_blank:
                continue

        # Roman numeral page numbers (iv–xv)
        if stripped and re.match(
            r"^(iv|v|vi|vii|viii|ix|x|xi|xii|xiii|xiv|xv)$", stripped, re.IGNORECASE
        ):
            if prev_blank and next_blank:
                continue

        filtered.append(line)
        prev_blank = not stripped

    text = "\n".join(filtered)

    # Compress 3+ blank lines → single blank line
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip trailing whitespace
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    # Remove leading blank lines
    text = text.lstrip("\n")

    return text


def _extract_rule_ids(text: str) -> list[str]:
    """Extract rule IDs like R8, SG1, GG12 from <TAG> markers in text."""
    ids = re.findall(
        r"<(R\d+[a-z]?|S\d+|SG\d+|G\d+|GG\d+|T\d+|SC\d+|RSC\d+|VU[GRSTU]?\d+)>",
        text
    )
    return list(dict.fromkeys(ids))  # dedup, preserve order


def _load_and_index_rules() -> list[dict]:
    """Load raw rule files, clean noise, split into paragraphs, and index."""
    global _rule_paragraphs, _rules_indexed
    if _rules_indexed:
        return _rule_paragraphs

    for path, source in [
        (_RULES_FILE_CN, "cn"),
        (_RULES_FILE_EN, "en"),
    ]:
        if not os.path.exists(path):
            continue

        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()

        cleaned = _clean_rule_text(raw)

        # Split into paragraphs (by blank lines)
        paragraphs = re.split(r"\n\n+", cleaned)

        # Detect QRG section boundaries
        in_qrg = False
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Track QRG section – starts at "Quick Reference Guide" / "快速查阅指南",
            # ends at "Section 1" / "第一章"
            if source == "cn":
                if "快速查阅指南" in para:
                    in_qrg = True
                elif re.search(r"第[一二三四五六七八九十]章[：:]", para):
                    in_qrg = False
            else:  # en
                if "Quick Reference Guide" in para:
                    in_qrg = True
                elif re.search(r"^Section\s+1[\s-]", para):
                    in_qrg = False

            rule_ids = _extract_rule_ids(para)

            # Skip paragraphs with no meaningful text after stripping tags
            stripped_no_tags = re.sub(r"<[^>]+>", "", para).strip()
            if not stripped_no_tags or len(stripped_no_tags) < 3:
                continue

            # Skip title-page / front-matter noise: short paras with no rule IDs
            # and no section-heading markers
            if not rule_ids and len(stripped_no_tags) < 50:
                if not re.match(
                    r"^(#+|第[一二三四五六七八九十]章|Section\s+\d|Appendix|附录|[A-Z][a-z]+ Rules)",
                    stripped_no_tags
                ):
                    continue

            # Skip paragraphs that are TOC entries (dotted lines + page numbers).
            # TOC entries have no rule tags; the dotted-line pattern means it's a directory listing.
            if not rule_ids and re.search(r"\.{5,}\s*\d+", stripped_no_tags):
                continue

            _rule_paragraphs.append({
                "text": para,
                "source": source,
                "rule_ids": rule_ids,
                "is_qrg": in_qrg,
            })

    _rules_indexed = True
    return _rule_paragraphs


# ── Keyword expansion map for Chinese and English search ────────────────────
_RULE_KEYWORD_EXPANSION: dict[str, list[str]] = {
    "赛制": ["竞赛规则", "赛局规则", "赛事规则", "赛程", "competition rule", "tournament rule"],
    "新赛季": ["本赛季", "2026", "override", "0.1"],
    "场地": ["field", "场地", "尺寸", "规格", "12' x 12'"],
    "自动": ["autonomous", "自动时段", "autonomous period", "15秒", "15 second"],
    "手动": ["usercontrol", "driver control", "driver controlled", "手动控制"],
    "计分": ["scoring", "score", "得分", "scored", "scoring status"],
    "电机": ["motor", "11w", "5.5w", "智能电机", "smart motor"],
    "马达": ["motor", "11w", "5.5w"],
    "气动": ["pneumatic", "pneumatics", "气缸", "气压", "pressure"],
    "传感器": ["sensor", "vision", "gps", "inertial", "rotation", "optical", "distance"],
    "尺寸": ["dimension", '18"', "体积", "size", "volume", "expand"],
    "展开": ["expansion", "expand", "水平展开", "垂直展开"],
    "停泊": ["park", "parking", "climb", "爬升"],
    "电池": ["battery", "电池", "power", "电源", "lithium"],
    "端口": ["port", "triport", "三线端口", "3-wire"],
    "遥控器": ["controller", "遥控", "手柄", "v5 controller"],
    "主控": ["brain", "主控器", "v5 brain"],
}


def _score_paragraph(
    para: dict, terms: list[str], expanded_terms: list[str], full_query: str
) -> float:
    """Score a paragraph against search terms. Higher is better."""
    score = 0.0
    text_l = para["text"].lower()

    # Full query exact phrase match (strongest signal)
    if full_query in text_l:
        score += 80

    # Count individual term matches
    all_terms = terms + expanded_terms
    matched = sum(1 for t in all_terms if t in text_l)
    score += matched * 20

    # Exact rule ID match (e.g., query "r8" → paragraph contains <R8>)
    for t in terms:
        t_upper = t.upper().strip("<>")
        if t_upper in para["rule_ids"]:
            score += 100

    # Heading / titled paragraph bonus
    stripped = para["text"].strip()
    if re.match(r"^(#|<[RSCTG][CGTU]?\d+[a-z]?.*?>)", stripped):
        score += 20

    # CN source bonus (user is Chinese-speaking, only if already matched)
    if para["source"] == "cn" and score > 0:
        score += 10

    # QRG penalty (quick-reference summaries are less authoritative than full text)
    if para["is_qrg"]:
        score *= 0.1

    return score


@mcp.tool
def search_vex_rules(query: str) -> str:
    """【编写VEX竞赛代码前必须调用】搜索 2026-2027赛季 OVERRIDE 竞赛规则手册。涉及以下任何编程场景都应主动调用此工具检查规则限制：

必查场景：
- 电机编程：数量限制(R10)、子系统1特殊限制(R11)、电机型号(11W)
- 竞赛程序结构：必须用Competition Template(R9)、固件≥1.1.5(R8)
- 自动时段代码：15秒自动时段、自动分界线禁止越过(SG7)、AWP获取条件(SC8)
- 机器人构造编程约束：尺寸18"×18"×18"(R3)、气动系统限制(R25-R26)、V5主控器只能用1个(R6)、遥控器≤2个(R15)、仅VEX电池(R12)
- 赛局策略相关：最多持有1 Pin + 1 Cup(SG6)、水平/垂直展开限制(SG2-SG3)
- 传感器与硬件：传感器使用限制、电子/气动件不得修改(R28)
- 计分逻辑：placed pin标准(SC2)、toggle判定(SC4)、联队占有(SC5)、停泊条件

支持中英文关键词，如"R10""motor limit""autonomous""AWP条件""expansion""pneumatic限制"等。返回规则原文段落。"""
    paragraphs = _load_and_index_rules()
    if not paragraphs:
        return "未找到竞赛规则文件。"

    q = query.lower().strip()

    # Split query into individual search terms (whitespace, commas, Chinese commas)
    terms = [t.strip().lower() for t in re.split(r"[\s,，、]+", q) if t.strip()]

    # Expand keywords: each term may map to more specific search terms
    expanded_terms: list[str] = []
    for t in terms:
        if t in _RULE_KEYWORD_EXPANSION:
            expanded_terms.extend(_RULE_KEYWORD_EXPANSION[t])
    # Also try the full query against the expansion map
    if q in _RULE_KEYWORD_EXPANSION:
        expanded_terms.extend(_RULE_KEYWORD_EXPANSION[q])
    # For Chinese text queries, try partial key matches
    if re.search(r"[\u4e00-\u9fff]", q):
        for key, exps in _RULE_KEYWORD_EXPANSION.items():
            if key in q and key not in terms:
                expanded_terms.extend(exps)

    # Score every paragraph
    scored: list[tuple[float, dict]] = []
    for para in paragraphs:
        s = _score_paragraph(para, terms, expanded_terms, q)
        if s > 0:
            scored.append((s, para))

    # Sort descending by score
    scored.sort(key=lambda x: -x[0])

    # Deduplicate: same rule_ids → keep highest-scoring paragraph
    seen_ids: set[tuple] = set()
    results: list[str] = []
    for s, para in scored:
        id_key = tuple(para["rule_ids"]) if para["rule_ids"] else hash(para["text"][:80])
        if id_key in seen_ids:
            continue
        seen_ids.add(id_key)

        text = para["text"]
        if len(text) > 800:
            text = text[:800] + "..."

        header = f"[{para['source'].upper()}]"
        if para["rule_ids"]:
            header += f" {' '.join('<'+r+'>' for r in para['rule_ids'])}"
        results.append(f"{header}\n{text}")

    if not results:
        return (
            f"未找到与 '{query}' 相关的规则内容。\n\n"
            f"建议尝试：\n"
            f"  - 规则编号：R8 R9 R10 R11 R25 R26 R28 等\n"
            f"  - 中文关键词：电机 气动 自动 计分 尺寸 展开 停泊\n"
            f"  - 英文关键词：motor pneumatic autonomous scoring dimension\n"
            f"  - 赛局规则：SG1-SG12, GG1-GG18\n"
            f"  - 安全/通用规则：S1-S5, G1-G6"
        )

    return "\n\n---\n\n".join(results[:10])


if __name__ == "__main__":
    mcp.run()
