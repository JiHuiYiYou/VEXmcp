"""
Fix vex_cpp_api.json: split "Member Functions" and other grouped entries into
individual API entries. Handles Prism.js spaceless tokens and filters examples.

Run: python fix_data.py
Output: vex_cpp_api_v2.json
"""

import json
import re
import os

# ── Helpers ───────────────────────────────────────────────────────────────────

# Known VEX types (lowercase) for filtering examples vs signatures
_KNOWN_TYPES = {
    "void", "bool", "int", "int32_t", "int8_t", "uint8_t", "uint32_t",
    "double", "float", "char", "const", "static", "virtual",
    "directionType", "rotationUnits", "velocityUnits", "voltageUnits",
    "percentUnits", "temperatureUnits", "torqueUnits", "powerUnits",
    "currentUnits", "analogUnits", "distanceUnits", "timeUnits",
    "brakeType", "gearSetting", "controllerType", "signaltower",
    "color", "fontType", "triport", "vex", "motor", "motor_group",
    "competition", "controller", "axis", "button", "pneumatic",
}

_WORD_RE = re.compile(r'\b\w+\b|[<>,&*;()[\]]')

def _is_type_like(word: str) -> bool:
    """Check if a word looks like a type name rather than a variable name.
    Types: lowercase start, known C++ types, or CamelCase VEX types.
    Variables: start with uppercase followed by digit (Motor1), or known variable patterns."""
    if not word:
        return False
    if word in _KNOWN_TYPES:
        return True
    if word.lower() in _KNOWN_TYPES:
        return True
    # VEX type names: CamelCase ending with "Type", "Units", etc.
    if word[0].isupper() and (word.endswith("Type") or word.endswith("Units") or word.endswith("Sensor")):
        return True
    # Variable-like: CamelCase with digit (Motor1, LeftMotor, etc.)
    if word[0].isupper() and any(c.isdigit() for c in word):
        return False
    # Lowercase = likely type (int32_t, etc.)
    if word[0].islower():
        return True
    return False


def _is_signature(text: str) -> bool:
    """Check if text looks like a function signature (not an example call)."""
    # Remove comments
    clean = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    clean = re.sub(r'//.*$', '', clean)
    clean = clean.strip()
    if not clean:
        return False
    # Must contain parentheses
    if '(' not in clean or ')' not in clean:
        return False
    # Must end with semicolon
    if not clean.rstrip().endswith(';'):
        return False
    # Must not have multiple statements (examples often have motor.spin();wait();)
    # Count semicolons outside parens
    depth = 0
    semicolons = 0
    for ch in clean:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == ';' and depth == 0:
            semicolons += 1
    if semicolons > 1:
        return False
    # Must start with a type-like word, not an object reference
    words = clean.split()
    if not words:
        return False
    first_word = words[0]
    # If first word contains a dot, it's an example (Motor1.spin(...))
    if '.' in first_word:
        return False
    # If first word starts with uppercase and contains number, it's a variable
    if first_word[0].isupper() and any(c.isdigit() for c in first_word):
        return False
    return True


def _reinsert_spaces(text: str) -> str:
    """Reinsert spaces that Prism.js syntax highlighting removed between tokens.

    Prism.js wraps each token in <span>, and get_text() by default joins them
    without whitespace. This function uses a heuristic: insert space between
    lowercase→uppercase transitions, and around known delimiters.

    But since we're working with cleaned text (after crawler's _clean_code),
    we need a different approach. The crawler already extracted the text.
    We need to fix the spaceless concatenation.
    """
    # The crawler's _clean_code strips HTML and gets text.
    # Space-less signatures like "voidspin(" need to become "void spin("

    # Pattern: lowercase word followed by another word (CamelCase boundary)
    # Example: "voidspin(" → "void spin("
    # Example: "boolisSpinning(" → "bool isSpinning("

    result = text

    # Insert space before capital letter that follows a lowercase letter
    # "voidspin" → "void spin"
    result = re.sub(r'([a-z])([A-Z])', r'\1 \2', result)

    # Insert space after known types that are concatenated
    # "int32_tindex" → "int32_t index"
    result = re.sub(r'(_t)([a-zA-Z])', r'\1 \2', result)

    # "doublevelocity" → "double velocity"
    result = re.sub(r'(double)([a-zA-Z])', r'\1 \2', result, flags=re.IGNORECASE)

    return result


