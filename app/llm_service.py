"""LLM 网关：OpenAI 兼容协议、结构化 JSON 容错重试 + 完全可用的本地规则降级。

设计原则（对应需求文档第二节）：
- 归纳不是罗列：Prompt 要求跨提交综合判断。
- 证据优先绝不脑补：证据不足必须输出「原因未知（证据不足）」。
- 未配置 / 调用失败时自动降级为确定性本地规则，整套功能仍可完整跑通。
"""
from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from .diff_parser import CHANGE_TYPE_CN, FileDiff, describe_blocks
from .models import SystemConfig
from .schemas import (CommitAnalysisResult, EvolutionResult, FileAnalysisResult,
                      FileBaselineResult, ModuleClusterResult, parse_llm_json)
from .signal_filter import extract_motivation, guess_risk

NO_MOTIVATION = "原因未知（证据不足）"


def get_config(db: Session) -> SystemConfig:
    cfg = db.get(SystemConfig, 1)
    if cfg is None:
        cfg = SystemConfig(id=1)
        db.add(cfg)
        db.commit()
    return cfg


class LLMUnavailable(RuntimeError):
    pass


def _client(cfg: SystemConfig):
    from openai import OpenAI
    if not cfg.llm_enabled:
        raise LLMUnavailable("LLM 已在系统设置中关闭（本地规则模式）")
    if not cfg.api_key:
        raise LLMUnavailable("未配置 API Key（本地规则模式）")
    return OpenAI(base_url=cfg.base_url or "https://api.openai.com/v1",
                  api_key=cfg.api_key, timeout=60.0, max_retries=0)


def _extract_json(text: str) -> dict:
    """容错：剥离 markdown 代码块、截取首尾花括号。"""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    raise LLMUnavailable("LLM 返回内容不是合法 JSON")


def chat_json(cfg: SystemConfig, system: str, user: str, max_tokens: int = 1800) -> dict:
    """强制结构化 JSON，兼容不支持 response_format 的本地模型（Ollama 等）。"""
    client = _client(cfg)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    last_err: Exception | None = None
    for attempt in range(2):
        for use_rf in (True, False):
            try:
                kwargs: dict[str, Any] = dict(model=cfg.model, messages=messages,
                                              temperature=0.2, max_tokens=max_tokens)
                if use_rf:
                    kwargs["response_format"] = {"type": "json_object"}
                resp = client.chat.completions.create(**kwargs)
                return _extract_json(resp.choices[0].message.content or "")
            except Exception as exc:  # noqa: BLE001  兼容各厂商 SDK 异常
                last_err = exc
                continue
    raise LLMUnavailable(f"LLM 调用失败：{type(last_err).__name__}: {str(last_err)[:200]}")


def test_connection(cfg: SystemConfig) -> tuple[bool, str]:
    """连通性测试：不写入任何业务数据。"""
    try:
        result = chat_json(cfg,
                           "你是一个只输出 JSON 的连通性测试端点。",
                           "请严格输出 JSON：{\"ok\": true}", max_tokens=60)
        if result.get("ok") is True or result:
            return True, f"连接成功（模型 {cfg.model} 正常响应）"
        return False, "模型已响应但内容异常"
    except LLMUnavailable as exc:
        return False, str(exc)
    except Exception as exc:  # noqa: BLE001
        return False, f"连接失败：{type(exc).__name__}: {str(exc)[:200]}"


# ---------------------------------------------------------------------------
# 各分析能力：LLM 优先，失败自动降级
# ---------------------------------------------------------------------------

SYSTEM_BASE = (
    "你是一名资深代码考古工程师，服务于「单文件变更历史知识库」。"
    "严格只输出 JSON，不要输出任何解释文字或 markdown 代码块。"
    "铁律：证据不足时动机必须写「原因未知（证据不足）」，严禁编造业务原因、严禁猜测需求背景。"
    "归纳优先于罗列：要给出跨改动/跨提交的综合结论，不要逐条复述 diff。"
)


