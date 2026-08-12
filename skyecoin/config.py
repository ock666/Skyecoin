import json
import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Config:
    host: str = "0.0.0.0"
    port: int = 5000
    difficulty: int = 4
    target_block_time: int = 60
    difficulty_adjust_interval: int = 10
    coinbase_reward: float = 50.0
    fee_per_kb: float = 0.25
    max_peers: int = 50
    bootstrap_nodes: list[str] = field(default_factory=list)
    data_dir: str = "data"
    db_name: str = "skyecoin.db"

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Config":
        cfg = cls()

        env_map = {
            "SKYECOIN_HOST": "host",
            "SKYECOIN_PORT": ("port", int),
            "SKYECOIN_DIFFICULTY": ("difficulty", int),
            "SKYECOIN_TARGET_BLOCK_TIME": ("target_block_time", int),
            "SKYECOIN_DIFFICULTY_ADJUST_INTERVAL": ("difficulty_adjust_interval", int),
            "SKYECOIN_COINBASE_REWARD": ("coinbase_reward", float),
            "SKYECOIN_FEE_PER_KB": ("fee_per_kb", float),
            "SKYECOIN_MAX_PEERS": ("max_peers", int),
            "SKYECOIN_DATA_DIR": "data_dir",
            "SKYECOIN_DB_NAME": "db_name",
        }
        for env_var, attr in env_map.items():
            val = os.environ.get(env_var)
            if val is not None:
                if isinstance(attr, tuple):
                    setattr(cfg, attr[0], attr[1](val))
                else:
                    setattr(cfg, attr, val)

        if path is None:
            path = str(Path(cfg.data_dir) / "config.json")

        p = Path(path)
        if p.exists():
            with open(p) as f:
                data = json.load(f)
            for key, value in data.items():
                if hasattr(cfg, key):
                    setattr(cfg, key, value)

        return cfg

    def save(self, path: Optional[str] = None):
        if path is None:
            path = str(Path(self.data_dir) / "config.json")
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            k: v
            for k, v in self.__dict__.items()
            if not k.startswith("_")
        }
        with open(p, "w") as f:
            json.dump(data, f, indent=2)

    @property
    def db_path(self) -> str:
        return str(Path(self.data_dir) / self.db_name)


def setup_logging(level: int = logging.INFO):
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
