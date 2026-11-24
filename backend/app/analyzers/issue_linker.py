"""需求/缺陷 ↔ Git 提交 的自动关联与「修复证据充分性」评级。

设计原则（与整体系统一致）：
1. 关联分级：显式引用 > 语义推测 > 上下文推断，每级都带置信度与证据文本；
2. 绝不承诺「已修复」：只评估四项可验证的信号，输出证据充分性三档结论；
3. 本地确定性优先：无 LLM 也能完整跑通；LLM 只做候选复核与证据解读，不参与定档；
4. 可纠错：推测/推断关联默认待确认，人工可确认或否决，否决后不再自动重建。

从 legacy app/issue_linker.py 迁出：模型改从 ..models.knowledge 导入；所有 db 参数
保持由 service 层注入 Session（无全局会话导入）；写入 Issue / IssueCommitLink 时
额外补齐新版冗余列 project_id（通过 repo_id 反查 Repository.project_id）。
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import llm_service
from ..models.knowledge import (CommitAnalysis, FileChangeEvent, Issue, IssueCommitLink,
                                ModuleChangeEvent, SystemConfig)
from ..models.project import Repository

NO_MOTIVATION = llm_service.NO_MOTIVATION


def _project_id_of_repo(db: Session, repo_id: int) -> int | None:
    """反查 Repository.project_id，用于补齐新版分析表的 project_id 冗余列。"""
    repo = db.get(Repository, repo_id)
    return getattr(repo, "project_id", None) if repo is not None else None

# ---------------------------------------------------------------------------
# 一、引用号解析
# ---------------------------------------------------------------------------

_ID = r"(?:[A-Za-z][A-Za-z0-9_-]{0,20}-\d{1,7}|\d{1,7})"
_KEYWORD = (r"(?:fix(?:es|ed)?|close[sd]?|resolve[sd]?|refs?|references?|see|"
            r"issue|bug|story|task|需求|缺陷|问题|修复|关联|解决|修正)")

RE_HASH = re.compile(r"[#＃]\s*(\d{1,7})")
RE_KEYWORD = re.compile(
    rf"(?<![A-Za-z]){_KEYWORD}\s*[:：=#＃\s]\s*[#＃]?({_ID})", re.I)
RE_JIRA = re.compile(r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9_]{1,20}-\d{1,7})(?![A-Za-z0-9])")

RE_TEST_PATH = re.compile(r"(?:^|/)(?:tests?|specs?|__tests__)/|(?:^|/)test_|_test\.|\.test\.|\.spec\.")
RE_FIX_DECL = re.compile(
    r"(?i)(?<![A-Za-z])(?:fix|fixed|fixes|hotfix|resolve|resolved|close|closed|reopen|patch)(?![A-Za-z])"
    r"|修复|解决|修正|关闭|回归|兜底|纠错|已处理")

# 常见无区分度的中文 bigram，避免语义匹配被虚词污染
_BAD_BIGRAM = {
    "进行", "导致", "出现", "需要", "应该", "可以", "能够", "以及", "一个", "这个", "那个",
    "时候", "问题", "处理", "相关", "修改", "调整", "新增", "支持", "使用", "当前", "之后",
    "之前", "如果", "因为", "所以", "但是", "并且", "通过", "对于", "关于", "以及", "中的",
}


def normalize_ext_id(raw: str) -> str:
    """把 '#123' / '123' / 'BUG-1' 规范化为可比对的键。纯数字 → N123，字母数字 → 去分隔符大写。"""
    s = re.sub(r"[^0-9A-Za-z]", "", (raw or "")).upper()
    if s.isdigit():
        return "N" + str(int(s))
    return s


def _numeric_key(raw: str) -> str:
    digits = re.findall(r"\d{1,7}", raw or "")
    return "N" + str(int(digits[-1])) if digits else ""


def parse_references(message: str) -> list[str]:
    """抽取提交说明里出现的编号，返回规范化键（去重保序）。

    支持：fix #123 / closes #456 / refs #7 / #123 / BUG-1 / PROJ-42 /
          「修复 缺陷#123」「需求: 789」「关联 story=12」等常见写法。
    """
    text = message or ""
    keys: list[str] = []
    for regex in (RE_HASH, RE_KEYWORD, RE_JIRA):
        for m in regex.finditer(text):
            k = normalize_ext_id(m.group(1))
            if k and k not in keys:
                keys.append(k)
    return keys


def issue_keys(issue: Issue) -> list[str]:
    """一个需求可能对应多种写法：主编号 + 纯数字编号（用于兼容禅道 bug#123）。"""
    main = normalize_ext_id(issue.external_id)
    num = _numeric_key(issue.external_id)
    out = [main] if main else []
    if num and num not in out:
        out.append(num)
    return out


