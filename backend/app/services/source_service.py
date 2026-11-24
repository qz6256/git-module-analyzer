"""源码只读预览服务。

源码不入库，按 SourceFile.repo_id 找到本地 Git 仓库，再用 git show 从指定引用读取。
只做预览：不允许编辑、保存或回写仓库。
"""
from __future__ import annotations

from pathlib import Path

from ..analyzers import git_service
from ..core.errors import NotFoundError
from ..models.project import Repository
from ..repositories import knowledge_repo

MAX_BYTES = 200 * 1024
MAX_LINES = 2000

SKIP_NAMES = {
    ".env", ".env.local", ".env.production", ".env.development",
    "id_rsa", "id_ed25519", "credentials", "credentials.json",
}
SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
    ".zip", ".tar", ".gz", ".7z", ".jar", ".class", ".pyc",
    ".lock", ".sum", ".min.js", ".min.css", ".woff", ".woff2", ".ttf",
    ".pem", ".key", ".p12", ".pfx", ".keystore",
}


def read_source(db, file_id: int, branch: str = "") -> dict:
    f = knowledge_repo.get_file(db, file_id)
    if not f:
        raise NotFoundError("文件档案")
    repo = db.get(Repository, f.repo_id)
    if not repo or not repo.local_path:
        return {"path": f.path, "language": f.language, "content": "",
                "truncated": False, "total_lines": 0, "ref": "",
                "reason": "仓库尚未初始化，暂无源码预览"}

    root = Path(repo.local_path).resolve()
    rel = Path(f.path)
    if rel.is_absolute() or ".." in rel.parts:
        return {"path": f.path, "language": f.language, "content": "",
                "truncated": False, "total_lines": 0, "ref": "",
                "reason": "文件路径不合法，已拒绝预览"}
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return {"path": f.path, "language": f.language, "content": "",
                "truncated": False, "total_lines": 0, "ref": "",
                "reason": "文件路径越界，已拒绝预览"}

    if target.name in SKIP_NAMES or target.suffix.lower() in SKIP_SUFFIXES:
        return {"path": f.path, "language": f.language, "content": "",
                "truncated": False, "total_lines": 0, "ref": "",
                "reason": "敏感文件或非文本文件，已跳过预览"}

    ref = branch or repo.default_branch or "HEAD"
    sha = git_service.resolve_ref(root, ref) or "HEAD"
    git_path = rel.as_posix()
    try:
        size_out = git_service.run_git(root, ["cat-file", "-s", f"{sha}:{git_path}"], timeout=15)
        size = int((size_out or "0").strip() or 0)
    except Exception:
        size = 0
    if size > MAX_BYTES:
        return {"path": f.path, "language": f.language, "content": "",
                "truncated": True, "total_lines": 0, "ref": ref,
                "reason": f"文件超过 {MAX_BYTES // 1024}KB，已跳过内容预览"}

    try:
        raw = git_service.show_blob(root, sha, git_path)
    except Exception as exc:
        return {"path": f.path, "language": f.language, "content": "",
                "truncated": False, "total_lines": 0, "ref": ref,
                "reason": f"源码读取失败：{str(exc)[:200]}"}

    if b"\x00" in raw:
        return {"path": f.path, "language": f.language, "content": "",
                "truncated": False, "total_lines": 0, "ref": ref,
                "reason": "检测到二进制内容，已跳过预览"}
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"path": f.path, "language": f.language, "content": "",
                "truncated": False, "total_lines": 0, "ref": ref,
                "reason": "非 UTF-8 文本，已跳过预览"}

    lines = text.splitlines()
    truncated = len(lines) > MAX_LINES
    if truncated:
        text = "\n".join(lines[:MAX_LINES])
    return {"path": f.path, "language": f.language, "content": text,
            "truncated": truncated, "total_lines": len(lines), "ref": ref,
            "reason": ""}
