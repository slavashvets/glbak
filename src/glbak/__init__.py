from __future__ import annotations

from importlib.metadata import version, PackageNotFoundError

__all__ = ["__version__"]

try:
    __version__ = version("glbak")
except PackageNotFoundError:
    __version__ = "0+local"
