"""Load externalized YAML prompt templates."""

from functools import lru_cache
from pathlib import Path

import yaml


def _prompts_dir() -> Path:
    return Path(__file__).resolve().parent / "prompts"


@lru_cache
def load_prompt(name: str) -> dict[str, str]:
    """Load a prompt file `name.yaml` with string fields system/user or single body."""
    path = _prompts_dir() / f"{name}.yaml"
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid prompt format: {path}")
    return {str(k): str(v) for k, v in data.items()}
