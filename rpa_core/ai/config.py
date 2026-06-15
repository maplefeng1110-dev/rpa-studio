"""
AI 配置存储（个人版：用户在客户端自配 API）
- api_key：敏感，存进加密保险库（Fernet），绝不明文落盘、绝不回读
- base_url / model / fallback_enabled：非敏感，存 data/ai_config.json
读取时若本地没配，回退到环境变量（方便开发 / 高级用法）。
"""
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from ..storage import get_data_dir

# 存在保险库里的保留名（会在凭据列表中被过滤掉，不展示给用户）
AI_KEY_NAME = "__rpa_ai_key__"
DEFAULT_MODEL = "claude-opus-4-8"


@dataclass
class AIConfig:
    api_key: Optional[str]
    base_url: Optional[str]
    model: str
    fallback_enabled: bool


class AIConfigStore:
    def __init__(self, vault, path=None):
        self._vault = vault
        self._path = Path(path) if path else (get_data_dir() / "ai_config.json")

    def _load(self) -> Dict[str, Any]:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self, data: Dict[str, Any]) -> None:
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_api_key(self) -> Optional[str]:
        try:
            key = self._vault.get(AI_KEY_NAME)
        except Exception:
            key = None
        return key or os.environ.get("ANTHROPIC_API_KEY") or None

    def get(self) -> AIConfig:
        s = self._load()
        env_fallback = os.environ.get("RPA_AI_FALLBACK", "").strip().lower() in ("1", "true", "yes", "on")
        return AIConfig(
            api_key=self.get_api_key(),
            base_url=s.get("base_url") or os.environ.get("ANTHROPIC_BASE_URL") or None,
            model=s.get("model") or os.environ.get("RPA_LLM_MODEL") or DEFAULT_MODEL,
            fallback_enabled=bool(s.get("fallback_enabled", env_fallback)),
        )

    def public(self) -> Dict[str, Any]:
        """返回给前端的配置——绝不含 key，只给一个 has_key 标志。"""
        c = self.get()
        return {
            "has_key": bool(c.api_key),
            "base_url": c.base_url or "",
            "model": c.model,
            "fallback_enabled": c.fallback_enabled,
        }

    def update(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        fallback_enabled: Optional[bool] = None,
        clear_key: bool = False,
    ) -> None:
        s = self._load()
        if base_url is not None:
            s["base_url"] = base_url.strip()
        if model is not None:
            s["model"] = model.strip() or DEFAULT_MODEL
        if fallback_enabled is not None:
            s["fallback_enabled"] = bool(fallback_enabled)
        self._save(s)

        if clear_key:
            self._vault.delete(AI_KEY_NAME)
        elif api_key:
            self._vault.set(AI_KEY_NAME, api_key.strip())
