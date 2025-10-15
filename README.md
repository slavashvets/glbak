# glbak

Simple CLI tool to backup all repositories (all refs) from a GitLab group (including all subgroups)
into local mirror repositories for archival purposes. Requires `git`.

## Quick start

```bash
uv tool install .
glbak --help
```

Set `GITLAB_TOKEN` to a Personal Access Token with scopes `read_api` and `read_repository`.

```bash
export GITLAB_TOKEN=glpat_xxx
export GLBAK_BASE_URL=https://gitlab.mycompany.com

glbak my-root/group/path
```

Dry run:

```bash
glbak my-root/group/path --dry-run
```
