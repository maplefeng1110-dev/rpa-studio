"""
Select Step 模块
操作 <select> 下拉框，支持按文本/值/下标选择。
"""
from typing import Any, Dict

from .base import BaseStep, StepResult, StepError
from ..browser import BrowserAdapter, ElementNotFoundError
from ..utils import RuntimeContext


class SelectStep(BaseStep):
    """
    下拉选择 Step
    - selector / selectors: 目标 <select> 元素
    - by: 选择方式 text | value | index（默认 text）
    - value: 对应的选项文本/值/下标
    - frame: 可选 iframe
    """

    step_type = "select"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.by = config.get("by", "text")

    def execute(self, browser: BrowserAdapter, context: RuntimeContext) -> StepResult:
        candidates = self._candidate_selectors(context)
        value = self._render_value(self.value, context)

        if not candidates:
            raise StepError(self.step_type, "selector 不能为空")
        if value is None or value == "":
            raise StepError(self.step_type, "value 不能为空（要选择的选项）")

        try:
            used = browser.select_option(candidates, by=self.by, value=value,
                                         timeout=self.timeout, frame=self.frame)
            return StepResult(
                success=True,
                message=f"成功选择下拉项: {used} by={self.by} value={value}"
            )
        except ElementNotFoundError as e:
            raise StepError(self.step_type, str(e))
        except Exception as e:
            raise StepError(self.step_type, f"下拉选择失败: {candidates}, 错误: {str(e)}")
