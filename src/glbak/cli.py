from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from loguru import logger

from . import __version__
from .clone import clone_all
from .gitlab_api import GitLabClient
from .logging_utils import setup_logging
from .settings import Settings

console = Console()


def main(
    group_path: str = typer.Argument(..., help="Full path of the root GitLab group, e.g. 'company/legacy'."),
    *,
    base_url: Optional[str] = typer.Option(None, "--base-url", help="GitLab base URL, e.g. https://gitlab.com"),
    dest: Optional[Path] = typer.Option(None, "--dest", help="Destination directory for backups."),
    concurrency: Optional[int] = typer.Option(None, "--concurrency", help="Parallel clones."),
    timeout: Optional[float] = typer.Option(None, "--timeout", help="HTTP timeout seconds."),
    verify_ssl: Optional[bool] = typer.Option(None, "--verify-ssl/--no-verify-ssl", help="Verify TLS certs."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not modify filesystem or run git."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable debug logging."),
) -> None:
    """Single-command CLI: `glbak <group_path> [options]`."""
    setup_logging(verbose)

    cfg = Settings()
    base_url_val = base_url or cfg.base_url

    dest_input = str(dest or cfg.dest_dir)
    dest_dir_val = Path(os.path.expanduser(dest_input)).resolve()

    concurrency_val = concurrency if concurrency is not None else cfg.concurrency
    timeout_val = timeout if timeout is not None else cfg.timeout
    verify_ssl_val = verify_ssl if verify_ssl is not None else cfg.verify_ssl

    token = os.environ.get("GITLAB_TOKEN")
    if not token:
        raise typer.BadParameter("Environment variable GITLAB_TOKEN is required.")

    console.print(f"[bold]glbak {__version__}[/bold]")
    console.print(f"Base URL: {base_url_val}")
    console.print(f"Group:    {group_path}")
    console.print(f"Dest:     {dest_dir_val}")
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
        concurrency=max(1, concurrency_val),
        dry_run=dry_run,
        console=console,
        group_root=group_path,
    )

    by_status: dict[str, int] = {}
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


def entrypoint() -> None:
    typer.run(main)


if __name__ == "__main__":
    entrypoint()
