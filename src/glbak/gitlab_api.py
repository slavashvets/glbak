from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Dict, Iterable, List
from typing import Any, Dict, Iterable, List
from requests import Response
import gitlab
from loguru import logger


@dataclass(frozen=True)
class Project:
    id: int
    path_with_namespace: str
    http_url_to_repo: str
    archived: bool


class GitLabClient:
    """Thin wrapper over GitLab API v4 using python-gitlab."""

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout: float = 30.0,
        verify_ssl: bool = True,
    ) -> None:
        if not token:
            raise ValueError("GitLab API token is required.")
        self._gl = gitlab.Gitlab(
            url=base_url.rstrip("/"),
            private_token=token,
            ssl_verify=verify_ssl,
            timeout=timeout,
        )

    def close(self) -> None:
        return

    def get_group_id_by_path(self, full_path: str) -> int:
        """Resolve a group id by its full path, handling URL encoding safely."""
        encoded = urllib.parse.quote_plus(full_path.strip("/"))
        raw = self._gl.http_get(f"/groups/{encoded}")
        if isinstance(raw, Response):
            data: dict[str, Any] = raw.json()
        else:
            data = raw
        group_id = int(data["id"])
        logger.debug("Resolved group {} -> id {}", full_path, group_id)
        return group_id

    def list_all_projects(self, group_id: int) -> List[Project]:
        """List all projects for the group, including subgroups and archived."""
        grp = self._gl.groups.get(group_id)
        projects: Dict[int, Project] = {}

        def collect(archived: bool) -> None:
            items: Iterable = grp.projects.list(
                include_subgroups=True,
                with_shared=False,
                simple=True,
                archived=archived,
                all=True,
                per_page=100,
            )
            for it in items:
                proj = Project(
                    id=int(it.id),
                    path_with_namespace=str(it.path_with_namespace),
                    http_url_to_repo=str(it.http_url_to_repo),
                    archived=archived,
                )
                projects[proj.id] = proj

        collect(False)
        collect(True)
        return sorted(projects.values(), key=lambda p: p.path_with_namespace)
