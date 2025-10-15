from __future__ import annotations

import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import urlparse, urlunparse, quote

from git import Git, Repo
from git.exc import GitCommandError, InvalidGitRepositoryError
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn

from .gitlab_api import Project


@dataclass(frozen=True)
class CloneResult:
    project: Project
    dest: Path
    status: str  # "cloned" | "updated" | "skipped" | "failed"
    message: str = ""


def embed_token(url: str, token: str) -> str:
    """Return https URL with oauth2:<token>@ embedded for Git clone."""
    if not token:
        return url
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return url  # only modify https URLs
    safe_token = quote(token, safe="")
    netloc = f"oauth2:{safe_token}@{parsed.netloc}"
    return urlunparse((parsed.scheme, netloc, parsed.path, "", "", ""))


def repo_dest(base_dir: Path, project: Project) -> Path:
    # Mirror clones are bare repos that usually end with .git
    rel = Path(project.path_with_namespace + ".git")
    return (base_dir / rel).resolve()


def clone_or_update(
    *,
    project: Project,
    base_dir: Path,
    remote_url: str,
    dry_run: bool = False,
) -> CloneResult:
    dest = repo_dest(base_dir, project)
    if dry_run:
        return CloneResult(project=project, dest=dest, status="skipped", message="dry-run")

    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        try:
            repo = Repo(dest)
        except InvalidGitRepositoryError:
            # Destination path exists but is not a git repo: cleanup and re-clone
            shutil.rmtree(dest, ignore_errors=True)
            return _clone_fresh(project=project, dest=dest, remote_url=remote_url)

        try:
            # Ensure remote URL is correct
            try:
                repo.remotes.origin.set_url(remote_url)
            except Exception:
                repo.git.remote("set-url", "origin", remote_url)

            # Mirror update: all refs, prune branches and tags
            repo.git.fetch("--prune", "--prune-tags", "--all", "--tags", "--force")
            return CloneResult(project=project, dest=dest, status="updated", message="fetch ok")
        except GitCommandError as e:
            return CloneResult(project=project, dest=dest, status="failed", message=str(e))
    else:
        return _clone_fresh(project=project, dest=dest, remote_url=remote_url)


def _clone_fresh(*, project: Project, dest: Path, remote_url: str) -> CloneResult:
    try:
        # GitPython does not expose mirror=True directly, pass raw option.
        Git().clone("--mirror", remote_url, str(dest))
        return CloneResult(project=project, dest=dest, status="cloned", message="clone ok")
    except GitCommandError as e:
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        return CloneResult(project=project, dest=dest, status="failed", message=str(e))


def clone_all(
    *,
    projects: Iterable[Project],
    base_dir: Path,
    token_for_clone: str,
    concurrency: int,
    dry_run: bool,
    console: Console,
) -> List[CloneResult]:
    projs = list(projects)
    total = len(projs)
    results: List[CloneResult] = []

    task_desc = "Cloning mirrors"
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        main_task = progress.add_task(task_desc, total=total)

        def work(p: Project) -> CloneResult:
            remote = embed_token(p.http_url_to_repo, token_for_clone)
            return clone_or_update(project=p, base_dir=base_dir, remote_url=remote, dry_run=dry_run)

        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
            futures = [pool.submit(work, p) for p in projs]
            for fut in as_completed(futures):
                res = fut.result()
                results.append(res)
                progress.advance(main_task, 1)

    logger.debug("Clone/update completed for {} projects", len(results))
    return results