def cluster_modules(cfg: SystemConfig, tree_text: str, cochange_text: str) -> tuple[ModuleClusterResult, str]:
    system = SYSTEM_BASE + (
        "任务：把仓库归纳成少量业务功能模块。输出格式："
        '{"modules":[{"name":"模块名","path_rules":["src/a/","src/b/x.py"],"responsibility":"一句话职责"}]}'
        "要求：模块数 3-10 个；path_rules 用目录前缀或具体路径，尽量覆盖全部源码文件；"
        "优先参考文件共变关系，把经常一起改动的文件放进同一模块。"
    )
    user = f"【仓库文件结构（节选）】\n{tree_text[:6000]}\n\n【历史共变统计】\n{cochange_text[:3000]}"
    try:
        data = chat_json(cfg, system, user, max_tokens=1600)
        res = parse_llm_json(ModuleClusterResult, data)
        if res.modules:
            return res, "LLM"
    except Exception:  # noqa: BLE001
        pass
    return _fallback_modules(tree_text), "本地规则"


def _fallback_modules(tree_text: str) -> ModuleClusterResult:
    """按目录前缀聚类，确定性降级。"""
    from .schemas import ModuleItem
    groups: dict[str, list[str]] = {}
    for line in tree_text.splitlines():
        path = line.strip()
        if not path or "/" not in path:
            continue
        parts = path.split("/")
        key = "/".join(parts[:2]) if len(parts) > 2 else parts[0]
        groups.setdefault(key, []).append(path)
    items = []
    for key, paths in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:10]:
        items.append(ModuleItem(name=key.replace("/", " / "), path_rules=[key + "/"],
                                responsibility=f"包含 {len(paths)} 个文件的代码目录（按目录结构自动聚类）"))
    if not items:
        items.append(ModuleItem(name="全部代码", path_rules=[""], responsibility="仓库根目录"))
    return ModuleClusterResult(modules=items)


def file_baseline(cfg: SystemConfig, path: str, content: str, symbols_text: str,
                  module_name: str = "") -> tuple[FileBaselineResult, str]:
    system = SYSTEM_BASE + (
        "任务：为一个代码文件生成基线档案。输出格式："
        '{"one_liner":"一句话当前职责（不超过40字）","doc_md":"Markdown 功能说明"}'
        "doc_md 需包含：## 职责、## 核心结构（函数/类清单）、## 上下游依赖、## 约束与注意事项（只写代码中可验证的）。"
        "严禁凭空编造业务背景；无法判断的地方写「暂无可靠信息」。"
    )
    excerpt = content[:5000]
    user = (f"文件路径：{path}\n所属模块：{module_name or '未分类'}\n"
            f"识别到的符号：{symbols_text[:1200]}\n\n【源码节选】\n{excerpt}")
    try:
        data = chat_json(cfg, system, user, max_tokens=1400)
        res = parse_llm_json(FileBaselineResult, data)
        if res.one_liner:
            return res, "LLM"
    except Exception:  # noqa: BLE001
        pass
    return _fallback_baseline(path, content, symbols_text, module_name), "本地规则"


def _fallback_baseline(path: str, content: str, symbols_text: str,
                       module_name: str) -> FileBaselineResult:
    import os
    base = os.path.basename(path)
    stem = os.path.splitext(base)[0]
    lines = [l for l in (content or "").splitlines()]
    syms = [re.sub(r"\((?:function|class|method|hunk)\)$", "", s.strip())
            for s in symbols_text.split(",") if s.strip()][:20]
    one = f"{stem}：{module_name or '代码'} 模块下的实现文件，包含 {len(syms)} 个可识别的函数/类"
    sym_lines = "\n".join(f"- `{s}`" for s in syms) if syms else "- 未识别到函数/类边界"
    doc = (f"# {path}\n\n## 职责\n\n{one}。\n\n"
           f"## 核心结构\n\n" + sym_lines +
           f"\n\n## 上下游依赖\n\n- 共 {len(lines)} 行源码；import/using 语句见源码头部。\n\n"
           "## 约束与注意事项\n\n- 暂无可靠信息（本地规则模式，未做语义归纳）。\n")
    return FileBaselineResult(one_liner=one, doc_md=doc)


