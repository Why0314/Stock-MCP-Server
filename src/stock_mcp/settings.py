from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _parse_dotenv(dotenv_path: Path) -> dict[str, str]:
    if not dotenv_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def _resolve_optional_path(raw_value: str | None) -> Path | None:
    if not raw_value:
        return None
    return Path(raw_value).expanduser()


@dataclass(frozen=True)
class Settings:
    env: str = "dev"
    history_data_dir: Path | None = None
    fin_data_dir: Path | None = None
    config_dir: Path = Path("config")

    def __post_init__(self) -> None:
        if self.history_data_dir is not None and not isinstance(self.history_data_dir, Path):
            object.__setattr__(self, "history_data_dir", Path(self.history_data_dir).expanduser())
        if self.fin_data_dir is not None and not isinstance(self.fin_data_dir, Path):
            object.__setattr__(self, "fin_data_dir", Path(self.fin_data_dir).expanduser())
        if not isinstance(self.config_dir, Path):
            object.__setattr__(self, "config_dir", Path(self.config_dir).expanduser())

    def require_history_data_dir(self) -> Path:
        if self.history_data_dir is None:
            raise ValueError("STOCK_HISTORY_DATA_DIR is not configured.")
        return self.history_data_dir

    def require_fin_data_dir(self) -> Path:
        if self.fin_data_dir is None:
            raise ValueError("STOCK_FIN_DATA_DIR is not configured.")
        return self.fin_data_dir


def load_settings(dotenv_path: str | Path = ".env") -> Settings:
    dotenv_values = _parse_dotenv(Path(dotenv_path))

    def get_value(key: str) -> str | None:
        return os.environ.get(key, dotenv_values.get(key))

    return Settings(
        env=get_value("STOCK_ENV") or "dev",
        history_data_dir=_resolve_optional_path(get_value("STOCK_HISTORY_DATA_DIR")),
        fin_data_dir=_resolve_optional_path(get_value("STOCK_FIN_DATA_DIR")),
        config_dir=_resolve_optional_path(get_value("STOCK_CONFIG_DIR")) or Path("config"),
    )