def build_index(issues: list[Issue]) -> dict[str, list[Issue]]:
    idx: dict[str, list[Issue]] = {}
    for it in issues:
        for k in issue_keys(it):
            idx.setdefault(k, []).append(it)
    return idx


# ---------------------------------------------------------------------------
# 二、语义关键词
# ---------------------------------------------------------------------------

def extract_keywords(issue: Issue) -> list[str]:
    """确定性关键词：英文词 + 中文 bigram，不引入分词依赖，离线可复现。"""
    text = f"{issue.title or ''} {issue.description or ''}"[:800]
    chunks = re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2,}", text)
    out: list[str] = []
    for ch in chunks:
        if re.match(r"^[A-Za-z]", ch):
            t = ch.lower()
            if len(t) >= 3 and t not in {"the", "and", "for", "fix", "bug", "with", "from"}:
                out.append(t)
        else:
            for i in range(len(ch) - 1):
                bg = ch[i:i + 2]
                if bg not in _BAD_BIGRAM:
                    out.append(bg)
    seen: set[str] = set()
    uniq = []
    for t in out:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq[:40]


def semantic_score(issue: Issue, ca: CommitAnalysis) -> tuple[int, list[str]]:
    """关键词重合度评分（0-85），返回分数与命中的词。"""
    kws = list(issue.keywords or []) or extract_keywords(issue)
    if not kws:
        return 0, []
    hay = " ".join([ca.message or "", ca.summary or "",
                    " ".join(ca.affected_files or [])]).lower()
    hits = [k for k in kws if k and k.lower() in hay]
    if not hits:
        return 0, []
    ratio = len(hits) / len(kws)
    score = round(45 * ratio) + min(30, len(hits) * 6)
    # 登记的相关路径被触及，额外加分（最强佐证）
    related = [p.lower().strip() for p in (issue.related_paths or []) if p.strip()]
    paths = [p.lower() for p in (ca.affected_files or [])]
    if related and any(r in p or p in r for r in related for p in paths):
        score += 20
    return min(85, score), hits[:8]


def _inferred_match(issue: Issue, ca: CommitAnalysis) -> bool:
    """弱证据：报告人=提交人 + 时间窗 14 天 + 触及登记的相关路径，三者同时满足才提示。"""
    if not issue.occurred_at or not ca.committed_at:
        return False
    if (issue.reporter or "").strip() and (issue.reporter or "").strip() != (ca.author or "").strip():
        return False
    if abs((ca.committed_at - issue.occurred_at).days) > 14:
        return False
    related = [p.lower().strip() for p in (issue.related_paths or []) if p.strip()]
    paths = [p.lower() for p in (ca.affected_files or [])]
    return bool(related and any(r in p or p in r for r in related for p in paths))


# ---------------------------------------------------------------------------
# 三、四项信号与证据评级
# ---------------------------------------------------------------------------

SIGNAL_LABELS = {
    "explicit_ref": "显式引用",
    "file_hit": "文件命中",
    "test_change": "测试改动",
    "fix_declaration": "修复声明",
}


def compute_signals(issue: Issue, ca: CommitAnalysis, link_type: str) -> dict[str, Any]:
    msg = ca.message or ""
    paths = [p.lower() for p in (ca.affected_files or [])]
    related = [p.lower().strip() for p in (issue.related_paths or []) if p.strip()]
    notes: list[str] = []

    if related:
        file_hit = any(r in p or p in r for r in related for p in paths)
        notes.append("按登记的相关路径比对" + ("，已命中" if file_hit else "，未命中"))
    else:
        kws = list(issue.keywords or []) or extract_keywords(issue)
        file_hit = any(k.lower() in p for k in kws[:20] for p in paths)
        notes.append("未登记相关路径，按标题关键词比对文件路径（判定力较弱）")

    test_change = any(RE_TEST_PATH.search(p) for p in paths)
    fix_declaration = bool(RE_FIX_DECL.search(msg))
    explicit_ref = link_type in ("explicit", "manual")
    if explicit_ref:
        notes.append("提交说明明确引用该编号")
    if not ca.is_high_signal:
        notes.append("该提交被判定为低信号（纯格式化/噪音），关联仅供参考")

    return {
        "explicit_ref": explicit_ref,
        "file_hit": file_hit,
        "test_change": test_change,
        "fix_declaration": fix_declaration,
        "notes": notes,
    }