def analyze_commit(cfg: SystemConfig, message: str, fds: list[FileDiff],
                   max_diff_chars: int) -> tuple[CommitAnalysisResult, str]:
    """提交级分析：改动代码块 / 动机 / 文档更新 / 风险。"""
    local_motivation, local_evidence = extract_motivation(message)
    system = SYSTEM_BASE + (
        "任务：分析一次 Git 提交。输出格式："
        '{"summary":"一句话综合结论（跨文件归纳，不复述diff）",'
        '"motivation":"改动动机","evidence_source":"commit message|PR|diff 推断|未知",'
        '"risk_level":"低|中|高",'
        '"files":[{"path":"文件路径","one_liner":"改动后该文件的一句话职责",'
        '"doc_update":"该功能说明文档本次应如何更新（一句话）",'
        '"blocks":[{"name":"函数名","change_type":"added|removed|modified|signature_changed",'
        '"description":"这个代码块改了什么（一句话）"}]}]}'
        "铁律：evidence_source 只能是上述四值之一；commit message 只有 fix/update 等无信息量词时，"
        "motivation 必须写「原因未知（证据不足）」且 evidence_source 为「未知」。"
        "blocks 的 name 必须来自给定代码块清单，不要发明函数名。"
    )
    file_desc = []
    budget = max_diff_chars
    for fd in fds:
        desc = (f"文件 {fd.path} [{fd.status}] +{fd.added}/-{fd.deleted}\n"
                f"改动代码块：{describe_blocks(fd.blocks)}\n"
                f"diff 节选：\n{fd.raw[:600]}")
        if budget - len(desc) < 0:
            break
        file_desc.append(desc)
        budget -= len(desc)
    user = f"【提交说明】\n{message[:1200] or '(空)'}\n\n【改动明细】\n" + "\n\n".join(file_desc)
    try:
        data = chat_json(cfg, system, user, max_tokens=2200)
        res = parse_llm_json(CommitAnalysisResult, data)
        if not res.summary:
            raise LLMUnavailable("空摘要")
        # 兜底约束：LLM 不得在证据不足时编造动机
        if local_evidence == "未知":
            res.motivation = NO_MOTIVATION
            res.evidence_source = "未知"
        if res.evidence_source not in ("commit message", "PR", "diff 推断", "未知"):
            res.evidence_source = "未知"
        if res.risk_level not in ("低", "中", "高"):
            res.risk_level = guess_risk(message, fds)
        if not res.files:
            res.files = _fallback_files(fds)
        return res, "LLM"
    except Exception:  # noqa: BLE001
        pass
    return _fallback_analysis(message, fds, local_motivation, local_evidence), "本地规则"


def _fallback_files(fds: list[FileDiff]) -> list[FileAnalysisResult]:
    out = []
    for fd in fds:
        blocks = []
        for b in fd.blocks[:10]:
            blocks.append({
                "name": b["name"],
                "change_type": b.get("change_type", "modified"),
                "description": f"{CHANGE_TYPE_CN.get(b.get('change_type'), '修改')} "
                               f"+{b['added_lines']}/-{b['removed_lines']} 行"
                               + ("" if b["precision"] == "function" else "（仅 hunk 级精度）"),
            })
        fn_names = [b["name"] for b in fd.blocks if b.get("precision") == "function"]
        added = [b["name"] for b in fd.blocks
                 if b.get("precision") == "function" and b.get("change_type") == "added"]
        removed = [b["name"] for b in fd.blocks
                   if b.get("precision") == "function" and b.get("change_type") == "removed"]
        parts = [f"共 {len(fd.blocks)} 处代码块变更（+{fd.added}/-{fd.deleted} 行）"]
        if added:
            parts.append("新增 " + "、".join(added[:5]))
        if removed:
            parts.append("移除 " + "、".join(removed[:5]))
        if not fn_names:
            parts.append("（本次仅 hunk 级精度）")
        out.append(FileAnalysisResult(
            path=fd.path,
            blocks=[_as_block(b) for b in blocks],
            doc_update="；".join(parts),
            one_liner="",
        ))
    return out


