"""
VEX V5 C++ API 爬虫

从 api.vex.com 爬取 66 个 C++ 文档页面，提取结构化 API 数据。

用法：
    python crawl_vex_api.py              # 爬取全部 66 页
    python crawl_vex_api.py --limit 3    # 只爬前 3 页（测试用）
    python crawl_vex_api.py --local ./html  # 从本地 HTML 文件读取

输出：vex_cpp_api.json
"""

import json
import re
import time
import argparse
from pathlib import Path
from collections import Counter

import requests
from bs4 import BeautifulSoup, Tag

BASE_URL = "https://api.vex.com/v5/"
SEARCHINDEX_PATH = Path(__file__).parent / "searchindex.js"
OUTPUT_PATH = Path(__file__).parent / "vex_cpp_api.json"


# ─── 1. 从 searchindex.js 获取 C++ 页面列表 ───

def load_searchindex(path: Path) -> dict:
    """解析 Sphinx searchindex.js，返回 JSON 数据"""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Search.setIndex({...}) → 提取 {} 中的 JSON
    m = re.search(r"Search\.setIndex\((.+)\)\s*$", content, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    # Fallback: 整个文件就是 JSON
    return json.loads(content)


def get_cpp_page_list(data: dict) -> list[dict]:
    """返回 C++ 页面列表 [{docname, title, url}]"""
    pages = []
    for i, docname in enumerate(data["docnames"]):
        if "cpp" in docname:
            pages.append({
                "docname": docname,
                "title": data["titles"][i],
                "url": f"{BASE_URL}{docname}.html",
            })
    return pages


# ─── 2. 单个页面解析 ───

# 全局 session（复用浏览器 cookie 避免 Cloudflare 403）
_session = None

# 从浏览器复制的关键 headers（标头.txt）
BROWSER_COOKIE = (
    "_ga=GA1.1.511505595.1778859563; "
    "_ga_LL95TVTM1K=GS2.1.s1778859561$o1$g1$t1778859595$j26$l0$h0; "
    "_cf_clearance=WW2iZtT135zF4SVjPCwrJQ8ru1You8ePN9.CNicDM-1779002877-1.2.1.1-"
    "1QZY7A7M_Tv8sr7VPTM1wAa.pZ2CQtqhh3mGeYUKsAlnfM7jQ9uwZRAgg5gx2t1zHEbuP_Jq"
    "8LgRYPb8j4hH2RuFb73pbkHlPGcNurEqWRlGwNnNtcl7BuPEONYQpblt2e3epdhoD61Oh6r"
    "gUV571uh5zQQOgbLjW6IHSz2JAz5h_ldldNSUPVWbm6s8kbUscHoICFQAn5YFsWqji05aKRG"
    "7sQhi79djHciE3E6QdFFpwk0nihr3GuBofeXc4BOWwOlgBcgnvwmYlYKuxReJLFOzYT0jEP"
    "LUoRcAY.mP4wQdBVnaGTJUucN7JNmSKcWvSV2Dzwxqul39Ja1BqiDg; "
    "_cf_bm=2WiOBsrIQyEoLp1WTib1nPUfaw8.vkk7lnA6Xem5prI-1779002877.09344-1.0.1.1-"
    "wSr0sg8Ayu8lCDEaESk4YQb2WhkYAD0QB1GlVePx6i_PqaDPIU.JVcQ6IZStV48TlgHafgh6"
    "SQZBPriqUF9pSe.tpNJuBYdFJPUkY1sO6uB5qvl4CYCaAQVw_D1aH4"
)


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Cache-Control": "no-cache",
            "Sec-Ch-Ua": '"Chromium";v="148", "Microsoft Edge";v="148", "Not/A)Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
        })
        _session.cookies.update({
            k: v for k, v in
            [p.split("=", 1) for p in BROWSER_COOKIE.replace(" ", "").split(";") if "=" in p]
        })
    return _session


