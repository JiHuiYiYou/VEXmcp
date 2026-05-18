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

_rules_text: str = ""
_rules_loaded: bool = False


def _load_rules() -> str:
    global _rules_text, _rules_loaded
    if not _rules_loaded:
        # Load both CN and EN for bilingual search
        texts = []
        for path in (_RULES_FILE_CN, _RULES_FILE_EN):
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    texts.append(f.read())
        _rules_text = '\n'.join(texts)
        _rules_loaded = True
    return _rules_text


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
    text = _load_rules()
    if not text:
        return "未找到竞赛规则文件。"

    q = query.lower()
    lines = text.split('\n')
    results = []
    context = 4  # lines of context before/after

    for i, line in enumerate(lines):
        if q in line.lower():
            start = max(0, i - context)
            end = min(len(lines), i + context + 1)
            snippet = '\n'.join(lines[start:end])
            # Trim snippet if too long
            if len(snippet) > 500:
                snippet = snippet[:500] + "..."
            results.append(snippet)

    if not results:
        return f"未找到与 '{query}' 相关的规则内容。试试中文关键词？"

    return '\n\n---\n\n'.join(results[:5])


if __name__ == "__main__":
    mcp.run()