def _as_block(d: dict) -> Any:
    from .schemas import BlockResult
    return BlockResult(name=d.get("name", ""), change_type=d.get("change_type", "modified"),
                       description=d.get("description", ""))


def _fallback_analysis(message: str, fds: list[FileDiff], motivation: str,
                       evidence: str) -> CommitAnalysisResult:
    paths = [fd.path for fd in fds]
    block_total = sum(len(fd.blocks) for fd in fds)
    summary = (f"本次提交涉及 {len(paths)} 个文件、{block_total} 处代码块变更，"
               f"共 +{sum(fd.added for fd in fds)}/-{sum(fd.deleted for fd in fds)} 行。")
    return CommitAnalysisResult(
        summary=summary, motivation=motivation, evidence_source=evidence,
        risk_level=guess_risk(message, fds), files=_fallback_files(fds))


def evolution_line(cfg: SystemConfig, path: str, current: str,
                   events: list[dict]) -> tuple[str, str]:
    """跨提交归纳：把孤立事件串成「职责演进主线」。"""
    if not events:
        return current, "本地规则"
    system = SYSTEM_BASE + (
        "任务：把一个文件的历次改动串成一条职责演进主线。输出格式："
        '{"evolution_line":"用 → 连接的短句，例如：同步扣库 → 支持异步退款 → 加幂等与超时兜底"}'
        "要求：只写职责/能力层面的变化，不写行号与琐碎细节；不超过 80 字；"
        "证据不足的节点不要臆测，可省略该节点。"
    )
    compact = "\n".join(
        f"- {e.get('sha_short', '')} 提交说明：{(e.get('message') or '')[:70]} | "
        f"改动：{(e.get('summary') or '')[:80]} | "
        f"新增能力：{(e.get('capability') or '')[:70]} | 动机：{(e.get('motivation') or '')[:50]}"
        for e in events[:20]
    )
    user = (f"文件：{path}\n已有主线：{current or '(无)'}\n\n"
            f"【按时间排序的改动节点】\n{compact}\n\n"
            "注意：优先用提交说明与新增能力归纳职责变化，不要把『涉及几个文件几行代码』写进主线。")
    try:
        data = chat_json(cfg, system, user, max_tokens=300)
        res = parse_llm_json(EvolutionResult, data)
        if res.evolution_line:
            return res.evolution_line, "LLM"
    except Exception:  # noqa: BLE001
        pass
    return _fallback_evolution(current, events), "本地规则"


def _fallback_evolution(current: str, events: list[dict]) -> str:
    """确定性降级：从提交说明 / 新增能力归纳职责阶段，绝不罗列「涉及几个文件几行」。

    可用证据只有 commit message 与代码块变更；信息不足的节点省略，不脑补业务背景。
    """
    prefix_rx = re.compile(
        r"^\s*(?:feat|fix|chore|style|refactor|perf|docs|test|revert|hotfix|"
        r"功能|修复|重构|新增|优化|调整|更新|提交|回滚)(\([^)]*\))?\s*[:：\-]\s*", re.I)
    stages: list[str] = []
    for e in events[:12]:
        msg = (e.get("message") or "").strip().splitlines()[0] if (e.get("message") or "").strip() else ""
        stage = prefix_rx.sub("", msg).strip()
        stage = re.split(r"[，,。;；]", stage)[0].strip()[:34]
        if not stage or len(stage) < 3:
            cap = (e.get("capability") or "").strip()
            stage = re.split(r"[，,。;；]", cap)[0].strip()[:34] if cap else ""
        if not stage or stage == "原因未知（证据不足）":
            stage = "一次结构性调整（原因未知）"
        if stage and stage not in stages:
            stages.append(stage)
    if not stages:
        return current
    if len(stages) == 1:
        return f"初始建档：{stages[0]}"
    return " → ".join(stages[:8])[:200]


