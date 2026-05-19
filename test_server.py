"""
Test VEX MCP server with v2 data.
Run: python test_server.py
"""
import sys

try:
    import fastmcp
    print(f"[OK] FastMCP {fastmcp.__version__}")
except ImportError:
    print("[FAIL] FastMCP not installed. Run: pip install fastmcp")
    sys.exit(1)

import server

print(f"\n[OK] Server loaded: {len(server.API_DATA)} APIs, {len(server.ALL_CLASSES)} classes")

# Test 1: search_vex_api
print("\n" + "="*60)
print("TEST 1: search_vex_api")
print("="*60)

tests = [
    ("motor", "should find Motor class"),
    ("spin", "should find spin function"),
    ("setVelocity", "should find setVelocity (was missing before)"),
    ("pressing", "should find controller button"),
    ("电机", "Chinese alias"),
    ("stop", "should find stop function"),
    ("isDone", "should find isDone"),
]

for query, desc in tests:
    results = server.search_vex_api(query)
    top = results[0]["name"] if results else "NOT FOUND"
    print(f"  '{query}' → {len(results)} results, top: {top} ({desc})")

# Test 2: get_vex_api_detail
print("\n" + "="*60)
print("TEST 2: get_vex_api_detail")
print("="*60)

for name in ["spin", "setVelocity", "motor", "pressing"]:
    detail = server.get_vex_api_detail(name)
    if isinstance(detail, list):
        d = detail[0]
        print(f"  '{name}' → {len(detail)} overloads: {d['signatures'][:2]}") # type: ignore
    elif isinstance(detail, dict):
        print(f"  '{name}' → {detail['name']}: {detail['signatures'][:2]}")
    else:
        print(f"  '{name}' → {detail}")

# Test 3: list_vex_class_methods
print("\n" + "="*60)
print("TEST 3: list_vex_class_methods (exact match fix)")
print("="*60)

for cls in ["Motor and Motor Group", "motor", "controller"]:
    methods = server.list_vex_class_methods(cls)
    if isinstance(methods, list):
        names = [m["name"] for m in methods]
        print(f"  '{cls}' → {len(methods)} methods: {names[:8]}...")
    else:
        print(f"  '{cls}' → {methods}")

# Test 4: Search rules
print("\n" + "="*60)
print("TEST 4: search_vex_rules")
print("="*60)

for query in ["自动阶段", "AWP", "计分", "autonomous"]:
    result = server.search_vex_rules(query)
    lines = result.split('\n')
    print(f"  '{query}' → {len(lines)} lines ({len(result)} chars)")
    # Show first meaningful line
    for line in lines:
        if line.strip() and not line.startswith('---'):
            print(f"    first: {line.strip()[:100]}")
            break

# Test 5: get_vex_code_template
print("\n" + "="*60)
print("TEST 5: get_vex_code_template")
print("="*60)

for tmpl_name in ["competition", "autonomous_basic", "motor_setup"]:
    result = server.get_vex_code_template(tmpl_name)
    lines = result.split('\n')
    print(f"  '{tmpl_name}' → {len(lines)} lines, starts with: {lines[0][:60] if lines else 'EMPTY'}")

# Test 6: get_vex_game_context
print("\n" + "="*60)
print("TEST 6: get_vex_game_context")
print("="*60)

ctx = server.get_vex_game_context()
if isinstance(ctx, dict):
    season = ctx.get("season", "N/A")
    robot = ctx.get("robot_constraints", {})
    timing = ctx.get("match_timing", {})
    print(f"  season: {season}")
    print(f"  starting_size: {robot.get('starting_size', {}).get('value', 'N/A') if isinstance(robot.get('starting_size'), dict) else robot.get('starting_size')}")
    print(f"  motor_limit: {str(robot.get('motor_limit', {}))[:100]}")
    print(f"  autonomous: {timing.get('autonomous_duration', {}).get('value', 'N/A') if isinstance(timing.get('autonomous_duration'), dict) else timing.get('autonomous_duration')}")
else:
    print(f"  {ctx}")

print("\n[DONE]")