def assess(signals: dict[str, Any], issue_type: str) -> tuple[str, str, str]:
    """只做证据充分性评级，绝不输出「已修复 / 未修复」这类运行时判断。"""
    hits = sum(1 for k in SIGNAL_LABELS if signals.get(k))
    noun = "修复" if issue_type == "bug" else "实现"
    if signals.get("explicit_ref") and not signals.get("file_hit") and not signals.get("test_change"):
        return ("review", "需人工复核",
                f"提交明确引用该{'缺陷' if issue_type == 'bug' else '需求'}，但未触及任何相关文件且无测试改动，"
                "信号相互矛盾，不能据此判断结论。")
    if signals.get("fix_declaration") and not signals.get("file_hit") and hits <= 2:
        return ("review", "需人工复核",
                f"提交声明{noun}，但改动文件与登记范围无交集且缺少测试证据，建议人工确认。")
    if hits >= 3:
        return ("strong", f"较强{noun}证据",
                f"四项信号命中 {hits} 项，证据较为充分；系统不验证运行时结果，仍需人工确认实际效果。")
    return ("weak", "仅有关联，证据不足",
            f"四项信号仅命中 {hits} 项，只能说明这条提交与该事项有关，无法判断{noun}情况。")


# ---------------------------------------------------------------------------
# 四、关联落库（单条提交 / 全仓回填）
# ---------------------------------------------------------------------------

def _upgrade_motivation(db: Session, ca: CommitAnalysis, issue: Issue) -> None:
    """把需求单升级为「为什么改」的权威来源。

    - 原本「原因未知」→ 直接替换为需求单来源；
    - 原本已有 commit message 证据 → 保留原文，追加需求单引用（不覆盖已有证据）；
    - 已包含该编号 → 不重复追加，保证重复同步幂等。
    """
    label = "缺陷" if issue.issue_type == "bug" else "需求"
    link_text = f"关联{label} {issue.external_id}：{issue.title or '（无标题）'}（来自需求登记）"
    marker = f"关联{label} {issue.external_id}"

    def upgrade(row) -> None:
        cur = (getattr(row, "motivation", "") or "").strip()
        if not cur or cur == NO_MOTIVATION:
            new = link_text
        elif marker not in cur:
            new = f"{cur}；{link_text}"
        else:
            new = cur
        row.motivation = new[:600]
        row.evidence_source = "需求登记"

    upgrade(ca)
    for model, cond in ((FileChangeEvent, FileChangeEvent.commit_sha == ca.commit_sha),
                        (ModuleChangeEvent, ModuleChangeEvent.commit_sha == ca.commit_sha)):
        for row in db.scalars(select(model).where(cond, model.repo_id == ca.repo_id)).all():
            upgrade(row)