def update_current_doc(cfg: SystemConfig, path: str, current_doc: str,
                       change_summary: str, doc_update: str, one_liner: str,
                       blocks: list[dict] | None = None) -> tuple[str, str]:
    """当前态说明增量修订（不推倒重写）：同步函数清单 + 追加变更记录。"""
    blocks = blocks or []
    changed = "；".join(f"{b.get('name', '')}({b.get('change_type', '')})" for b in blocks[:12])
    system = SYSTEM_BASE + (
        "任务：在原有功能说明基础上做局部增量修订。输出格式：{\"doc_md\":\"完整 Markdown 文档\"}"
        "要求：把本次新增的函数/类补进『核心结构』清单、把已删除的从中移除；"
        "保留仍然成立的内容，只更新因本次改动而过时的职责/结构/约束描述；"
        "不得删除未受影响的段落；不得编造代码中不存在的信息。"
    )
    user = (f"文件：{path}\n一句话职责：{one_liner}\n本次改动：{change_summary[:400]}\n"
            f"文档更新建议：{doc_update[:400]}\n改动代码块：{changed[:600]}\n\n"
            f"【现有文档】\n{current_doc[:3500]}")
    try:
        data = chat_json(cfg, system, user, max_tokens=1400)
        doc = str(data.get("doc_md", "")).strip()
        if doc:
            return doc, "LLM"
    except Exception:  # noqa: BLE001
        pass
    return _fallback_doc_update(path, current_doc, change_summary, doc_update, blocks), "本地规则"


def _fallback_doc_update(path: str, current_doc: str, change_summary: str,
                         doc_update: str, blocks: list[dict]) -> str:
    """本地规则：真实维护「核心结构」函数清单，并追加可追溯的变更记录。"""
    doc = current_doc or f"# {path}\n"
    added = [b.get("name", "") for b in blocks if b.get("change_type") == "added"
             and b.get("precision") == "function" and b.get("name")]
    removed = {b.get("name", "") for b in blocks if b.get("change_type") == "removed"
               and b.get("precision") == "function"}

    if "## 核心结构" in doc:
        head, rest = doc.split("## 核心结构", 1)
        if "\n## " in rest:
            section, tail = rest.split("\n## ", 1)
            tail = "\n## " + tail
        else:
            section, tail = rest, ""
        lines = [ln for ln in section.splitlines() if not (ln.strip().startswith("- `")
                 and any(f"`{n}`" in ln for n in removed))]
        for name in added:
            if not any(f"`{name}`" in ln for ln in lines):
                lines.append(f"- `{name}`")
        doc = head + "## 核心结构" + "\n".join(lines).rstrip() + "\n" + tail
    elif added:
        doc += "\n## 核心结构\n\n" + "\n".join(f"- `{n}`" for n in added) + "\n"

    # 变更轨迹：复用已有条目，最新在前，最多保留 8 条
    marker = "## 变更轨迹（本地规则）"
    old_entries: list[str] = []
    if marker in doc:
        base, history = doc.split(marker, 1)
        old_entries = [ln.strip() for ln in history.splitlines()
                       if ln.strip().startswith("- ")][:7]
        doc = base.rstrip()
    entry = (doc_update or change_summary).strip().replace("\n", " ")[:240]
    doc = doc.rstrip() + f"\n\n{marker}\n\n- {entry}\n"
    if old_entries:
        doc += "\n".join(old_entries) + "\n"
    return doc[:6000]


