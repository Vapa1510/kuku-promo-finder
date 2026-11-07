"""
Storage and Caching Module
==========================
Provides persistent hash-based response caching and run checkpointing.
Enables fast resumption of pipeline executions without redundant LLM calls.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any


class CacheManager:
    """Manages disk-based JSON caching for candidate evaluations and judge runs."""

    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.eval_cache_file = self.cache_dir / "evaluation_cache.json"
        self._cache: Dict[str, Any] = self._load_cache()

    def _load_cache(self) -> Dict[str, Any]:
        if self.eval_cache_file.exists():
            try:
                with open(self.eval_cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self) -> None:
        try:
            with open(self.eval_cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
        except Exception:
            pass

    @staticmethod
    def generate_key(candidate_id: str, text: str, model_name: str, prompt_version: str = "v1") -> str:
        """Create deterministic SHA256 key from content and model metadata."""
        content = f"{candidate_id}::{model_name}::{prompt_version}::{text}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self._cache.get(key)

    def set(self, key: str, value: Dict[str, Any]) -> None:
        self._cache[key] = value
        self._save_cache()

    def save_checkpoint(self, checkpoint_path: str, data: Dict[str, Any]) -> None:
        """Save pipeline intermediate checkpoint."""
        p = Path(checkpoint_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_checkpoint(self, checkpoint_path: str) -> Optional[Dict[str, Any]]:
        """Load pipeline intermediate checkpoint if it exists."""
        p = Path(checkpoint_path)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None


def compute_input_fingerprint(input_folder: str, config_dict: Dict[str, Any]) -> str:
    """
    Compute deterministic SHA256 fingerprint for screenplay inputs and config settings.
    Ensures stale checkpoints are not reused when inputs or configs change.
    """
    p = Path(input_folder)
    file_signatures = []
    if p.is_dir():
        for f in sorted(p.glob("*.txt")):
            stat = f.stat()
            file_signatures.append(f"{f.name}:{stat.st_size}")
    elif p.is_file():
        stat = p.stat()
        file_signatures.append(f"{p.name}:{stat.st_size}")

    keys_to_hash = ["min_duration", "max_duration", "iou_threshold", "candidates_per_episode", "enable_llm"]
    cfg_sig = {k: config_dict.get(k) for k in keys_to_hash if k in config_dict}

    content = f"FILES:{'|'.join(file_signatures)}::CONFIG:{json.dumps(cfg_sig, sort_keys=True)}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

