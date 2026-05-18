"""调试脚本：下载一个页面并打印其 DOM 结构"""
from crawl_vex_api import fetch_html, parse_html, load_searchindex, get_cpp_page_list
from bs4 import BeautifulSoup
from pathlib import Path

import json
data = load_searchindex(Path(__file__).parent / "searchindex.js")
pages = get_cpp_page_list(data)

# 测试 3-Wire_Expander（返回 0 API 的页面）
target = [p for p in pages if "3-Wire_Expander" in p["docname"]]
if not target:
    print("未找到 3-Wire_Expander 页面")
    exit()

page = target[0]
html = fetch_html(page["url"])

# 保存原始 HTML
with open("debug_expander.html", "w", encoding="utf-8") as f:
    f.write(html)
print(f"已保存 HTML ({len(html)} chars)")

# 分析结构
soup = BeautifulSoup(html, "html.parser")
article = soup.find("article", class_="bd-article")
if not article:
    print("❌ 未找到 article.bd-article")
    # 尝试其他容器
    for tag in ["main", "div.content", "div.document", "body"]:
        el = soup.find(tag)
        if el:
            print(f"  找到 <{tag}>")
            article = el
            break
    if not article:
        exit()

# 找所有 section
all_sections = article.find_all("section", recursive=True)
print(f"\nSection 总数: {len(all_sections)}")

# 找 h 标签
for i, s in enumerate(all_sections):
    sid = s.get("id", "")
    h = s.find(["h1", "h2", "h3"])
    if h:
        print(f"  [{i}] id='{sid}' <{h.name}>'{h.get_text(strip=True)[:60]}</{h.name}>")

# 找直接子 section
child_sections = article.find_all("section", recursive=False)
if not child_sections:
    child_sections = article.find_all("section", recursive=True)[:1]

print(f"\n直接子 section 数: {len(child_sections)}")

# 用 parse_html 试试
results = parse_html(html, page)
print(f"\nparse_html 结果: {len(results)} APIs")
for r in results:
    print(f"  name={r['name']} class={r['class']} sigs={len(r['signatures'])}")
