"""
Test script for VEX MCP server.
Run: python test_server.py
This tests all tools without starting the MCP server.
"""
import json
import sys

# Check dependencies
try:
    import fastmcp
    print(f"[OK] FastMCP {fastmcp.__version__} installed")
except ImportError:
    print("[MISSING] FastMCP not installed. Run: pip install fastmcp")
    sys.exit(1)

# Import server module (this loads vex_cpp_api.json and builds indexes)
import server

print(f"\n[OK] Server loaded: {len(server.API_DATA)} APIs, {len(server.ALL_CLASSES)} classes")

# Test 1: search_vex_api
print("\n" + "="*60)
print("TEST 1: search_vex_api")
print("="*60)

for query in ["motor", "spin", "controller", "电机", "手柄", "distance", "pressing"]:
    results = server.search_vex_api(query)
    print(f"\n  search('{query}') -> {len(results)} results")
    for r in results[:3]:
        ctor = " [C]" if r["is_constructor"] else ""
        dtor = " [D]" if r["is_destructor"] else ""
        print(f"    {r['name']}{ctor}{dtor} ({r['class']}): {r['signatures']}")

# Test 2: get_vex_api_detail
print("\n" + "="*60)
print("TEST 2: get_vex_api_detail")
print("="*60)

for name in ["motor", "spin", "pressing", "setVelocity"]:
    detail = server.get_vex_api_detail(name)
    if isinstance(detail, list):
        print(f"\n  detail('{name}') -> {len(detail)} overloads")
        d = detail[0]
    elif isinstance(detail, dict):
        print(f"\n  detail('{name}') -> {detail['name']}")
        d = detail
    else:
        print(f"\n  detail('{name}') -> {detail[:80]}...")
        continue
    print(f"    Class: {d['class']}")
    print(f"    Signatures: {d['signatures']}")
    print(f"    Params: {len(d.get('parameters', []))}")
    print(f"    Examples: {len(d.get('examples', []))}")

# Test 3: list_vex_classes
print("\n" + "="*60)
print("TEST 3: list_vex_classes")
print("="*60)
classes = server.list_vex_classes()
print(f"  Total: {len(classes)} classes")
for c in classes[:5]:
    print(f"    {c['class']}: {c['api_count']} APIs")

# Test 4: list_vex_class_methods
print("\n" + "="*60)
print("TEST 4: list_vex_class_methods")
print("="*60)

for cls in ["motor", "controller", "brain"]:
    methods = server.list_vex_class_methods(cls)
    if isinstance(methods, list):
        print(f"\n  class '{cls}': {len(methods)} methods")
        for m in methods[:5]:
            ctor = " [C]" if m["is_constructor"] else ""
            dtor = " [D]" if m["is_destructor"] else ""
            print(f"    {m['name']}{ctor}{dtor}: {m['signatures']}")
    else:
        print(f"\n  class '{cls}': {methods}")

# Test 5: alias search
print("\n" + "="*60)
print("TEST 5: Alias searches (Chinese terms)")
print("="*60)
for query in ["电机", "手柄", "气动", "转速", "传感器"]:
    results = server.search_vex_api(query)
    print(f"  search('{query}') -> {len(results)} results: {[r['name'] for r in results[:5]]}")

print("\n[DONE] All tests passed!")
