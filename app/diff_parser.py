"""diff → 代码块级解析：轻量多语言函数边界识别 + hunk 级降级。

不引入 tree-sitter 编译依赖（Windows 开箱即用优先）；识别不到函数边界时
自动降级为 hunk 级并标注 precision='hunk'，绝不假装精确到函数。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

EXT_LANG = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".java": "java", ".kt": "kotlin",
    ".go": "go", ".rb": "ruby", ".php": "php", ".rs": "rust", ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp", ".cs": "csharp", ".swift": "swift",
    ".scala": "scala", ".vue": "vue", ".sh": "shell", ".sql": "sql",
}

# 每种语言的函数/类定义行正则：第 1 个捕获组为名称
DEF_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "python": [(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(", "function"),
               (r"^\s*class\s+([A-Za-z_]\w*)[\s(:]", "class")],
    "javascript": [(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)", "function"),
                   (r"^\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>", "function"),
                   (r"^\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{", "function"),
                   (r"^\s*class\s+([A-Za-z_$][\w$]*)", "class")],
    "typescript": [(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)", "function"),
                   (r"^\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)", "function"),
                   (r"^\s*(?:public|private|protected|static|async|\s)*([A-Za-z_$][\w$]*)\s*\([^)]*\)[^{;]*\{", "function"),
                   (r"^\s*(?:export\s+)?(?:interface|class|enum)\s+([A-Za-z_$][\w$]*)", "class")],
    "java": [(r"^\s*(?:public|private|protected|static|final|abstract|synchronized|native|\s)*[\w<>\[\],.?\s]+?\s+([A-Za-z_]\w*)\s*\([^;{]*\)\s*(?:throws\s+[\w,\s]+)?\{", "function"),
             (r"^\s*(?:public|private|protected|\s)*(?:class|interface|enum|record)\s+([A-Za-z_]\w*)", "class")],
    "kotlin": [(r"^\s*(?:suspend\s+)?fun\s+(?:<[^>]+>\s*)?([A-Za-z_]\w*)\s*\(", "function"),
               (r"^\s*(?:data\s+)?class\s+([A-Za-z_]\w*)", "class")],
    "go": [(r"^func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*\(", "function"),
           (r"^type\s+([A-Za-z_]\w*)\s+struct", "class")],
    "ruby": [(r"^\s*def\s+([A-Za-z_]\w*[?!]?)", "function"),
             (r"^\s*class\s+([A-Za-z_]\w*)", "class")],
    "php": [(r"^\s*(?:public|private|protected|static|\s)*function\s+([A-Za-z_]\w*)\s*\(", "function"),
            (r"^\s*(?:abstract\s+|final\s+)?class\s+([A-Za-z_]\w*)", "class")],
    "rust": [(r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z_]\w*)\s*\(", "function"),
             (r"^\s*(?:pub\s+)?(?:struct|enum|trait|impl)\s+([A-Za-z_]\w*)", "class")],
    "c": [(r"^\s*[\w\s\*\&:<>]+\b([A-Za-z_]\w*)\s*\([^;]*\)\s*\{", "function"),
          (r"^\s*(?:typedef\s+)?(?:struct|enum|union)\s+([A-Za-z_]\w*)", "class")],
    "cpp": [(r"^\s*[\w\s\*\&:<>~]+\b([A-Za-z_]\w*)\s*\([^;]*\)\s*(?:const\s*)?\{", "function"),
            (r"^\s*(?:class|struct|enum|namespace)\s+([A-Za-z_]\w*)", "class")],
    "csharp": [(r"^\s*(?:public|private|protected|internal|static|async|virtual|override|\s)*[\w<>\[\],.?]+\s+([A-Za-z_]\w*)\s*\([^;{]*\)\s*\{", "function"),
               (r"^\s*(?:public|private|protected|internal|\s)*(?:class|interface|enum|struct|record)\s+([A-Za-z_]\w*)", "class")],
    "swift": [(r"^\s*(?:public|private|internal|static|class|\s)*func\s+([A-Za-z_]\w*)\s*[({]", "function"),
              (r"^\s*(?:public|private|internal|\s)*(?:class|struct|enum|protocol)\s+([A-Za-z_]\w*)", "class")],
    "scala": [(r"^\s*(?:def|val)\s+([A-Za-z_]\w*)", "function"),
              (r"^\s*(?:case\s+)?class\s+([A-Za-z_]\w*)", "class")],
    "vue": [(r"^\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{", "function")],
    "shell": [(r"^\s*(?:function\s+)?([A-Za-z_]\w*)\s*\(\)\s*\{", "function")],
}
DEF_PATTERNS["jsx"] = DEF_PATTERNS["javascript"]
DEF_PATTERNS["tsx"] = DEF_PATTERNS["typescript"]
DEF_PATTERNS["hpp"] = DEF_PATTERNS["cpp"]
DEF_PATTERNS["cc"] = DEF_PATTERNS["cpp"]


def lang_of(path: str) -> str:
    import os
    return EXT_LANG.get(os.path.splitext(path)[1].lower(), "")


@dataclass
class Hunk:
    old_start: int
    new_start: int
    old_count: int
    new_count: int
    heading: str = ""
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    added_lines: list[int] = field(default_factory=list)
    removed_lines: list[int] = field(default_factory=list)


@dataclass
class FileDiff:
    path: str
    old_path: str = ""
    status: str = "M"
    is_binary: bool = False
    hunks: list[Hunk] = field(default_factory=list)
    added: int = 0
    deleted: int = 0
    raw: str = ""
    blocks: list[dict[str, Any]] = field(default_factory=list)
    precision: str = "function"


@dataclass
class Symbol:
    name: str
    kind: str
    start: int
    end: int


def extract_symbols(content: str, lang: str) -> list[Symbol]:
    """识别源码里的函数/类边界（行号 1-based，end 为下一个定义前一行）。"""
    if not content or not lang or lang not in DEF_PATTERNS:
        return []
    lines = content.splitlines()
    found: list[tuple[int, str, str]] = []
    patterns = [(re.compile(p), k) for p, k in DEF_PATTERNS[lang]]
    for idx, line in enumerate(lines, 1):
        for rx, kind in patterns:
            m = rx.match(line)
            if m:
                found.append((idx, m.group(1), kind))
                break
    result: list[Symbol] = []
    for i, (start, name, kind) in enumerate(found):
        end = found[i + 1][0] - 1 if i + 1 < len(found) else len(lines)
        result.append(Symbol(name=name, kind=kind, start=start, end=max(end, start)))
    return result


def _owner(symbols: list[Symbol], line_no: int) -> Symbol | None:
    for s in symbols:
        if s.start <= line_no <= s.end:
            return s
    return None


def _parse_hunk_header(line: str) -> Hunk | None:
    m = re.match(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@\s*(.*)$", line)
    if not m:
        return None
    return Hunk(old_start=int(m.group(1)), old_count=int(m.group(2) or 1),
                new_start=int(m.group(3)), new_count=int(m.group(4) or 1),
                heading=(m.group(5) or "").strip())


def parse_diff(diff_text: str) -> list[FileDiff]:
    """解析 unified diff 为 FileDiff 列表。"""
    if not diff_text:
        return []
    chunks = re.split(r"(?m)^(?=diff --git )", diff_text)
    out: list[FileDiff] = []
    for ch in chunks:
        if not ch.strip() or not ch.startswith("diff --git"):
            continue
        header = ch.splitlines()[0]
        m = re.match(r"^diff --git a/(.+?) b/(.+?)$", header)
        if not m:
            continue
        old_path, new_path = m.group(1), m.group(2)
        fd = FileDiff(path=new_path, old_path=old_path, raw=ch)
        if "GIT binary patch" in ch or "Binary files" in ch:
            fd.is_binary = True
        if "new file mode" in ch:
            fd.status = "A"
        elif "deleted file mode" in ch:
            fd.status = "D"
        elif "rename from" in ch:
            fd.status = "R"
        hunk: Hunk | None = None
        old_ln = new_ln = 0
        for line in ch.splitlines()[1:]:
            if line.startswith("@@"):
                hunk = _parse_hunk_header(line)
                if hunk:
                    fd.hunks.append(hunk)
                    old_ln, new_ln = hunk.old_start, hunk.new_start
                continue
            if hunk is None:
                continue
            if line.startswith("+++") or line.startswith("---") or line.startswith("\\"):
                continue
            if line.startswith("+"):
                hunk.added.append(line[1:])
                hunk.added_lines.append(new_ln)
                fd.added += 1
                new_ln += 1
            elif line.startswith("-"):
                hunk.removed.append(line[1:])
                hunk.removed_lines.append(old_ln)
                fd.deleted += 1
                old_ln += 1
            elif line.startswith(" ") or line == "":
                old_ln += 1
                new_ln += 1
        out.append(fd)
    return out


def build_blocks(fd: FileDiff, old_content: str, new_content: str) -> list[dict[str, Any]]:
    """把 hunk 内的变更行归属到函数/类，生成代码块级结构。"""
    lang = lang_of(fd.path)
    old_syms = extract_symbols(old_content, lang)
    new_syms = extract_symbols(new_content, lang)
    supports = lang in DEF_PATTERNS
    grouped: dict[str, dict[str, Any]] = {}

    def key_for(sym: Symbol | None, hunk: Hunk) -> tuple[str, str, str]:
        if sym:
            return (sym.name, sym.kind, "function")
        return (f"hunk@{hunk.new_start}", "hunk", "hunk")

    for h in fd.hunks:
        pairs: list[tuple[int, Symbol | None]] = []
        pairs += [(ln, _owner(old_syms, ln)) for ln in h.removed_lines]
        pairs += [(ln, _owner(new_syms, ln)) for ln in h.added_lines]
        for _ln, sym in pairs:
            name, kind, precision = key_for(sym, h)
            g = grouped.setdefault(name, {
                "name": name, "kind": kind, "precision": precision,
                "change_type": "modified", "old_range": "", "new_range": "",
                "added_lines": 0, "removed_lines": 0, "heading": h.heading,
            })
        # 累加每个 hunk 的行数到其命中的块
        for ln, sym in [(ln, _owner(new_syms, ln)) for ln in h.added_lines]:
            name, _, _ = key_for(sym, h)
            grouped[name]["added_lines"] += 1
            grouped[name]["new_range"] = f"{h.new_start}-{h.new_start + h.new_count - 1}"
        for ln, sym in [(ln, _owner(old_syms, ln)) for ln in h.removed_lines]:
            name, _, _ = key_for(sym, h)
            grouped[name]["removed_lines"] += 1
            grouped[name]["old_range"] = f"{h.old_start}-{h.old_start + h.old_count - 1}"

    old_names = {s.name for s in old_syms}
    new_names = {s.name for s in new_syms}
    for name, g in grouped.items():
        if g["precision"] == "hunk":
            g["change_type"] = "modified"
        elif fd.status == "A" or (name not in old_names and name in new_names):
            g["change_type"] = "added"
        elif fd.status == "D" or (name in old_names and name not in new_names):
            g["change_type"] = "removed"
        elif g["heading"] and name in g["heading"] and g["added_lines"] and g["removed_lines"]:
            g["change_type"] = "signature_changed"
        else:
            g["change_type"] = "modified"
    return list(grouped.values())


CHANGE_TYPE_CN = {
    "added": "新增", "removed": "删除", "modified": "修改",
    "signature_changed": "签名变更", "refactored": "重构",
}


def describe_blocks(blocks: list[dict[str, Any]], limit: int = 12) -> str:
    """给 LLM / 本地降级用的紧凑文本描述。"""
    if not blocks:
        return "（未能定位到具体代码块）"
    parts = []
    for b in sorted(blocks, key=lambda x: -(x["added_lines"] + x["removed_lines"]))[:limit]:
        parts.append(f"{b['name']}（{CHANGE_TYPE_CN.get(b['change_type'], '修改')}，"
                     f"+{b['added_lines']}/-{b['removed_lines']}，{b['precision']}级）")
    return "；".join(parts)
