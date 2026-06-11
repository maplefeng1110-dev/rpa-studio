"""
Click Step 模块
负责点击指定元素
"""
from typing import Any, Dict

from .base import BaseStep, StepResult, StepError
from ..browser import BrowserAdapter, ElementNotFoundError
from ..utils import RuntimeContext


class ClickStep(BaseStep):
    """
    点击元素 Step
    - 使用 selector 字段指定目标元素
    """
    
    step_type = "click"
    
    def execute(self, browser: BrowserAdapter, context: RuntimeContext) -> StepResult:
        """
        执行点击操作
        
        Args:
            browser: 浏览器适配器
            context: 运行时上下文
        
        Returns:
            StepResult: 执行结果
        """
        candidates = self._candidate_selectors(context)

        if not candidates:
            raise StepError(self.step_type, "selector 不能为空")

        try:
            used = browser.click(candidates, timeout=self.timeout, frame=self.frame, intent=self.description)
            return StepResult(
                success=True,
                message=f"成功点击元素: {used}"
            )
        except ElementNotFoundError as e:
            raise StepError(self.step_type, str(e))
        except Exception as e:
            raise StepError(self.step_type, f"点击失败: {candidates}, 错误: {str(e)}")
