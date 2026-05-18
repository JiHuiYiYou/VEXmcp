"""
分析 searchindex.js 和 objects.inv 的真实结构，
帮助确定 C++ API 数据在哪里。

用法：
    python analyze_sources.py
"""

import json
import zlib
import re
from pathlib import Path
from collections import Counter

INV_PATH = Path(__file__).parent / "objects.inv"
JS_PATH = Path(__file__).parent / "searchindex.js"
INVENTORY_JSON = Path(__file__).parent / "vex_api_inventory.json"


def analyze_objects_inv():
    """分析 objects.inv 内容"""
    print("=" * 60)
    print("📦 objects.inv 分析")
    print("=" * 60)

    # 读 JSON（已解析过的）
    if INVENTORY_JSON.exists():
        with open(INVENTORY_JSON, "r", encoding="utf-8") as f:
            entries = json.load(f)
    else:
        with open(INV_PATH, "rb") as f:
            for _ in range(4):
                f.readline()
            compressed = f.read()
        decompressed = zlib.decompress(compressed).decode("utf-8")
        entries = []
        for line in decompressed.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.strip().split()
            if len(parts) >= 5:
                name = parts[0]
                domain_role = parts[1]
                domain, role = domain_role.split(":", 1) if ":" in domain_role else (domain_role, "")
                uri = parts[3]
                dispname = " ".join(parts[4:]) if len(parts) > 4 else name
                entries.append({
                    "name": name, "domain": domain, "role": role,
                    "uri": uri, "display_name": dispname,
                })

    print(f"总条目: {len(entries)}")

    # 按 domain 统计
    domain_counts = Counter(e["domain"] for e in entries)
    print(f"\nDomain 分布: {dict(domain_counts)}")

    # 按 role 统计
    role_counts = Counter(e["role"] for e in entries)
    print(f"Role 分布: {dict(role_counts)}")

    # 分析 URI 路径结构
    uri_prefixes = Counter()
    for e in entries:
        uri = e["uri"]
        # 提取路径前缀
        parts = uri.split("/")
        if len(parts) > 1:
            uri_prefixes[parts[0]] += 1
        else:
            uri_prefixes[uri] += 1

    print(f"\nURI 顶层目录分布:")
    for prefix, count in uri_prefixes.most_common(20):
        print(f"  {prefix}/ ({count} 条)")

    # 显示所有条目（按URI分组）
    print(f"\n--- 所有条目（前30条）---")
    for e in entries[:30]:
        print(f"  [{e['domain']}:{e['role']}] {e['name'][:60]} -> {e['uri'][:60]}")

    if len(entries) > 30:
        print(f"  ... 还有 {len(entries) - 30} 条")

    # 看看有没有 cpp 相关的 URI
    print(f"\n--- 包含 'cpp' 的条目 ---")
    cpp_related = [e for e in entries if "cpp" in e["uri"].lower() or "cpp" in e["name"].lower()]
    for e in cpp_related:
        print(f"  [{e['domain']}:{e['role']}] {e['name'][:60]} -> {e['uri'][:60]}")
    if not cpp_related:
        print("  ⚠️ 无！objects.inv 中没有任何与 C++ 相关的条目")
        print("  💡 这意味着 C++ API 的 objects.inv 可能在另一个路径")
        print("     例如: https://api.vex.com/v5/home/cpp/objects.inv")