# ---------------------------------------------------------------------------
# 功能模块级能力：基线档案 / 职责演进主线
# ---------------------------------------------------------------------------

def module_baseline(cfg: SystemConfig, name: str, responsibility: str,
                    files_text: str) -> tuple[str, str, str]:
    """为一个功能模块生成基线档案，返回 (one_liner, doc_md, mode)。"""
    system = SYSTEM_BASE + (
        "任务：为一个业务功能模块生成基线档案。输出格式："
        '{"one_liner":"一句话当前职责（不超过40字）","doc_md":"Markdown 功能说明"}'
        "doc_md 必须包含：## 职责、## 当前能力（按子功能列点）、## 核心文件、"
        "## 边界与约束（只写给定材料中可验证的内容）。"
        "严禁凭空编造业务背景；信息不足写「暂无可靠信息」。"
    )
    user = (f"模块名称：{name}\n冷启动归纳的职责：{responsibility or '(无)'}\n\n"
            f"【模块内文件（含一句话职责）】\n{files_text[:4000]}")
    try:
        data = chat_json(cfg, system, user, max_tokens=1600)
        one = str(data.get("one_liner", "")).strip()
        doc = str(data.get("doc_md", "")).strip()
        if one and doc:
            return one, doc, "LLM"
    except Exception:  # noqa: BLE001
        pass
    lines = [ln.strip() for ln in files_text.splitlines() if ln.strip()][:30]
    one = responsibility or f"{name}：由 {len(lines)} 个源码文件组成的功能模块"
    doc = (f"# {name}\n\n## 职责\n\n{one}。\n\n## 当前能力\n\n"
           "- 能力清单待首次提交分析后生成（本地规则模式）。\n\n"
           "## 核心文件\n\n" + ("\n".join(f"- {ln}" for ln in lines) if lines else "- 暂无文件") +
           "\n\n## 边界与约束\n\n- 暂无可靠信息（本地规则模式，未做语义归纳）。\n")
    return one, doc, "本地规则"


def module_evolution(cfg: SystemConfig, name: str, current: str,
                     events: list[dict]) -> tuple[str, str]:
    """跨提交归纳模块职责演进主线，事件结构与 evolution_line 兼容。"""
    if not events:
        return current, "本地规则"
    system = SYSTEM_BASE + (
        "任务：把一个功能模块的历次改动串成一条职责演进主线。输出格式："
        '{"evolution_line":"用 → 连接的短句，例如：订单查询 → 支持退款 → 引入异步与幂等兜底"}'
        "要求：只写模块能力/职责层面的变化，不写行号、文件数与琐碎细节；"
        "不超过 80 字；证据不足的节点不要臆测，可省略。"
    )
    compact = "\n".join(
        f"- {e.get('sha_short', '')} 提交说明：{(e.get('message') or '')[:70]} | "
        f"能力变化：{(e.get('capability') or '')[:80]} | 结论：{(e.get('summary') or '')[:70]}"
        for e in events[:20]
    )
    user = (f"模块：{name}\n已有主线：{current or '(无)'}\n\n"
            f"【按时间排序的模块级改动节点】\n{compact}\n\n"
            "注意：不要写『涉及几个文件几行代码』，只写这个模块的功能边界如何变化。")
    try:
        data = chat_json(cfg, system, user, max_tokens=300)
        res = parse_llm_json(EvolutionResult, data)
        if res.evolution_line:
            return res.evolution_line, "LLM"
    except Exception:  # noqa: BLE001
        pass
    return _fallback_evolution(current, events), "本地规则"


