import json
with open("vex_cpp_api.json", "r", encoding="utf-8") as f:
    data = json.load(f)

ctors = sum(1 for a in data if a.get("is_constructor"))
dtors = sum(1 for a in data if a.get("is_destructor"))
fns = len(data) - ctors - dtors

print(f"总计: {len(data)} APIs")
print(f"  构造函数: {ctors}")
print(f"  析构函数: {dtors}")
print(f"  成员函数: {fns}")
print()
print("质量检查:")
print(f"  无签名: {sum(1 for a in data if not a['signatures'])}")
print(f"  无描述: {sum(1 for a in data if not a['description'])}")
print(f"  有参数: {sum(1 for a in data if a['parameters'])}")
print(f"  有示例: {sum(1 for a in data if a['examples'])}")
print(f"  有备注: {sum(1 for a in data if a['notes'])}")
print(f"  有返回值: {sum(1 for a in data if a['return_value'])}")

# 按 class 统计
from collections import Counter
classes = Counter(a["class"] for a in data if a["class"])
print(f"\n类分布 (Top 20):")
for cls, cnt in classes.most_common(20):
    print(f"  {cls}: {cnt} APIs")
