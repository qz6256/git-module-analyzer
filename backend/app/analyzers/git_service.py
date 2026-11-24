"""原生 git CLI 封装：跨 Windows / macOS / Linux，UTF-8 容错，超时与错误捕获。

从 legacy app/git_service.py 迁出；原 `from .database import REPOS_DIR` 改为
包内共享路径模块 `from ._paths import REPOS_DIR`（新版 db 层不再暴露该常量）。
其余业务逻辑保持不变。
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ._paths import REPOS_DIR

# 提交字段分隔符：用控制字符避免与 commit message 内容冲突
FIELD_SEP = "\x1f"
RECORD_SEP = "\x1e"
GIT_LOG_FORMAT = f"%H{FIELD_SEP}%an{FIELD_SEP}%aI{FIELD_SEP}%B{RECORD_SEP}"


class GitError(RuntimeError):
    pass


@dataclass
class CommitInfo:
    sha: str
    author: str
    committed_at: datetime | None
    message: str


@dataclass
class ChangedFile:
    path: str
    status: str = "M"          # A / M / D / R / C
    old_path: str = ""
    insertions: int = 0
    deletions: int = 0


@dataclass
class CommitDetail:
    info: CommitInfo
    files: list[ChangedFile] = field(default_factory=list)
    diff_text: str = ""


def run_git(repo_path: str | Path, args: list[str], timeout: int = 90) -> str:
    """执行 git 命令，返回 UTF-8 文本。"""
    cmd = ["git", "-c", "core.quotepath=false", "-c", "i18n.logOutputEncoding=UTF-8",
           "-C", str(repo_path)] + args
    kwargs: dict = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "timeout": timeout,
        "env": {**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C.UTF-8"},
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(cmd, **kwargs)
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"git 命令超时（{timeout}s）：{' '.join(args[:4])}") from exc
    except FileNotFoundError as exc:
        raise GitError("未检测到 git 可执行文件，请先安装 Git 并确保其在 PATH 中") from exc

    out = proc.stdout.decode("utf-8", errors="replace")
    err = proc.stderr.decode("utf-8", errors="replace")
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args[:4])} 失败：{err.strip()[:400]}")
    return out


def is_git_repo(path: str | Path) -> bool:
    try:
        run_git(path, ["rev-parse", "--is-inside-work-tree"], timeout=15)
        return True
    except GitError:
        return False


def clone_remote(url: str, repo_id: int) -> str:
    """远程地址克隆到 workspace/repos/<repo_id>/repo。"""
    target = REPOS_DIR / str(repo_id) / "repo"
    if (target / ".git").exists():
        run_git(target, ["fetch", "--all", "--prune", "--quiet"], timeout=180)
        return str(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "-c", "core.quotepath=false", "clone", "--quiet", url, str(target)]
    kwargs: dict = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "timeout": 300,
                    "env": {**os.environ, "GIT_TERMINAL_PROMPT": "0"}}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.run(cmd, **kwargs)
    if proc.returncode != 0:
        raise GitError(f"克隆失败：{proc.stderr.decode('utf-8', errors='replace').strip()[:400]}")
    return str(target)


def normalize_local_path(raw: str) -> str:
    """归一化用户输入的本地路径（支持 /c/... 形式与 Windows 盘符）。"""
    p = raw.strip().strip('"').strip("'")
    if re.match(r"^/[a-zA-Z]/", p):
        p = p[2].upper() + ":" + p[3:]
    return str(Path(p).expanduser())


def list_branches(repo_path: str) -> list[str]:
    out = run_git(repo_path, ["branch", "--format=%(refname:short)"])
    local = [x.strip() for x in out.splitlines() if x.strip()]
    remote_out = run_git(repo_path, ["branch", "-r", "--format=%(refname:short)"])
    remote = [x.strip().split("/", 1)[1] for x in remote_out.splitlines()
              if x.strip() and "/" in x.strip() and "HEAD" not in x]
    return list(dict.fromkeys(local + remote))


def current_branch(repo_path: str) -> str:
    return run_git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()


def resolve_ref(repo_path: str, branch: str) -> str | None:
    """按 本地分支 → origin/分支 → 直接 ref 的顺序解析到 commit sha。"""
    for ref in (branch, f"origin/{branch}", f"refs/heads/{branch}", f"refs/remotes/origin/{branch}"):
        try:
            sha = run_git(repo_path, ["rev-parse", "--verify", ref], timeout=20).strip()
            if sha:
                return sha
        except GitError:
            continue
    return None


def head_sha(repo_path: str, branch: str = "") -> str | None:
    if branch:
        return resolve_ref(repo_path, branch)
    try:
        return run_git(repo_path, ["rev-parse", "HEAD"]).strip()
    except GitError:
        return None


def fetch_all(repo_path: str) -> None:
    try:
        run_git(repo_path, ["fetch", "--all", "--prune", "--quiet"], timeout=180)
    except GitError:
        pass  # 本地仓库 / 离线场景不阻断


def parse_commit_log(raw: str) -> list[CommitInfo]:
    result: list[CommitInfo] = []
    for record in raw.split(RECORD_SEP):
        record = record.strip("\n")
        if not record.strip():
            continue
        parts = record.split(FIELD_SEP)
        if len(parts) < 4:
            continue
        sha, author, date_str = parts[0].strip(), parts[1].strip(), parts[2].strip()
        message = FIELD_SEP.join(parts[3:]).strip()
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            dt = None
        result.append(CommitInfo(sha=sha, author=author, committed_at=dt, message=message))
    return result


def log_range(repo_path: str, since_sha: str, until_ref: str) -> list[CommitInfo]:
    """拉取 since..until 之间的提交，按时间正序返回。"""
    rng = f"{since_sha}..{until_ref}" if since_sha else until_ref
    raw = run_git(repo_path, ["log", "--reverse", "--date=iso-strict",
                              f"--format={GIT_LOG_FORMAT}", rng, "--"])
    return parse_commit_log(raw)


def log_recent(repo_path: str, ref: str, limit: int = 100) -> list[CommitInfo]:
    raw = run_git(repo_path, ["log", f"-n{limit}", "--date=iso-strict",
                              f"--format={GIT_LOG_FORMAT}", ref, "--"])
    return parse_commit_log(raw)


def numstat(repo_path: str, sha: str) -> dict[str, tuple[int, int, str]]:
    """返回 {path: (insertions, deletions, status)}。"""
    raw = run_git(repo_path, ["show", "--format=", "--numstat", "--find-renames", "-M", sha])
    result: dict[str, tuple[int, int, str]] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        add, dele, path = parts[0], parts[1], "\t".join(parts[2:])
        if "{" in path and "=>" in path:  # 重命名简写 a/{old=>new}/x.py
            m = re.match(r"(.*)\{.*=>\s*(.*)\}(.*)", path)
            if m:
                path = (m.group(1) + m.group(2) + m.group(3)).strip("/")
        if " => " in path:
            path = path.split(" => ", 1)[1].strip()
        try:
            result[path] = (int(add), int(dele), "M")
        except ValueError:  # 二进制文件显示 '-'
            result[path] = (0, 0, "B")
    return result


def name_status(repo_path: str, sha: str) -> dict[str, str]:
    raw = run_git(repo_path, ["show", "--format=", "--name-status", "-M", sha])
    result: dict[str, str] = {}
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0] and parts[0][0] in "AMDRCT":
            status = parts[0][0]
            path = parts[-1].strip()
            if "{" in path and "=>" in path:
                m = re.match(r"(.*)\{.*=>\s*(.*)\}(.*)", path)
                if m:
                    path = (m.group(1) + m.group(2) + m.group(3)).strip("/")
            result[path] = status
    return result


def commit_diff(repo_path: str, sha: str, max_chars: int = 12000) -> str:
    """获取提交的完整 diff，超限时按文件边界截断。"""
    raw = run_git(repo_path, ["show", "--format=", "--no-ext-diff", "--no-color",
                              "--unified=3", "--find-renames", "-M", sha], timeout=120)
    if len(raw) <= max_chars:
        return raw
    chunks = re.split(r"(?=^diff --git )", raw, flags=re.M)
    kept, size = [], 0
    for ch in chunks:
        if size + len(ch) > max_chars:
            kept.append(f"\n[diff 已按 max_diff_chars={max_chars} 截断，共 {len(chunks) - 1} 个文件]")
            break
        kept.append(ch)
        size += len(ch)
    return "".join(kept)


def file_content(repo_path: str, path: str, ref: str = "HEAD") -> str:
    try:
        return run_git(repo_path, ["show", f"{ref}:{path}"], timeout=30)
    except GitError:
        return ""


def tracked_files(repo_path: str, ref: str = "HEAD") -> list[str]:
    try:
        raw = run_git(repo_path, ["ls-tree", "-r", "--name-only", ref])
    except GitError:
        raw = run_git(repo_path, ["ls-files"])
    return [x.strip() for x in raw.splitlines() if x.strip()]


def co_change_stats(repo_path: str, ref: str, limit: int = 150) -> list[dict]:
    """统计近 N 条提交里的文件共变关系（Co-change），供模块聚类参考。"""
    raw = run_git(repo_path, ["log", f"-n{limit}", "--format=", "--name-only", ref, "--"], timeout=120)
    pair_count: dict[tuple[str, str], int] = {}
    single_count: dict[str, int] = {}
    for block in raw.split("\n\n"):
        files = sorted({f.strip() for f in block.splitlines() if f.strip()})
        if not files:
            continue
        for f in files:
            single_count[f] = single_count.get(f, 0) + 1
        if len(files) > 25:
            continue
        for i, a in enumerate(files):
            for b in files[i + 1:]:
                pair_count[(a, b)] = pair_count.get((a, b), 0) + 1
    pairs = [{"a": a, "b": b, "count": c} for (a, b), c in
             sorted(pair_count.items(), key=lambda kv: -kv[1])[:40]]
    hot = [{"path": p, "count": c} for p, c in
           sorted(single_count.items(), key=lambda kv: -kv[1])[:40]]
    return [{"pairs": pairs, "hot_files": hot}]