def _split_params(s: str) -> list[str]:
    """Split parameter string by commas, respecting angle brackets and parentheses."""
    parts = []
    depth = 0
    current = []
    for ch in s:
        if ch in '<(':
            depth += 1
        elif ch in '>)':
            depth -= 1
        if ch == ',' and depth == 0:
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        parts.append(''.join(current).strip())
    return [p for p in parts if p]


def _parse_sig_params(params_str: str) -> list[dict]:
    """Parse parameter string into list of {name, type, description} dicts."""
    if not params_str.strip():
        return []

    params = []
    for part in _split_params(params_str):
        # Remove default values (=xxx)
        part = re.sub(r'=.*$', '', part).strip()
        tokens = part.split()
        if len(tokens) >= 2:
            param_name = tokens[-1]
            param_type = " ".join(tokens[:-1])
            params.append({"name": param_name, "type": param_type, "description": ""})
        elif len(tokens) == 1 and tokens[0]:
            params.append({"name": "", "type": tokens[0], "description": ""})
    return params


def _extract_functions_from_code_blocks(code_blocks: list[str]) -> list[dict]:
    """Parse a list of code strings and extract individual function signatures.
    Returns list of {name, signature, return_value, parameters} dicts."""
    results = []
    seen = set()

    for raw in code_blocks:
        raw = raw.strip()
        if not raw:
            continue

        # Try to reinsert spaces lost by Prism.js highlighting
        text = _reinsert_spaces(raw)

        # Split by lines (some code blocks have multiple lines)
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue

            if not _is_signature(line):
                continue

            # Clean up: remove block comments, line comments
            clean = re.sub(r'/\*.*?\*/', '', line, flags=re.DOTALL)
            clean = re.sub(r'//.*$', '', clean).strip()

            if not clean:
                continue

            # Remove trailing semicolon
            clean_ns = clean.rstrip(';').strip()

            # Match: virtual? return_type func_name ( params )
            match = re.match(
                r'^(?:virtual\s+)?(.*?)\s+(\w+)\s*\(([^)]*)\)\s*$',
                clean_ns
            )

            if not match:
                # Try without space between type and name (Prism.js issue)
                match = re.match(
                    r'^(?:virtual\s+)?(.+?[a-zA-Z_])([A-Z][a-zA-Z0-9_]*|[a-z][a-zA-Z0-9_]*)\s*\(([^)]*)\)\s*$',
                    clean_ns
                )

            if not match:
                continue

            return_type = match.group(1).strip()
            func_name = match.group(2).strip()
            params_str = match.group(3).strip()

            # Filter: skip if func_name looks like a type name
            if func_name in _KNOWN_TYPES:
                continue
            # Skip constructors/destructors (handled separately)
            if func_name.startswith('~'):
                continue
            # Skip single-letter names (usually noise)
            if len(func_name) <= 1:
                continue

            # Reconstruct clean signature
            clean_sig = f"{return_type} {func_name}({params_str});"

            key = (func_name, clean_sig)
            if key in seen:
                continue
            seen.add(key)

            parsed_params = _parse_sig_params(params_str)

            results.append({
                "name": func_name,
                "signature": clean_sig,
                "return_value": return_type,
                "parameters": parsed_params,
            })

    return results


# ── Main ─────────────────────────────────────────────────────────────────────

DATA_FILE = os.path.join(os.path.dirname(__file__), "vex_cpp_api.json")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "vex_cpp_api_v2.json")

