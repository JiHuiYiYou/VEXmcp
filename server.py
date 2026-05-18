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
DATA_FILE = os.path.join(os.path.dirname(__file__), "vex_cpp_api.json")
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
    "spin": ["spin", "spinTo", "spinToPosition", "spinFor", "setVelocity"],
    "转动": ["spin", "spinTo", "spinFor", "rotateTo", "rotateFor"],
    "转速": ["setVelocity", "setVelocityCustom"],
    "停止": ["stop", "setStopping", "stopHold", "stopCoast", "stopBrake"],
    "制动": ["setStopping", "stopHold", "stopBrake"],
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
    """搜索 VEX V5 C++ API。输入关键词、API名称、类名或中文术语（如"电机""手柄""传感器""转速"），返回匹配的API列表。每个结果包含名称(name)、类名(class)、签名(signatures)、描述(description)、是否为构造函数/析构函数等简要信息。"""
    q = query.lower().strip()
    scored: dict[int, dict] = {}  # id(api) -> (score, api)

    def add(api, base_score=0):
        key = id(api)
        if key in scored:
            scored[key] = (max(scored[key][0], base_score), api)
        else:
            scored[key] = (base_score, api)

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

    # Sort by score descending, then name
    results = sorted(scored.values(), key=lambda x: (-x[0], x[1]["name"].lower()))
    return [_format_api_brief(api) for _, api in results[:20]]


@mcp.tool
def get_vex_api_detail(name: str) -> dict | str:
    """获取指定 VEX API 的完整详细信息。包含所有签名、参数列表（含类型和说明）、返回值、示例代码、备注等。传入 API 名称（大小写不敏感），如 'motor'、'spin'、'pressing'。"""
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
        return [_format_api_full(api) for api in apis]

    return _format_api_full(apis[0])


@mcp.tool
def list_vex_classes() -> list[dict]:
    """列出所有可用的 VEX V5 C++ API 类。返回类名及每个类的 API 数量。用于了解有哪些类可用。"""
    return sorted(
        [{"class": cls, "api_count": len(apis)} for cls, apis in _by_class.items()],
        key=lambda x: x["class"].lower()
    )


@mcp.tool
def list_vex_class_methods(class_name: str) -> list[dict] | str:
    """列出指定 VEX 类的所有方法（构造函数、成员函数、析构函数）。传入类名（大小写不敏感），如 'motor'、'controller'。返回该方法列表的简要信息。"""
    q = class_name.lower().strip()

    for cls, apis in _by_class.items():
        if q in cls.lower():
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


if __name__ == "__main__":
    mcp.run()
