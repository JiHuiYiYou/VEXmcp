"""
解析 VEX Sphinx objects.inv 文件，提取所有 API 索引。

用法：
    python parse_objects_inv.py

输出：vex_api_inventory.json（结构化 API 清单）
"""

import zlib
import json
import re
from pathlib import Path

INV_PATH = Path(__file__).parent / "objects.inv"
OUT_PATH = Path(__file__).parent / "vex_api_inventory.json"


def parse_objects_inv(path: Path) -> list[dict]:
    """解析 Sphinx objects.inv v2 格式"""

    with open(path, "rb") as f:
        header = f.readline().decode("ascii")  # # Sphinx inventory version 2
    version = int(header.split()[-1])
    print(f"格式版本: v{version}")
    if version != 2:
        raise ValueError(f"不支持的版本: {version}")

    # 跳过 3 行注释
    with open(path, "rb") as f:
        for _ in range(4):
            line = f.readline()
            if line.startswith(b"#"):
                print(f"  注释: {line.decode('ascii').strip()}")

        # 剩余部分是 zlib 压缩数据
        compressed = f.read()

    decompressed = zlib.decompress(compressed).decode("utf-8")
    lines = decompressed.strip().split("\n")

    entries = []
    for line in lines:
        if not line.strip():
            continue
        # 格式: name domain:role priority uri dispname
        parts = line.strip().split()
        if len(parts) < 5:
            continue

        name = parts[0]
        domain_role = parts[1]
        priority = parts[2]
        uri = parts[3]
        dispname = " ".join(parts[4:]) if len(parts) > 4 else name

        if ":" in domain_role:
            domain, role = domain_role.split(":", 1)
        else:
            domain, role = domain_role, ""

        entries.append({
            "name": name,
            "domain": domain,
            "role": role,
            "priority": int(priority) if priority.lstrip("-").isdigit() else priority,
            "uri": uri,
            "anchor": uri.split("#")[-1] if "#" in uri else "",
            "display_name": dispname,
        })

    return entries


def main():
    entries = parse_objects_inv(INV_PATH)
    print(f"\n总计: {len(entries)} 个 API 索引条目\n")

    # 按 domain 统计
    from collections import Counter
    domain_counts = Counter(e["domain"] for e in entries)
    print("=== 按 Domain 统计 ===")
    for d, c in domain_counts.most_common():
        print(f"  {d}: {c}")

    role_counts = Counter(e["role"] for e in entries)
    print("\n=== 按 Role 统计 ===")
    for r, c in role_counts.most_common():
        print(f"  {r}: {c}")

    # 显示 cpp 域的前 20 条
    cpp_entries = [e for e in entries if e["domain"] == "cpp"]
    print(f"\n=== C++ 域条目 ({len(cpp_entries)} 条) ===")
    for e in cpp_entries[:20]:
        print(f"  [{e['role']}] {e['name']}  ->  {e['uri']}")

    if len(cpp_entries) > 20:
        print(f"  ... 还有 {len(cpp_entries) - 20} 条")

    # 保存为 JSON
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"\n已保存到: {OUT_PATH}")

    # 输出所有 API 名称列表
    print("\n=== 全部 C++ API 名称 ===")
    for e in cpp_entries:
        print(f"  {e['name']}")


if __name__ == "__main__":
    main()
