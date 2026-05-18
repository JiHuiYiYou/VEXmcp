import json
with open("vex_cpp_api.json", "r", encoding="utf-8") as f:
    data = json.load(f)
print(f"总计 {len(data)} APIs\n")
for i, api in enumerate(data):
    tag = "[ctor]" if api.get("is_constructor") else ("[dtor]" if api.get("is_destructor") else "[fn  ]")
    sigs = len(api["signatures"])
    print(f"{i:3d}. {tag} {api['name']:35s} ({sigs} sigs)")
