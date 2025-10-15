from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
from loguru import logger
from rich.console import Console

from . import __version__
from .clone import clone_all
from .gitlab_api import GitLabClient
from .logging_utils import setup_logging
from .settings import Settings

app = typer.Typer(help="Backup all repos (all branches) from a GitLab group (including subgroups).")
console = Console()


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", help="Enable debug logging."),
) -> None:
    setup_logging(verbose)


@app.command("backup")
def backup(
    group_path: str = typer.Argument(..., help="Full path of the root GitLab group, e.g. 'company/legacy'."),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="GitLab base URL, e.g. https://gitlab.com"),
    dest: Optional[Path] = typer.Option(None, "--dest", help="Destination directory for backups."),
    concurrency: Optional[int] = typer.Option(None, "--concurrency", help="Parallel clones."),
    timeout: Optional[float] = typer.Option(None, "--timeout", help="HTTP timeout seconds."),
    verify_ssl: Optional[bool] = typer.Option(None, "--verify-ssl/--no-verify-ssl", help="Verify TLS certs."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not modify filesystem or run git."),
) -> None:
    """Backup a GitLab group and all its projects into local mirror repositories."""
    cfg = Settings()
    # Apply CLI overrides
    base_url_val = base_url or cfg.base_url
    dest_dir_val = dest or cfg.dest_dir
    concurrency_val = concurrency if concurrency is not None else cfg.concurrency
    timeout_val = timeout if timeout is not None else cfg.timeout
    verify_ssl_val = verify_ssl if verify_ssl is not None else cfg.verify_ssl

    token = os.environ.get("GITLAB_TOKEN")
    if not token:
        raise typer.BadParameter("Environment variable GITLAB_TOKEN is required.")

    console.print(f"[bold]gitlab-backup {__version__}[/bold]")
    console.print(f"Base URL: {base_url_val}")
    console.print(f"Group:    {group_path}")
    console.print(f"Dest:     {dest_dir_val.resolve()}")
    if dry_run:
        console.print("[yellow]Dry run: no changes will be made[/yellow]")

    client = GitLabClient(
        base_url=base_url_val,
        token=token,
        timeout=timeout_val,
        verify_ssl=verify_ssl_val,
    )

    try:
        group_id = client.get_group_id_by_path(group_path)
        projects = client.list_all_projects(group_id)
    finally:
        client.close()

    if not projects:
        console.print("[yellow]No projects found under the specified group path.[/yellow]")
        raise typer.Exit(code=0)

    console.print(f"Discovered projects: {len(projects)}")

    results = clone_all(
        projects=projects,
        base_dir=dest_dir_val,
        token_for_clone=token,
        concurrency=concurrency_val,
        dry_run=dry_run,
        console=console,
    )

    by_status = {}
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1

    console.print("\n[bold]Summary[/bold]")
    for key in sorted(by_status):
        console.print(f"{key:>8}: {by_status[key]}")

    failures = [r for r in results if r.status == "failed"]
    if failures:
        console.print("\n[red]Failures[/red]")
        for r in failures[:20]:
            console.print(f"- {r.project.path_with_namespace}: {r.message.strip()[:200]}")
        raise typer.Exit(code=2)

    logger.info("Done")