def fetch_html(url: str) -> str:
    """下载 HTML 页面"""
    session = _get_session()
    headers = {"Referer": "https://api.vex.com/v5/"}
    resp = session.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_html(html: str, page_info: dict) -> list[dict]:
    """解析 VEX C++ API 页面（自动适配多种结构）"""
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article", class_="bd-article")
    if not article:
        return []

    page_section = article.find("section")
    if not page_section:
        return []

    page_title = _htext(page_section.find("h1")) if page_section.find("h1") else page_info["title"]

    # 判断页面结构：检测直接子 section 用的是 h2 还是 h3
    child_sections = page_section.find_all("section", recursive=False)
    has_h2 = any(s.find("h2", recursive=False) for s in child_sections)
    has_h3 = any(s.find("h3", recursive=False) for s in child_sections)

    results = []

    if has_h2 and not has_h3:
        # 结构 B：简单单类页面（h2 作为段落标题）
        results = _parse_simple_page(page_section, page_title, page_info)
    else:
        # 结构 A：复杂多类页面（h2=类名, h3=函数名）
        results = _parse_complex_page(page_section, page_title, page_info)

    return results


def _parse_simple_page(page_section, page_title, page_info) -> list[dict]:
    """结构 B：单类页面。h1=类名，h2=段落标题"""
    class_name = page_title
    results = []
    ctor_params = []
    ctor_sigs = []
    ctor_desc = ""
    dtor_sigs = []
    dtor_desc = ""

    for child in page_section.find_all("section", recursive=False):
        sid = child.get("id", "")
        h2 = child.find("h2", recursive=False)
        h2_text = _htext(h2) if h2 else ""

        if sid in ("class-constructor", "class-constructors"):
            ctor_sigs = _extract_signatures(child)
            ctor_desc = _extract_description(child)
            ctor_params = _extract_params(child)
        elif sid in ("class-destructor", "class-destructors"):
            dtor_sigs = _extract_signatures(child)
            dtor_desc = _extract_description(child)
        elif sid == "parameters":
            ctor_params = _extract_params(child)
        elif sid in ("introduction", "examples", "notes", "id1"):
            continue
        else:
            # 其他 section → 成员函数
            sigs = _extract_signatures(child)
            if sigs:
                api = _parse_function_section(child, _htext(h2) if h2 else sid, page_info, page_title, class_name)
                if api:
                    results.append(api)

    if ctor_sigs:
        results.insert(0, {
            "name": class_name,
            "class": class_name,
            "page": page_info["docname"],
            "page_title": page_title,
            "url": page_info["url"],
            "signatures": ctor_sigs,
            "description": ctor_desc,
            "parameters": ctor_params,
            "return_value": "",
            "notes": [],
            "examples": _extract_examples_from_page(page_section),
            "is_constructor": True,
        })

    if dtor_sigs:
        results.insert(1 if ctor_sigs else 0, {
            "name": f"~{class_name}",
            "class": class_name,
            "page": page_info["docname"],
            "page_title": page_title,
            "url": page_info["url"],
            "signatures": dtor_sigs,
            "description": dtor_desc,
            "parameters": [],
            "return_value": "",
            "notes": [],
            "examples": [],
            "is_destructor": True,
        })

    return results


def _parse_complex_page(page_section, page_title, page_info) -> list[dict]:
    """结构 A：多类/多函数页面。h2=类名/大段落，h3=函数名"""
    results = []

    for child in page_section.find_all("section", recursive=False):
        h_tag = child.find(["h2", "h3"], recursive=False)
        if not h_tag:
            continue

        tag_text = _htext(h_tag)
        section_id = child.get("id", "")

        if h_tag.name == "h2":
            _parse_class_section(child, tag_text, page_info, page_title, results)

        elif h_tag.name == "h3":
            if section_id in ("introduction",):
                continue
            api = _parse_function_section(child, tag_text, page_info, page_title)
            if api:
                results.append(api)

    return results


def _extract_description(section) -> str:
    """从 section 提取描述（第一个 <p>）"""
    p = section.find("p")
    return p.get_text(strip=True) if p else ""