def link_commit(db: Session, repo_id: int, ca: CommitAnalysis,
                issues: list[Issue] | None = None,
                cfg: SystemConfig | None = None,
                use_llm: bool = False) -> list[IssueCommitLink]:
    """为一条提交建立关联。幂等：已存在（含被否决）的关联不会被重建。"""
    project_id = _project_id_of_repo(db, repo_id)
    issues = issues if issues is not None else list(
        db.scalars(select(Issue).where(Issue.repo_id == repo_id)).all())
    if not issues:
        return []
    existing = {l.issue_id for l in db.scalars(
        select(IssueCommitLink).where(IssueCommitLink.repo_id == repo_id,
                                      IssueCommitLink.commit_sha == ca.commit_sha)).all()}
    index = build_index(issues)
    candidates: dict[int, tuple[str, int, str]] = {}

    def put(issue: Issue, kind: str, conf: int, evidence: str) -> None:
        if issue.id in existing:
            return
        old = candidates.get(issue.id)
        rank = {"explicit": 3, "manual": 3, "semantic": 2, "inferred": 1}
        if old is None or rank[kind] > rank[old[0]] or (rank[kind] == rank[old[0]] and conf > old[1]):
            candidates[issue.id] = (kind, conf, evidence)

    # ① 显式引用
    for key in parse_references(ca.message or ""):
        matched = index.get(key) or []
        # 编号歧义时优先取主键精确匹配的那个
        exact = [i for i in matched if normalize_ext_id(i.external_id) == key]
        for issue in (exact or matched):
            put(issue, "explicit", 100, f"提交说明明确引用编号 {key}（匹配 {issue.external_id}）")

    # ② 语义推测 + ③ 上下文推断
    for issue in issues:
        if issue.id in existing or issue.id in candidates:
            continue
        score, hits = semantic_score(issue, ca)
        if len(hits) >= 2 and score >= 35:
            put(issue, "semantic", score,
                f"标题关键词与提交说明/影响文件重合：{'、'.join(hits)}")
        elif _inferred_match(issue, ca):
            put(issue, "inferred", 30,
                "同一报告人/提交人、时间窗 14 天内且触及登记的相关路径（弱证据，仅供参考）")

    # LLM 只复核「模棱两可」的语义候选，不参与显式引用与证据定档
    llm_judged = 0
    if use_llm and cfg is not None and cfg.llm_enabled and cfg.api_key:
        for iid, (kind, conf, evidence) in list(candidates.items()):
            if kind != "semantic" or not (35 <= conf < 75) or llm_judged >= 2:
                continue
            issue = next((i for i in issues if i.id == iid), None)
            if not issue:
                continue
            note = llm_service.judge_issue_link(cfg, issue, ca)
            llm_judged += 1
            if not note:
                continue
            if note.get("related") is False:
                candidates.pop(iid, None)
            else:
                bump = 8 if note.get("related") is True else 0
                candidates[iid] = (kind, min(85, conf + bump),
                                   evidence + f"；AI 复核：{note.get('reason', '')[:100]}")

    created: list[IssueCommitLink] = []
    for iid, (kind, conf, evidence) in candidates.items():
        issue = next((i for i in issues if i.id == iid), None)
        if not issue:
            continue
        signals = compute_signals(issue, ca, kind)
        key, label, note = assess(signals, issue.issue_type)
        llm_note = ""
        if use_llm and cfg is not None and cfg.llm_enabled and cfg.api_key and key in ("strong", "review"):
            llm_note = llm_service.review_evidence(cfg, issue, ca, signals, label) or ""
        link = IssueCommitLink(
            repo_id=repo_id, project_id=project_id, issue_id=issue.id, commit_sha=ca.commit_sha,
            branch=ca.branch or "", link_type=kind, confidence=conf,
            evidence=evidence, signals=signals, assessment=key,
            assessment_label=label, assessment_note=note, llm_note=llm_note,
            review_status="confirmed" if kind == "explicit" else "pending")
        db.add(link)
        created.append(link)
        if kind == "explicit":
            _upgrade_motivation(db, ca, issue)
    if created:
        db.flush()
    return created


def relink_repo(db: Session, repo_id: int, use_llm: bool = False,
                only_new: bool = True) -> dict:
    """新增需求后批量回填历史提交的关联。默认只处理尚未建立任何关联的提交。"""
    issues = list(db.scalars(select(Issue).where(Issue.repo_id == repo_id)).all())
    cfg = llm_service.get_config(db)
    commits = list(db.scalars(select(CommitAnalysis)
                              .where(CommitAnalysis.repo_id == repo_id)
                              .order_by(CommitAnalysis.committed_at.asc().nullslast(),
                                        CommitAnalysis.id.asc())).all())
    linked_shas = set(db.scalars(select(IssueCommitLink.commit_sha)
                                 .where(IssueCommitLink.repo_id == repo_id)).all()) if only_new else set()
    created = 0
    for ca in commits:
        if ca.commit_sha in linked_shas:
            continue
        created += len(link_commit(db, repo_id, ca, issues, cfg, use_llm=use_llm))
    db.commit()
    return {"issues": len(issues), "commits": len(commits), "new_links": created}


# ---------------------------------------------------------------------------
# 五、需求登记与 CSV 导入
# ---------------------------------------------------------------------------

CSV_ALIASES: dict[str, list[str]] = {
    "external_id": ["external_id", "编号", "id", "ID", "缺陷编号", "需求编号", "工单号", "issue_id"],
    "issue_type": ["issue_type", "类型", "type", "类别"],
    "title": ["title", "标题", "名称", "主题", "摘要"],
    "description": ["description", "描述", "详情", "内容", "重现步骤"],
    "status": ["status", "状态"],
    "source": ["source", "来源"],
    "external_url": ["external_url", "链接", "url", "地址", "URL"],
    "reporter": ["reporter", "创建人", "报告人", "提出人", "指派人"],
    "keywords": ["keywords", "关键词"],
    "related_paths": ["related_paths", "相关路径", "涉及文件", "路径", "文件路径"],
    "occurred_at": ["occurred_at", "创建时间", "提出时间", "日期", "created_at"],
}


def _norm_type(v: str) -> str:
    s = (v or "").strip().lower()
    return "story" if s in ("story", "需求", "功能", "feature", "task", "任务") else "bug"