def analyze_searchindex():
    """分析 searchindex.js 内容"""
    print("\n" + "=" * 60)
    print("🔍 searchindex.js 分析")
    print("=" * 60)

    with open(JS_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # 找 Search.setIndex 调用
    match = re.search(r"Search\.setIndex\((.*)\)", content)
    if not match:
        print("❌ 未找到 Search.setIndex 调用")
        return

    # 统计顶层参数个数（按括号深度解析逗号）
    args_str = match.group(1)
    depth = 0
    args = []
    current_start = 0
    for i, c in enumerate(args_str):
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
        elif c == "," and depth == 0:
            args.append(args_str[current_start:i].strip())
            current_start = i + 1
    args.append(args_str[current_start:].strip())

    # Sphinx 标准参数名
    arg_names = ["docnames", "filenames", "titles", "terms", "fulltitles", "objects"]
    print(f"\nSearch.setIndex 参数个数: {len(args)} (标准为 {len(arg_names)})")

    for i, (name, arg) in enumerate(zip(arg_names, args)):
        # 估算大小
        size = len(arg)
        # 看是数组还是其他
        arg_preview = arg[:80] if len(arg) > 80 else arg

        # 计算数组元素个数（粗略：统计 [[ 或 ,[ 模式）
        if arg.startswith("["):
            # 简单计数顶层元素
            depth = 0
            elem_count = 0
            in_string = False
            for c in arg[1:-1]:
                if c == '"' and depth == 0:
                    in_string = not in_string
                elif c == "[" and not in_string:
                    depth += 1
                elif c == "]" and not in_string:
                    depth -= 1
                elif c == "," and depth == 0 and not in_string:
                    elem_count += 1
            elem_count += 1  # 最后一个元素

            print(f"\n  [{i}] {name}: 数组, ~{elem_count} 个元素, {size:,} 字节")
            print(f"      前 100 字符: {arg[:100]}...")
        else:
            print(f"\n  [{i}] {name}: {arg_preview}..., {size:,} 字节")

    # 尝试用 py_mini_racer 解析（如果可用）
    try:
        from py_mini_racer import MiniRacer
        ctx = MiniRacer()
        ctx.eval(content)

        # 真实存在的变量
        for var_name in arg_names:
            try:
                val = ctx.eval(var_name)
                if isinstance(val, list):
                    print(f"\n  ✅ {var_name}: list, len={len(val)}")
                    if len(val) > 0:
                        if isinstance(val[0], list):
                            print(f"     element[0]: list, len={len(val[0])}: {val[0][:5]}...")
                        else:
                            print(f"     element[0]: {val[0]}")
                        if len(val) > 1:
                            print(f"     element[1]: {val[1]}")
                elif isinstance(val, dict):
                    keys = list(val.keys())
                    print(f"\n  ✅ {var_name}: dict, keys={keys[:10]}")
                    if keys:
                        first_key = keys[0]
                        print(f"     {first_key}: {val[first_key]}")
                else:
                    print(f"\n  ✅ {var_name}: {type(val).__name__} = {str(val)[:100]}")
            except Exception as e:
                print(f"\n  ❌ {var_name}: eval 失败 - {e}")

        # 重点看 objects
        print(f"\n--- objects 数组详细分析 ---")
        try:
            objects = ctx.eval("objects")
            if isinstance(objects, list):
                print(f"objects 条目数: {len(objects)}")
                # 显示前 10 条
                for j, obj in enumerate(objects[:10]):
                    print(f"  [{j}] {obj}")
                # 统计 obj[1] (角色/类型)
                if objects and isinstance(objects[0], list):
                    roles = Counter(obj[1] if len(obj) > 1 else "?" for obj in objects)
                    print(f"\n  objects 角色分布: {dict(roles)}")

                    # 筛选 cpp 相关
                    cpp_objs = [o for o in objects if "cpp" in str(o).lower()]
                    print(f"\n  含 'cpp' 的 objects: {len(cpp_objs)}")
                    for o in cpp_objs[:10]:
                        print(f"    {o}")
        except Exception as e:
            print(f"  错误: {e}")

        # 看 docnames
        print(f"\n--- docnames 分析 ---")
        try:
            docnames = ctx.eval("docnames")
            print(f"docnames 条目数: {len(docnames)}")
            for j, dn in enumerate(docnames[:15]):
                print(f"  [{j}] {dn}")

            # 统计路径前缀
            prefixes = Counter()
            for dn in docnames:
                parts = dn.split("/")
                if len(parts) > 1:
                    prefixes[parts[0]] += 1
                else:
                    prefixes[dn] += 1
            print(f"\n  路径前缀分布: {dict(prefixes)}")
        except Exception as e:
            print(f"  错误: {e}")

    except ImportError:
        print("\n⚠️ py_mini_racer 未安装")
        print("   安装命令: pip install py_mini_racer")


def main():
    analyze_objects_inv()
    analyze_searchindex()


if __name__ == "__main__":
    main()