def _extract_examples_from_page(page_section) -> list[str]:
    """从整页的 Examples section 提取示例"""
    for section in page_section.find_all("section"):
        if section.get("id") == "examples":
            return _extract_examples(section)
    return []


def _htext(tag) -> str:
    """提取标签的纯文本，去除 headerlink 锚点 (#)"""
    text = tag.get_text(strip=True)
    return text.rstrip("#").strip()


def _parse_class_section(section, class_name, page_info, page_title_text, results):
    """解析 class section (h2 级别)"""

    # 跳过非 class 的 section（如 "Member Functions"）
    if class_name.lower() in ("member functions",):
        # 直接解析其中的函数，不指定 class
        for child in section.find_all("section", recursive=False):
            h3 = child.find("h3", recursive=False)
            if not h3:
                continue
            h3_text = _htext(h3)
            if h3_text.lower() in ("class constructors", "class destructor", "parameters", "notes", "example"):
                continue
            api = _parse_function_section(child, h3_text, page_info, page_title_text, "")
            if api:
                results.append(api)
        return

    for child in section.find_all("section", recursive=False):
        h3 = child.find("h3", recursive=False)
        if not h3:
            continue

        h3_text = _htext(h3)
        section_id = child.get("id", "")

        if section_id in ("introduction", "parameters", "notes", "example"):
            continue

        if section_id == "class-constructors" or h3_text.lower() == "class constructors":
            ctor = _parse_constructor_section(child, section, class_name, page_info, page_title_text)
            if ctor:
                results.append(ctor)
            continue

        if section_id == "class-destructor" or h3_text.lower() == "class destructor":
            dtor = _parse_destructor_section(child, class_name, page_info, page_title_text)
            if dtor:
                results.append(dtor)
            continue

        if h3_text.lower() in ("parameters", "example", "notes"):
            continue

        api = _parse_function_section(child, h3_text, page_info, page_title_text, class_name)
        if api:
            results.append(api)


def _parse_function_section(section, fn_name, page_info, page_title_text, class_name=""):
    """解析一个函数 section (h3 级别)"""
    fn_name = fn_name.rstrip("#")  # 去掉 headerlink 锚点

    api = {
        "name": fn_name,
        "class": class_name,
        "page": page_info["docname"],
        "page_title": page_title_text,
        "url": page_info["url"],
        "signatures": [],
        "description": "",
        "parameters": [],
        "return_value": "",
        "notes": [],
        "examples": [],
    }

    # 描述：h3 后第一个 <p>（且在 blockquote 之前）
    for elem in section.find_all(recursive=False):
        if elem.name == "p":
            api["description"] = elem.get_text(strip=True)
            break
        if elem.name == "blockquote":
            break

    # 签名：section 内的 <code class="language-cpp">（blockquote 内或直接 highlight-cpp）
    api["signatures"] = _extract_signatures(section)

    # 参数表
    api["parameters"] = _extract_params(section)

    # 返回值 / Notes / Examples
    api["return_value"] = _extract_section_value(section, "Return Values")
    api["notes"] = _extract_notes(section)
    api["examples"] = _extract_examples(section)

    return api


def _parse_constructor_section(ctor_section, parent_section, class_name, page_info, page_title_text):
    """解析构造函数"""
    sigs = _extract_signatures(ctor_section)
    if not sigs:
        return None

    # 从父 section 提取构造函数的参数表
    params_section = parent_section.find("section", id="parameters")
    ctor_params = _extract_params(params_section) if params_section else []

    # 描述
    desc_p = ctor_section.find("p")
    desc = desc_p.get_text(strip=True) if desc_p else f"Creates a {class_name} object."

    return {
        "name": class_name,
        "class": class_name,
        "page": page_info["docname"],
        "page_title": page_title_text,
        "url": page_info["url"],
        "signatures": sigs,
        "description": desc,
        "parameters": ctor_params,
        "return_value": "",
        "notes": [],
        "examples": [],
        "is_constructor": True,
    }