with open(DATA_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

group_names = {"Member Functions", "Global Variables", "Enum", "Enums"}
new_data = []

for api in data:
    name = api.get("name", "")

    if name in group_names:
        signatures = api.get("signatures", [])

        if not signatures:
            new_data.append(api)
            continue

        # Parse function signatures from the code blocks
        funcs = _extract_functions_from_code_blocks(signatures)

        if not funcs:
            # Can't split, keep original
            new_data.append(api)
            continue

        for f in funcs:
            new_entry = {
                "name": f["name"],
                "class": api["class"],
                "page": api["page"],
                "page_title": api["page_title"],
                "url": api["url"],
                "signatures": [f["signature"]],
                "description": api.get("description", ""),
                "parameters": f.get("parameters", api.get("parameters", [])),
                "return_value": f.get("return_value", api.get("return_value", "")),
                "notes": api.get("notes", []),
                "examples": api.get("examples", []),
                "is_constructor": False,
                "is_destructor": False,
                "is_member_function": True,
            }
            new_data.append(new_entry)
    else:
        new_data.append(api)

# ── Deduplicate: merge entries with same name+class (keep the one with most info) ──
deduped = {}
for api in new_data:
    key = (api["name"], api["class"])
    if key in deduped:
        existing = deduped[key]
        # Merge signatures
        for sig in api["signatures"]:
            if sig not in existing["signatures"]:
                existing["signatures"].append(sig)
        # Keep longer description
        if len(api.get("description", "")) > len(existing.get("description", "")):
            existing["description"] = api["description"]
        # Merge parameters (keep the ones with more detail)
        if len(api.get("parameters", [])) > len(existing.get("parameters", [])):
            existing["parameters"] = api["parameters"]
        # Merge examples
        for ex in api.get("examples", []):
            if ex not in existing.get("examples", []):
                existing["examples"].append(ex)
    else:
        deduped[key] = dict(api)

new_data = list(deduped.values())

# Save
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(new_data, f, indent=2, ensure_ascii=False)

# ── Stats ─────────────────────────────────────────────────────────────────────
ctors = sum(1 for a in new_data if a.get("is_constructor"))
dtors = sum(1 for a in new_data if a.get("is_destructor"))
members = sum(1 for a in new_data if a.get("is_member_function"))
other = len(new_data) - ctors - dtors - members

print(f"Original: {len(data)} entries")
print(f"Fixed:   {len(new_data)} entries (deduplicated)")
print(f"  Constructors:        {ctors}")
print(f"  Destructors:         {dtors}")
print(f"  Member functions:    {members}")
print(f"  Other (uncategorized): {other}")

# Samples
print("\n--- Sample member functions ---")
seen = set()
count = 0
for a in sorted(new_data, key=lambda x: x["name"].lower()):
    if a.get("is_member_function"):
        key = f"{a['name']}::{a['class']}"
        if key not in seen:
            seen.add(key)
            print(f"  {a['name']} ({a['class']}): {a['signatures'][0]}")
            count += 1
            if count >= 30:
                break

# Per-class
print("\n--- Per-class (top 20) ---")
class_summary = {}
for a in new_data:
    cls = a["class"]
    if cls not in class_summary:
        class_summary[cls] = {"C": 0, "D": 0, "M": 0, "?": 0}
    if a.get("is_constructor"):
        class_summary[cls]["C"] += 1
    elif a.get("is_destructor"):
        class_summary[cls]["D"] += 1
    elif a.get("is_member_function"):
        class_summary[cls]["M"] += 1
    else:
        class_summary[cls]["?"] += 1

for cls, s in sorted(class_summary.items(), key=lambda x: -sum(x[1].values()))[:20]:
    total = sum(s.values())
    print(f"  {cls}: {total} (C:{s['C']} D:{s['D']} M:{s['M']} O:{s['?']})")

# Key API checks
print("\n--- Key API checks ---")
targets = ["spin", "setVelocity", "setStopping", "pressing", "released",
           "setMaxTorque", "resetRotation", "setRotation", "spinTo",
           "spinFor", "rotateTo", "stop", "isDone", "isSpinning",
           "current", "voltage", "temperature", "position",
           "velocity", "setPosition", "efficiency", "torque", "power",
           "setTimeout", "direction", "installed", "count",
           "spinToPosition", "open", "close", "extend", "retract"]
found = set()
for a in new_data:
    for t in targets:
        if a["name"].lower() == t.lower():
            found.add(t)
            entry = a["signatures"][0] if a["signatures"] else "?"
            print(f"  FOUND '{t}' → {a['name']} ({a['class']}): {entry}")
            break

missing = [t for t in targets if t not in found]
if missing:
    print(f"\n  STILL MISSING ({len(missing)}): {missing}")
