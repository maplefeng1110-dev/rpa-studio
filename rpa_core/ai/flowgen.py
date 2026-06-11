"""
自然语言 → Flow 生成
把一句话需求交给 Claude，生成可直接执行的 Flow JSON（支持嵌套 if/loop）。
由于结构化输出不支持递归 schema，这里用「提示词约束 + 自带校验」：
模型只返回 JSON，解析后用本模块的校验器把关，非法则回报错误。

默认走官方 anthropic SDK + Claude（claude-opus-4-8）。凭据走 ANTHROPIC_API_KEY。
"""
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("FlowGenerator")

# 引擎支持的 Step 类型（须与 engine.STEP_REGISTRY + 控制流保持一致）
VALID_STEP_TYPES = {
    "open", "click", "input", "wait", "extract",
    "select", "switch_tab", "download", "if", "loop",
}

_SPEC = """\
你是 RPA 流程生成器。把用户的自然语言需求转成一个 Flow JSON 对象，结构为：
{"name": "简短流程名", "steps": [ ...步骤... ]}

可用步骤类型与字段：
- open:   {"type":"open","value":"https://..."}              打开网址
- click:  {"type":"click","selector":"#id 或 css:.x 或 text:登录","description":"目标的自然语言描述"}
- input:  {"type":"input","selector":"...","value":"要输入的文本"}
- wait:   {"type":"wait","value":"3"}                         等待秒数
- extract:{"type":"extract","selector":"...","context_key":"变量名","save_path":"output/x.txt"}
- select: {"type":"select","selector":"...","by":"text|value|index","value":"选项"}
- switch_tab:{"type":"switch_tab","value":"latest"} 或 {"type":"switch_tab","new_tab":true,"url":"..."}
- download:{"type":"download","selector":"下载按钮选择器","save_path":"downloads"}
- if:     {"type":"if","condition":"{{var}} == 'ok'","then":[...],"else":[...]}
- loop:   {"type":"loop","loop_type":"count|each","value":"5 或 {{列表变量}}","steps":[...]}

约定：
- 选择器无前缀默认按 CSS 解析；也可用 xpath: / text: 前缀。不确定时给一个合理的 CSS 猜测，
  并在 click/input/extract 上加 "description" 字段（自然语言描述目标），便于运行时 AI 兜底定位。
- 用 {{变量名}} 引用上下文变量；用 {{secret:名称}} 引用加密凭据（如密码）。
- 任意步骤可加 "on_fail":"abort|skip|retry"。
- 只输出 JSON 对象本身，不要任何解释文字、不要 markdown 代码块。"""


def _strip_fences(text: str) -> str:
    """去掉可能的 ```json ... ``` 代码块包裹。"""
    t = text.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", t, re.DOTALL)
    return m.group(1).strip() if m else t


def validate_flow_dict(flow: Any) -> List[str]:
    """校验生成的 Flow 结构；返回错误列表（空表示合法）。递归校验 if/loop 子步骤。"""
    errors: List[str] = []
    if not isinstance(flow, dict):
        return ["顶层必须是对象"]
    steps = flow.get("steps")
    if not isinstance(steps, list):
        return ["缺少 steps 列表"]

    def check(step_list: List[Any], path: str):
        if not isinstance(step_list, list):
            errors.append(f"{path} 不是步骤列表")
            return
        for i, s in enumerate(step_list):
            p = f"{path}[{i}]"
            if not isinstance(s, dict):
                errors.append(f"{p} 不是对象")
                continue
            t = s.get("type")
            if t not in VALID_STEP_TYPES:
                errors.append(f"{p} 未知类型: {t}")
                continue
            if t == "open" and not s.get("value"):
                errors.append(f"{p} (open) 缺少 value")
            if t in ("click", "input", "extract", "select", "download") and not (s.get("selector") or s.get("selectors")):
                errors.append(f"{p} ({t}) 缺少 selector")
            if t == "input" and s.get("value") is None:
                errors.append(f"{p} (input) 缺少 value")
            if t == "if":
                check(s.get("then", []), f"{p}.then")
                check(s.get("else", []), f"{p}.else")
            if t == "loop":
                check(s.get("steps", []), f"{p}.steps")

    check(steps, "steps")
    return errors


class FlowGenerator:
    """自然语言 → Flow 生成器。缺少 anthropic 依赖或 API key 时不可用。"""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or os.environ.get("RPA_LLM_MODEL", "claude-opus-4-8")
        self._api_key = api_key
        self._client = None
        self._init_error: Optional[str] = None

    @property
    def available(self) -> bool:
        return self._ensure_client() is not None

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except Exception as e:
            self._init_error = f"anthropic SDK 未安装: {e}"
            return None
        try:
            self._client = anthropic.Anthropic(api_key=self._api_key) if self._api_key else anthropic.Anthropic()
        except Exception as e:
            self._init_error = str(e)
            return None
        return self._client

    def generate(self, instruction: str, url_hint: Optional[str] = None) -> Dict[str, Any]:
        """
        返回 {"success": bool, "flow": {...}|None, "errors": [...], "error": str|None}
        """
        client = self._ensure_client()
        if client is None:
            return {"success": False, "flow": None, "errors": [], "error": self._init_error or "AI 不可用"}

        user_text = instruction.strip()
        if url_hint:
            user_text += f"\n\n（起始网址提示：{url_hint}）"

        try:
            resp = client.messages.create(
                model=self.model,
                max_tokens=4096,
                thinking={"type": "adaptive"},
                system=_SPEC,
                messages=[{"role": "user", "content": user_text}],
            )
            text = next((b.text for b in resp.content if b.type == "text"), None)
            if not text:
                return {"success": False, "flow": None, "errors": [], "error": "模型未返回文本"}
            flow = json.loads(_strip_fences(text))
        except json.JSONDecodeError as e:
            return {"success": False, "flow": None, "errors": [], "error": f"返回的不是合法 JSON: {e}"}
        except Exception as e:
            logger.warning(f"Flow 生成调用失败: {e}")
            return {"success": False, "flow": None, "errors": [], "error": str(e)}

        errors = validate_flow_dict(flow)
        if errors:
            return {"success": False, "flow": flow, "errors": errors, "error": "生成的流程未通过校验"}
        flow.setdefault("name", "AI 生成的流程")
        return {"success": True, "flow": flow, "errors": [], "error": None}
