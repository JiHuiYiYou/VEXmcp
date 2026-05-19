"""
Clean PDF→Markdown conversion artifacts from VEX competition rule files.

Removes:
- Form feed characters (\\f)
- Page header/footer noise (copyright, version, page numbers)
- Repeated copyright+version combo lines
- Bare page numbers between noise lines

Fixes:
- URLs broken across lines (spaces in URLs)
- Compresses 3+ blank lines to 1

Output: .clean.md files in the same directory.
Originals are preserved.
"""

import re
import os


def clean_text(text: str, lang: str = "cn") -> str:
    """Remove PDF→MD conversion noise from rule text."""

    # ── 1. Remove form feed characters ──
    text = text.replace("\f", "")

    # ── 2. Remove combined header lines ──
    # EN: "VEX V5 Robotics Competition Override - Game ManualCopyright 2026..."
    text = re.sub(
        r"VEX V5 Robotics Competition Override\s*[-–]\s*Game[\s]*Manual\s*Copyright.{0,80}?(?:\n|$)",
        "\n",
        text,
    )

    # ── 3. Remove CN copyright + version blocks ──
    text = re.sub(
        r"Copyright 2026, VEX Robotics Inc\.?\s*\n\s*第 0\.\d 版\s*[-–]\s*\d{4} 年 \d+ 月 \d+ 日发布",
        "",
        text,
    )
    # Standalone CN lines
    text = re.sub(r"第 0\.\d 版\s*[-–]\s*\d{4} 年 \d+ 月 \d+ 日发布", "", text)
    text = re.sub(r"^\s*Copyright 2026, VEX Robotics Inc\.?\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*vexrobotics\.com\s*$", "", text, flags=re.MULTILINE)

    # ── 4. Remove EN standalone noise lines ──
    text = re.sub(r"^Game Manual$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^Version 0\.\d\s*[-–]\s*\w+\s+\d+,\s+\d+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^Version 0\.\d$", "", text, flags=re.MULTILINE)

    # ── 5. Fix broken URLs (spaces in URLs) ──
    # e.g., "https://link.vex.com/ firmware" → "https://link.vex.com/firmware"
    text = re.sub(r"(https?://\S+)[ \t]+(\S+)", r"\1\2", text)
    # Also fix URLs broken across lines
    text = re.sub(r"(https?://\S+)\n\s*(\S+)", r"\1\2", text)

    # ── 6. Remove standalone page numbers ──
    lines = text.split("\n")
    filtered = []
    prev_blank = True

    for i, line in enumerate(lines):
        stripped = line.strip()
        next_blank = (i + 1 >= len(lines)) or not lines[i + 1].strip()

        # Arabic page numbers (1-999) on their own, surrounded by blanks
        if stripped and re.match(r"^\d{1,3}$", stripped):
            if prev_blank and next_blank:
                continue

        # Roman numeral page numbers (iv, v, vi, vii, viii, ix, x, xi, xii)
        if stripped and re.match(r"^(iv|v|vi|vii|viii|ix|x|xi|xii|xiii|xiv|xv)$", stripped, re.IGNORECASE):
            if prev_blank and next_blank:
                continue

        filtered.append(line)
        prev_blank = not stripped

    text = "\n".join(filtered)

    # ── 7. Compress multiple blank lines (3+ → 1) ──
    text = re.sub(r"\n{3,}", "\n\n", text)

    # ── 8. Remove trailing whitespace ──
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)

    # ── 9. Remove leading blank lines ──
    text = text.lstrip("\n")

    return text


def clean_file(input_path: str, output_path: str, lang: str = "cn"):
    """Read, clean, and write a rule file."""
    if not os.path.exists(input_path):
        print(f"SKIP (not found): {input_path}")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        raw = f.read()

    cleaned = clean_text(raw, lang)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(cleaned)

    orig_size = os.path.getsize(input_path)
    clean_size = os.path.getsize(output_path)
    reduction = (1 - clean_size / orig_size) * 100 if orig_size > 0 else 0

    print(f"Cleaned: {os.path.basename(input_path)}")
    print(f"  {orig_size:,} → {clean_size:,} bytes ({reduction:.0f}% noise removed)")
    print(f"  Output: {os.path.basename(output_path)}")


if __name__ == "__main__":
    rules_dir = os.path.join(os.path.dirname(__file__), "赛季规则")

    print("=" * 60)
    print("VEX Rule File Cleaner")
    print("=" * 60)

    clean_file(
        os.path.join(rules_dir, "V5RC 26-27 OVERRIDE-0.1 CN.md"),
        os.path.join(rules_dir, "V5RC 26-27 OVERRIDE-0.1 CN.clean.md"),
        lang="cn",
    )

    print()

    clean_file(
        os.path.join(rules_dir, "override-0.1-game-manual.md"),
        os.path.join(rules_dir, "override-0.1-game-manual.clean.md"),
        lang="en",
    )

    print()
    print("Done. Original files are preserved.")
