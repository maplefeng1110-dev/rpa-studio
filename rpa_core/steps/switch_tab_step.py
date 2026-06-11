"""
Switch Tab Step 模块
切换当前操作的标签页，或打开新标签页。
"""
from typing import Any, Dict

from .base import BaseStep, StepResult, StepError
from ..browser import BrowserAdapter, ElementNotFoundError, PageLoadTimeoutError
from ..utils import RuntimeContext


class SwitchTabStep(BaseStep):
    """
    标签页切换 Step
    - value: 'latest'（最新标签页）或整数下标（从 0 开始）
    - new_tab: 为 true 时打开新标签页（可选配 url）
    - url: new_tab 时要打开的地址
    """

    step_type = "switch_tab"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.new_tab = config.get("new_tab", False)
        self.url = config.get("url")

    def execute(self, browser: BrowserAdapter, context: RuntimeContext) -> StepResult:
        try:
            if self.new_tab:
                url = self._render_value(self.url, context)
                browser.new_tab(url)
                return StepResult(success=True, message=f"已打开新标签页: {url or '空白页'}")

            target = self._render_value(self.value, context)
            if target is None or target == "":
                target = "latest"
            browser.switch_tab(target)
            return StepResult(success=True, message=f"已切换到标签页: {target}")
        except (ElementNotFoundError, PageLoadTimeoutError) as e:
            raise StepError(self.step_type, str(e))
        except Exception as e:
            raise StepError(self.step_type, f"标签页操作失败, 错误: {str(e)}")