def append_module_history(doc_md: str, capability: str, summary: str,
                          sha_short: str, max_entries: int = 8) -> str:
    """模块档案的变更轨迹：保留既有条目，最新在前，避免无限膨胀。"""
    base = doc_md or "# 模块\n"
    marker = "## 变更轨迹"
    old: list[str] = []
    if marker in base:
        head, tail = base.split(marker, 1)
        old = [ln.strip() for ln in tail.splitlines() if ln.strip().startswith("- ")][:max_entries - 1]
        base = head.rstrip()
    line = (capability or summary).strip().replace("\n", " ")[:220]
    entry = f"- [{sha_short}] {line}"
    return base.rstrip() + f"\n\n{marker}\n\n" + entry + "\n" + "\n".join(old) + "\n"


# ---------------------------------------------------------------------------
# 需求/缺陷追溯：AI 只做候选复核与「缺什么证据」的补充解读
# 注意：AI 不参与关联定级、不参与证据定档，更不判断「是否已修复」
# ---------------------------------------------------------------------------

def judge_issue_link(cfg: SystemConfig, issue: Any, ca: Any) -> dict | None:
    """复核一条语义关联候选。失败或不可用返回 None，交由确定性逻辑裁决。"""
    system = SYSTEM_BASE + (
        "任务：判断一条 Git 提交是否在实现/修复给定的需求或缺陷。严格输出 JSON："
        '{"related": true, "confidence": 0, "reason": "不超过40字的依据"}'
        "铁律：只依据给定的提交说明与影响文件；信息不足时 related 必须为 false；"
        "严禁把「同属一个模块」「都是退款相关」这类宽泛相似当成关联依据。"
    )
    user = (f"事项类型：{getattr(issue, 'issue_type', '')}\n"
            f"编号：{getattr(issue, 'external_id', '')}\n"
            f"标题：{getattr(issue, 'title', '')}\n"
            f"描述：{(getattr(issue, 'description', '') or '')[:300]}\n\n"
            f"提交说明：{(getattr(ca, 'message', '') or '')[:300]}\n"
            f"分析结论：{(getattr(ca, 'summary', '') or '')[:200]}\n"
            f"影响文件：{', '.join((getattr(ca, 'affected_files', None) or [])[:12])}")
    try:
        data = chat_json(cfg, system, user, max_tokens=220)
        confidence = data.get("confidence", 0)
        try:
            confidence = max(0, min(100, int(confidence)))
        except (TypeError, ValueError):
            confidence = 0
        return {"related": bool(data.get("related")), "confidence": confidence,
                "reason": str(data.get("reason", ""))[:120]}
    except Exception:  # noqa: BLE001  任何失败都降级为纯确定性关联
        return None


def review_evidence(cfg: SystemConfig, issue: Any, ca: Any,
                    signals: dict, label: str) -> str:
    """基于已确定的四项信号，只补充「还缺什么可验证证据」，不改变评级。"""
    system = SYSTEM_BASE + (
        "任务：基于已确定的证据信号，指出还缺少哪些可验证的证据。严格输出 JSON："
        '{"missing": "不超过60字"}'
        "铁律：不得判断缺陷是否已修复、不得推测运行时行为、不得推翻或改写已有评级；"
        "只说还缺什么证据，例如缺少回归测试、缺少对相关文件的改动、缺少复现步骤。"
    )
    hit = "、".join(k for k, v in signals.items() if k != "notes" and v) or "无"
    miss = "、".join(k for k, v in signals.items() if k != "notes" and not v) or "无"
    user = (f"事项：{getattr(issue, 'external_id', '')} {getattr(issue, 'title', '')}\n"
            f"当前评级：{label}\n命中信号：{hit}\n未命中信号：{miss}\n"
            f"提交说明：{(getattr(ca, 'message', '') or '')[:250]}\n"
            f"影响文件：{', '.join((getattr(ca, 'affected_files', None) or [])[:10])}")
    try:
        data = chat_json(cfg, system, user, max_tokens=200)
        return str(data.get("missing", "")).strip()[:160]
    except Exception:  # noqa: BLE001
        return ""
