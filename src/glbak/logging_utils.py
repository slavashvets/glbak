from __future__ import annotations

import sys
from loguru import logger


def setup_logging(verbose: bool = False) -> None:
    """Configure loguru logger."""
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(sys.stderr, level=level, format="{time:HH:mm:ss} | {level: <8} | {message}")
