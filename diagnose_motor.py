"""
Diagnose why the crawler missed member functions on the Motor page.
Run: python diagnose_motor.py
"""
from bs4 import BeautifulSoup, Tag
import re

HTML_FILE = r"C:\Users\liuzhen\Desktop\coding\projects\VEXmcp\Motor and Motor Group _ VEX V5 - C++ API — VEXcode Documentation.html"

with open(HTML_FILE, "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

def _htext(tag):
    text = tag.get_text(strip=True)
    return text.rstrip("#").strip()

# Find the article
article = soup.find("article", class_="bd-article")
if not article:
    print("ERROR: No article.bd-article found!")
    exit(1)

page_section = article.find("section")
if not page_section:
    print("ERROR: No top-level section found!")
    exit(1)

print(f"Page title (h1): {_htext(page_section.find('h1'))}")

# Check direct child sections
child_sections = page_section.find_all("section", recursive=False)
print(f"\nDirect child sections: {len(child_sections)}")

# Check h2 vs h3 presence
has_h2 = any(s.find("h2", recursive=False) for s in child_sections)
has_h3 = any(s.find("h3", recursive=False) for s in child_sections)
print(f"Has h2: {has_h2}, Has h3: {has_h3}")

for i, child in enumerate(child_sections):
    sid = child.get("id", "[no id]")
    h2 = child.find("h2", recursive=False)
    h3 = child.find("h3", recursive=False)
    h_text = _htext(h2) if h2 else (_htext(h3) if h3 else "[no heading]")
    h_level = "h2" if h2 else ("h3" if h3 else "none")

    # Count children
    sub_sections = child.find_all("section", recursive=False)
    code_blocks = child.find_all("code", class_="language-cpp")

    print(f"\n  [{i}] id='{sid}' {h_level}='{h_text}'")
    print(f"      sub-sections: {len(sub_sections)}, code blocks: {len(code_blocks)}")

    if sub_sections:
        for j, sub in enumerate(sub_sections):
            sub_id = sub.get("id", "[no id]")
            sub_h = sub.find(["h2", "h3", "h4"], recursive=False)
            sub_text = _htext(sub_h) if sub_h else "[no heading]"
            sub_codes = len(sub.find_all("code", class_="language-cpp"))
            print(f"        [{j}] id='{sub_id}' heading='{sub_text}' codes:{sub_codes}")

    # Show code samples
    for code in code_blocks[:3]:
        text = code.get_text(strip=True)[:100]
        parent = code.parent.name if code.parent else "?"
        print(f"      code (parent={parent}): {text}...")

# Simulate the crawler's decision
print("\n\n=== Simulating crawler decision ===")
if has_h2 and not has_h3:
    print("Parser would use: _parse_simple_page (Structure B)")
    print("This means each child section is treated as ONE function.")
    print("Checking what each section would produce...")

    for i, child in enumerate(child_sections):
        sid = child.get("id", "")
        h2 = child.find("h2", recursive=False)
        h2_text = _htext(h2) if h2 else ""

        if sid in ("class-constructor", "class-constructors"):
            sigs = [c.get_text(strip=True)[:80] for c in child.find_all("code", class_="language-cpp")]
            print(f"  [{i}] CONSTRUCTOR: {sigs}")
        elif sid in ("class-destructor", "class-destructors"):
            sigs = [c.get_text(strip=True)[:80] for c in child.find_all("code", class_="language-cpp")]
            print(f"  [{i}] DESTRUCTOR: {sigs}")
        elif sid in ("introduction", "examples", "notes", "id1"):
            print(f"  [{i}] SKIPPED (id={sid})")
        else:
            sigs = [c.get_text(strip=True)[:80] for c in child.find_all("code", class_="language-cpp")]
            if sigs:
                print(f"  [{i}] MEMBER FN (h2='{h2_text}'): {sigs}")
            else:
                # Check sub-sections
                subs = child.find_all("section", recursive=False)
                if subs:
                    print(f"  [{i}] HAS {len(subs)} SUB-SECTIONS (but parser doesn't recurse!)")
                    for sub in subs:
                        sub_h = sub.find(["h3", "h4"], recursive=False)
                        sub_text = _htext(sub_h) if sub_h else "?"
                        sub_codes = [c.get_text(strip=True)[:80] for c in sub.find_all("code", class_="language-cpp")]
                        print(f"       - '{sub_text}': {sub_codes}")
else:
    print("Parser would use: _parse_complex_page (Structure A)")
