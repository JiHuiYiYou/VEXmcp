"""
分析 searchindex.js 真实结构 - 修正版

之前脚本的两个问题：
1. Search.setIndex 参数解析失败（以为是6个数组参数，实际是1个JSON对象）
2. MiniRacer 无法 eval（Search 对象未定义）

修正方案：直接用正则提取 JSON，然后用 json.loads 解析
"""

import json
import re
from pathlib import Path
from collections import Counter

JS_PATH = Path(__file__).parent / "searchindex.js"


def main():
    with open(JS_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"文件大小: {len(content):,} 字符")
    print(f"前 200 字符:\n{content[:200]}\n")

    # 方法1: 尝试找 Search.setIndex({...}) 并提取 JSON
    # 找 "Search.setIndex(" 后面的内容
    match = re.search(r'Search\.setIndex\(', content)
    if match:
        json_start = match.end()  # Search.setIndex( 之后的位置
        # 从 json_start 开始找 JSON 对象的结束（最后一个 }）
        # 需要括号匹配
        print(f"Search.setIndex 从位置 {match.start()} 开始")
        print(f"JSON 从位置 {json_start} 开始")

        # 找最后一个 ) 之前的内容
        # 从末尾找起，找到最后一个匹配的 )
        depth = 0
        json_end = -1
        for i in range(len(content) - 1, json_start - 1, -1):
            if content[i] == ')':
                if depth == 0:
                    json_end = i
                    break
                depth += 1
            elif content[i] == '(':
                depth -= 1

        if json_end > json_start:
            json_str = content[json_start:json_end]
            print(f"JSON 部分长度: {len(json_str):,} 字符")
            print(f"JSON 开头: {json_str[:100]}...")
            print(f"JSON 结尾: ...{json_str[-100:]}")

            # 尝试解析
            try:
                data = json.loads(json_str)
                print(f"\n✅ JSON 解析成功！")
                print(f"顶层 keys: {list(data.keys())}")

                for key in data:
                    val = data[key]
                    if isinstance(val, list):
                        print(f"\n  {key}: list, len={len(val)}")
                        if val:
                            if isinstance(val[0], (list, dict)):
                                print(f"    element[0] type: {type(val[0]).__name__}")
                                print(f"    element[0]: {str(val[0])[:150]}")
                            else:
                                print(f"    first: {str(val[0])[:100]}")
                                if len(val) > 1:
                                    print(f"    second: {str(val[1])[:100]}")
                    elif isinstance(val, dict):
                        keys = list(val.keys())
                        print(f"\n  {key}: dict, {len(keys)} keys")
                        print(f"    sample keys: {keys[:10]}")
                        if keys:
                            first_val = val[keys[0]]
                            print(f"    {keys[0]}: {str(first_val)[:100]}")
                    else:
                        print(f"\n  {key}: {type(val).__name__} = {str(val)[:100]}")

                # --- 重点分析 ---
                print("\n" + "=" * 60)
                print("🔍 重点分析")

                # docnames 路径分析
                if "docnames" in data:
                    docnames = data["docnames"]
                    # 统计路径前缀
                    prefixes = Counter()
                    for dn in docnames:
                        parts = dn.split("/")
                        if len(parts) > 1:
                            prefixes[parts[0] + "/" + parts[1] if len(parts) > 2 else parts[0]] += 1
                        else:
                            prefixes[dn] += 1
                    print(f"\ndocnames 路径分布:")
                    for prefix, count in prefixes.most_common(20):
                        print(f"  {prefix}/ ({count} 页)")

                    # 找所有 cpp 路径
                    cpp_paths = [d for d in docnames if "cpp" in d.lower()]
                    print(f"\n  含 'cpp' 的路径: {len(cpp_paths)}")
                    for p in cpp_paths:
                        print(f"    {p}")

                # objects 分析
                if "objects" in data:
                    objects = data["objects"]
                    if isinstance(objects, dict):
                        print(f"\nobjects: dict, {len(objects)} keys")
                        # 看看 objects 是不是其实是 terms 的一部分
                        print(f"  (可能是 key: [doc_id_list] 的格式)")
                        sample_keys = list(objects.keys())[:20]
                        for k in sample_keys:
                            v = objects[k]
                            print(f"    '{k}': {str(v)[:100]}")
                    elif isinstance(objects, list):
                        print(f"\nobjects: list, {len(objects)} entries")
                        for obj in objects[:10]:
                            print(f"    {obj}")

            except json.JSONDecodeError as e:
                print(f"\n❌ JSON 解析失败: {e}")
                # 尝试找错误位置
                pos = e.pos
                print(f"  错误位置前后 100 字符: ...{json_str[max(0,pos-50):pos+50]}...")
    else:
        print("❌ 未找到 Search.setIndex")

        # 尝试其他格式
        for pattern in [r'var\s+index\s*=', r'var\s+searchData\s*=', r'window\.__search']:
            if re.search(pattern, content):
                print(f"  找到: {pattern}")
                match = re.search(pattern, content)
                if match:  # 仅在匹配成功时访问属性，原逻辑中未匹配时本就不会执行后续操作
                    print(f"  位置: {match.start()}")


if __name__ == "__main__":
    main()
