"""
AI 视觉兜底定位 / 选择器修复
当 DOM 候选选择器全部失效时，把页面截图 + 精简 DOM + 失败的选择器交给多模态 LLM，
让它返回一个「修好的选择器」或「点击坐标」。这是选择器自愈的终局，也是纯 DOM
工具难以企及的健壮性来源（对标艺赛旗的 CV 拾取，但更轻、可自带模型与 key）。

默认走官方 anthropic SDK + Claude（claude-opus-4-8，多模态 + 结构化输出）。
- 模型：环境变量 RPA_LLM_MODEL，默认 claude-opus-4-8
- 开关：环境变量 RPA_AI_FALLBACK（1/true/on 开启）
- 凭据：anthropic SDK 自行从 ANTHROPIC_API_KEY 解析；ANTHROPIC_BASE_URL 可指向代理/自托管
"""
import base64
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AILocator")

# 强制 LLM 返回的结构化结果：要么给选择器、要么给坐标、要么放弃
_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "strategy": {"type": "string", "enum": ["selector", "coordinates", "none"]},
        "selector": {"type": ["string", "null"]},
        "x": {"type": ["integer", "null"]},
        "y": {"type": ["integer", "null"]},
        "reason": {"type": "string"},
    },
    "required": ["strategy", "selector", "x", "y", "reason"],
    "additionalProperties": False,
}

_SYSTEM = (
    "你是网页自动化的元素定位专家。给定页面截图、精简后的 DOM 以及一组已失效的选择器，"
    "你的任务是定位用户想操作的目标元素。优先返回一个在当前页面唯一、稳定的选择器"
    "（CSS 用 css: 前缀，XPath 用 xpath: 前缀，文本用 text: 前缀）；"
    "若 DOM 中无法可靠定位（如 canvas / 富文本 / 图形界面），再返回截图中的点击坐标"
    "（x,y 为相对截图左上角的像素，取元素中心点）。两者都不可行时 strategy 返回 none。"
)


class AILocator:
    """多模态 LLM 兜底定位器。未开启或缺少依赖/凭据时静默不可用。"""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None,
                 enabled: Optional[bool] = None):
        self.model = model or os.environ.get("RPA_LLM_MODEL", "claude-opus-4-8")
        if enabled is None:
            enabled = os.environ.get("RPA_AI_FALLBACK", "").strip().lower() in ("1", "true", "yes", "on")
        self._enabled = enabled
        self._api_key = api_key
        self._client = None
        self._init_error: Optional[str] = None

    @property
    def available(self) -> bool:
        return self._enabled and self._ensure_client() is not None

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except Exception as e:  # 未安装
            self._init_error = f"anthropic SDK 未安装: {e}"
            return None
        try:
            self._client = anthropic.Anthropic(api_key=self._api_key) if self._api_key else anthropic.Anthropic()
        except Exception as e:  # 缺少 API key 等
            self._init_error = str(e)
            return None
        return self._client

    def _build_prompt(self, intent: Optional[str], failed_selectors: List[str],
                      html: Optional[str], viewport: Optional[Dict[str, int]]) -> str:
        parts = ["DOM 候选选择器已全部失效，请定位目标元素。"]
        if intent:
            parts.append(f"目标元素描述：{intent}")
        if failed_selectors:
            parts.append("已失效的选择器（可作为目标线索）：" + ", ".join(failed_selectors))
        if viewport:
            parts.append(f"截图尺寸：{viewport.get('width')}x{viewport.get('height')} 像素")
        if html:
            snippet = html if len(html) <= 12000 else html[:12000] + " …(已截断)"
            parts.append("精简 DOM：\n" + snippet)
        return "\n\n".join(parts)

    def locate(
        self,
        intent: Optional[str] = None,
        failed_selectors: Optional[List[str]] = None,
        html: Optional[str] = None,
        screenshot_png: Optional[bytes] = None,
        viewport: Optional[Dict[str, int]] = None,
        allow_coordinates: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        返回 {"strategy": "selector", "selector": ...} 或
            {"strategy": "coordinates", "x": ..., "y": ...}，无法定位返回 None。
        """
        client = self._ensure_client()
        if client is None:
            return None

        content: List[Dict[str, Any]] = []
        if screenshot_png:
            b64 = base64.standard_b64encode(screenshot_png).decode("utf-8")
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": b64},
            })
        content.append({"type": "text", "text": self._build_prompt(intent, failed_selectors or [], html, viewport)})

        try:
            resp = client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=_SYSTEM,
                messages=[{"role": "user", "content": content}],
                output_config={"format": {"type": "json_schema", "schema": _RESULT_SCHEMA}},
            )
            text = next((b.text for b in resp.content if b.type == "text"), None)
            if not text:
                return None
            data = json.loads(text)
        except Exception as e:
            logger.warning(f"AI 定位调用失败: {e}")
            return None

        strategy = data.get("strategy")
        if strategy == "selector" and data.get("selector"):
            return {"strategy": "selector", "selector": str(data["selector"]), "reason": data.get("reason", "")}
        if strategy == "coordinates" and allow_coordinates and data.get("x") is not None and data.get("y") is not None:
            return {"strategy": "coordinates", "x": int(data["x"]), "y": int(data["y"]), "reason": data.get("reason", "")}
        return None
