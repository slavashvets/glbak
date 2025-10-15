from __future__ import annotations

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration read from env (.env)."""

    base_url: str = Field(default="https://gitlab.com", description="GitLab base URL")
    dest_dir: Path = Field(default=Path("./backups"), description="Destination directory for mirrors")
    concurrency: int = Field(default=8, description="Max parallel clones")
    timeout: float = Field(default=30.0, description="HTTP timeout seconds")
    verify_ssl: bool = Field(default=True, description="Verify TLS certificates")

    model_config = SettingsConfigDict(
        env_prefix="GLBAK_",
        env_file=".env",
        extra="ignore",
    )
