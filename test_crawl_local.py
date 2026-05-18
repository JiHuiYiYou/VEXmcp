"""
用已保存的本地 HTML 文件测试爬虫解析逻辑。

用法：
    python test_crawl_local.py
"""

import json
from pathlib import Path
from crawl_vex_api import parse_html, load_searchindex, get_cpp_page_list

# 本地 HTML 文件
LOCAL_HTML = Path(__file__).parent / "Motor and Motor Group _ VEX V5 - C++ API — VEXcode Documentation.html"

# 从 searchindex.js 获取页面元信息
data = load_searchindex(Path(__file__).parent / "searchindex.js")
pages = get_cpp_page_list(data)

# 找到对应的页面信息
page_info = None
for p in pages:
    if "motor_and_motor_group" in p["docname"]:
        page_info = p
        break

if not page_info:
    print("⚠️ 未在 searchindex.js 中找到 motor_and_motor_group")
    page_info = {
        "docname": "home/cpp/Motors_and_MotorControllers/motor_and_motor_group",
        "title": "Motor and Motor Group",
        "url": "https://api.vex.com/v5/home/cpp/Motors_and_MotorControllers/motor_and_motor_group.html",
    }

# 读取本地 HTML
with open(LOCAL_HTML, "r", encoding="utf-8") as f:
    html = f.read()

# 解析
results = parse_html(html, page_info)

print(f"\n提取到 {len(results)} 个 API 条目:\n")
for api in results:
    print(f"{'='*60}")
    print(f"名称: {api['name']}")
    print(f"所属类: {api['class']}")
    print(f"描述: {api['description'][:100]}...")
    print(f"签名数: {len(api['signatures'])}")
    for s in api['signatures']:
        print(f"  → {s}")
    print(f"参数数: {len(api['parameters'])}")
    for p in api['parameters']:
        print(f"  → {p['type']} {p['name']}: {p['description'][:60]}...")
    if api['return_value']:
        print(f"返回值: {api['return_value'][:100]}")
    if api['notes']:
        print(f"注意事项: {len(api['notes'])} 条")
    if api['examples']:
        print(f"示例代码: {len(api['examples'])} 段")
        for ex in api['examples']:
            print(f"  → {ex[:80]}...")
    print()

# 保存
out_path = Path(__file__).parent / "test_output.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"已保存到: {out_path}")
