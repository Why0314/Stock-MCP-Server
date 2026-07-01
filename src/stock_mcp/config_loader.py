from __future__ import annotations

from pathlib import Path

import yaml


def load_named_records(path: Path, root_key: str) -> list[dict]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as file_obj:
        payload = yaml.safe_load(file_obj) or {}

    records = payload.get(root_key, [])
    if records is None:
        return []
    if not isinstance(records, list):
        raise ValueError(f"Config key '{root_key}' must be a list: {path}")
    return [item for item in records if isinstance(item, dict)]