def _norm_status(v: str) -> str:
    s = (v or "").strip().lower()
    if s in ("resolved", "已解决", "已修复", "fixed", "done"):
        return "resolved"
    if s in ("closed", "已关闭", "关闭"):
        return "closed"
    return "open"


def _parse_dt(v: str) -> datetime | None:
    s = (v or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _split_list(v: str) -> list[str]:
    return [x.strip() for x in re.split(r"[,，;；|\s]+", v or "") if x.strip()]


def upsert_issue(db: Session, repo_id: int, data: dict[str, Any]) -> tuple[Issue, bool]:
    """按 external_id 新增或更新需求；已有关联记录不受影响。返回 (实体, 是否新建)。"""
    ext = str(data.get("external_id") or "").strip()
    if not ext:
        raise ValueError("external_id 不能为空")
    issue = db.scalar(select(Issue).where(Issue.repo_id == repo_id,
                                          Issue.external_id == ext))
    created = issue is None
    if issue is None:
        issue = Issue(repo_id=repo_id, project_id=_project_id_of_repo(db, repo_id),
                      external_id=ext)
        db.add(issue)
    for field in ("title", "description", "external_url", "reporter"):
        if field in data and data[field] is not None:
            setattr(issue, field, str(data[field]).strip())
    if "issue_type" in data:
        issue.issue_type = _norm_type(str(data["issue_type"]))
    if "status" in data:
        issue.status = _norm_status(str(data["status"]))
    if "source" in data and data["source"]:
        issue.source = str(data["source"]).strip()[:30]
    for field in ("keywords", "related_paths"):
        if field in data:
            v = data[field]
            setattr(issue, field, list(v) if isinstance(v, list) else _split_list(str(v)))
    if data.get("occurred_at"):
        issue.occurred_at = _parse_dt(str(data["occurred_at"])) or issue.occurred_at
    db.flush()
    if not issue.keywords:
        issue.keywords = extract_keywords(issue)
    return issue, created


def import_csv(db: Session, repo_id: int, text: str, source: str = "csv") -> dict:
    """导入禅道/Jira/自制的 CSV 导出。列名支持中英文别名，重复编号做更新。"""
    raw = (text or "").lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        raise ValueError("CSV 为空或缺少表头")
    headers = {str(h).strip().lower(): str(h).strip() for h in reader.fieldnames}
    colmap: dict[str, str] = {}
    for field, aliases in CSV_ALIASES.items():
        for a in aliases:
            if a.lower() in headers:
                colmap[field] = headers[a.lower()]
                break
    if "external_id" not in colmap:
        raise ValueError("CSV 缺少编号列（external_id / 编号 / ID）")
    created = updated = skipped = 0
    for row in reader:
        data: dict[str, Any] = {f: (row.get(col) or "").strip() for f, col in colmap.items()}
        data.setdefault("source", source)
        if not data.get("external_id"):
            skipped += 1
            continue
        if not data.get("title"):
            data["title"] = f"（无标题）{data['external_id']}"
        try:
            _, is_new = upsert_issue(db, repo_id, data)
        except ValueError:
            skipped += 1
            continue
        created += int(is_new)
        updated += int(not is_new)
    db.commit()
    return {"created": created, "updated": updated, "skipped": skipped,
            "columns": list(colmap.keys())}


# ---------------------------------------------------------------------------
# 六、人工确认 / 否决
# ---------------------------------------------------------------------------

def review_link(db: Session, link_id: int, action: str) -> dict:
    link = db.get(IssueCommitLink, link_id)
    if not link:
        raise ValueError("关联记录不存在")
    if action not in ("confirm", "reject"):
        raise ValueError("action 只能是 confirm 或 reject")
    link.review_status = "confirmed" if action == "confirm" else "rejected"
    link.decided_at = datetime.now()
    if action == "confirm":
        ca = db.scalar(select(CommitAnalysis).where(
            CommitAnalysis.repo_id == link.repo_id,
            CommitAnalysis.commit_sha == link.commit_sha))
        issue = db.get(Issue, link.issue_id)
        if ca and issue:
            signals = dict(link.signals or {})
            signals["explicit_ref"] = True
            link.signals = signals
            key, label, note = assess(signals, issue.issue_type)
            link.assessment, link.assessment_label, link.assessment_note = key, label, note
            _upgrade_motivation(db, ca, issue)
    db.commit()
    return {"id": link_id, "review_status": link.review_status,
            "assessment": link.assessment, "assessment_label": link.assessment_label}