def _parse_destructor_section(section, class_name, page_info, page_title_text):
    """解析析构函数"""
    sigs = _extract_signatures(section)
    desc_p = section.find("p")
    desc = desc_p.get_text(strip=True) if desc_p else ""

    return {
        "name": f"~{class_name}",
        "class": class_name,
        "page": page_info["docname"],
        "page_title": page_title_text,
        "url": page_info["url"],
        "signatures": sigs,
        "description": desc,
        "parameters": [],
        "return_value": "",
        "notes": [],
        "examples": [],
        "is_destructor": True,
    }


def _extract_signatures(section) -> list[str]:
    """提取函数签名：优选 blockquote，否则全部 code（过滤注释和示例）"""
    sigs = []
    seen = set()

    # 找到边界标记（Parameters / Return Values / Examples）
    boundary_tag = _find_boundary(section)

    # 优先从 blockquote 提取
    for code in section.find_all("code", class_="language-cpp"):
        if _past_boundary(code, boundary_tag):
            continue
        if code.find_parent("blockquote"):
            text = _clean_code(code)
            if text and text not in seen and not text.startswith("//"):
                seen.add(text)
                sigs.append(text)

    # 如果 blockquote 内没有，放宽到全部
    if not sigs:
        for code in section.find_all("code", class_="language-cpp"):
            if _past_boundary(code, boundary_tag):
                continue
            text = _clean_code(code)
            if text and text not in seen and not text.startswith("//"):
                seen.add(text)
                sigs.append(text)

    return sigs


def _find_boundary(section) -> Tag | None:
    """找到 Parameters/Examples 等边界标签（span 或 h2/h3）"""
    for tag in section.find_all(["span", "h2", "h3"]):
        if tag.get_text(strip=True) in ("Parameters", "Return Values", "Notes", "Examples"):
            return tag
    return None


def _past_boundary(code, boundary) -> bool:
    """判断 code 标签是否在 boundary 之后"""
    if not boundary:
        return False
    # BeautifulSoup 的 sourceline 不可靠，用位置判断
    # 如果 code 在 boundary 的祖先/兄弟链之后
    return code in boundary.find_all_next("code", class_="language-cpp")


def _extract_examples(section) -> list[str]:
    """取 Examples 标签后第一个 highlight-cpp 中的代码（支持 h2/span 两种标签）"""
    # 先找标记（h2 或 span 中文本为 Examples）
    marker = None
    for tag in section.find_all(["h2", "h3", "span"]):
        if tag.get_text(strip=True) == "Examples":
            marker = tag
            break
    if marker:
        hl = marker.find_next("div", class_="highlight-cpp")
        if hl and _is_descendant_of(hl, section):
            code = hl.find("code", class_="language-cpp")
            if code:
                return [_clean_code(code)]
    return []


def _is_descendant_of(element, ancestor) -> bool:
    """检查 element 是否是 ancestor 的后代"""
    parent = element.parent
    while parent:
        if parent == ancestor:
            return True
        parent = parent.parent
    return False


def _clean_code(element) -> str:
    """从 <code> 元素提取纯文本 C++ 代码"""
    text = element.get_text()
    # 清理多余空白
    text = re.sub(r"\s+", " ", text).strip()
    # 修复 token 之间的空格
    text = text.replace(" ;", ";")
    text = text.replace(" ,", ",")
    text = text.replace("( ", "(")
    text = text.replace(" )", ")")
    text = text.replace(" &", "&")
    text = text.replace(" *", "*")
    # 移除 HTML 实体
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    return text


def _extract_params(section) -> list[dict]:
    """提取参数表"""
    table = section.find("table", class_="table")
    if not table:
        return []

    params = []
    tbody = table.find("tbody")
    if not tbody:
        return []

    for row in tbody.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) >= 3:
            params.append({
                "name": cells[0].get_text(strip=True),
                "type": cells[1].get_text(strip=True),
                "description": cells[2].get_text(" ", strip=True),
            })

    return params


def _extract_section_value(section, label: str) -> str:
    """提取 span[label] 后面的第一个 <p> 文本"""
    for span in section.find_all("span"):
        if span.get_text(strip=True) == label:
            # 找 span 后面的第一个 <p>
            next_p = span.find_next("p")
            if next_p:
                return next_p.get_text(strip=True)
            # 也可能是直接文本
            next_sib = span.next_sibling
            if next_sib:
                return str(next_sib).strip()
    return ""


def _extract_notes(section) -> list[str]:
    """提取 Notes 列表"""
    for span in section.find_all("span"):
        if span.get_text(strip=True) == "Notes":
            next_ul = span.find_next("ul")
            if next_ul:
                return [li.get_text(strip=True) for li in next_ul.find_all("li")]
    return []


# ─── 3. 主流程 ───

def crawl_all(pages: list[dict], limit: int = 0, delay: float = 1.0) -> list[dict]:
    """爬取所有页面"""
    all_api = []
    pages_to_crawl = pages[:limit] if limit > 0 else pages

    for i, page in enumerate(pages_to_crawl):
        print(f"[{i+1}/{len(pages_to_crawl)}] {page['docname']} ...", end=" ", flush=True)

        try:
            html = fetch_html(page["url"])
            entries = parse_html(html, page)
            print(f"✅ {len(entries)} APIs")
            all_api.extend(entries)
        except Exception as e:
            print(f"❌ {e}")
            continue

        if delay > 0 and i < len(pages_to_crawl) - 1:
            time.sleep(delay)

    return all_api


def crawl_local(html_dir: Path, pages: list[dict], limit: int = 0) -> list[dict]:
    """从本地 HTML 文件读取（用于测试）"""
    all_api = []
    pages_to_process = pages[:limit] if limit > 0 else pages

    for i, page in enumerate(pages_to_process):
        # 尝试匹配本地文件名
        docname = page["docname"]
        possible_paths = [
            html_dir / f"{docname.replace('/', '_')}.html",
            html_dir / f"{docname.split('/')[-1]}.html",
        ]

        found = False
        for p in possible_paths:
            if p.exists():
                print(f"[{i+1}/{len(pages_to_process)}] {p.name} ...", end=" ", flush=True)
                with open(p, "r", encoding="utf-8") as f:
                    html = f.read()
                entries = parse_html(html, page)
                print(f"✅ {len(entries)} APIs")
                all_api.extend(entries)
                found = True
                break

        if not found:
            print(f"[{i+1}/{len(pages_to_process)}] {docname} ... ⚠️ 本地文件未找到")

    return all_api


def main():
    parser = argparse.ArgumentParser(description="VEX V5 C++ API 爬虫")
    parser.add_argument("--limit", type=int, default=0, help="限制爬取页数（0=全部）")
    parser.add_argument("--delay", type=float, default=1.0, help="请求间隔（秒）")
    parser.add_argument("--local", type=str, default="", help="从本地 HTML 目录读取")
    parser.add_argument("--out", type=str, default=str(OUTPUT_PATH), help="输出 JSON 路径")
    args = parser.parse_args()

    # 加载页面列表
    data = load_searchindex(SEARCHINDEX_PATH)
    pages = get_cpp_page_list(data)
    print(f"C++ 文档页面数: {len(pages)}")

    if args.limit > 0:
        print(f"限制爬取: {args.limit} 页")

    # 爬取
    if args.local:
        all_api = crawl_local(Path(args.local), pages, args.limit)
    else:
        all_api = crawl_all(pages, args.limit, args.delay)

    # 统计
    print(f"\n总计提取 API: {len(all_api)}")
    type_counts = Counter("constructor" if a.get("is_constructor") else "function" for a in all_api)
    print(f"  构造函数: {type_counts.get('constructor', 0)}")
    print(f"  成员函数: {type_counts.get('function', 0)}")

    # 保存
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(all_api, f, ensure_ascii=False, indent=2)
    print(f"\n已保存到: {args.out}")


if __name__ == "__main__":
    main()
