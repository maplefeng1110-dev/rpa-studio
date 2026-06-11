"""
Input Step 模块
负责在指定元素中输入文本
"""
from typing import Any, Dict

from .base import BaseStep, StepResult, StepError
from ..browser import BrowserAdapter, ElementNotFoundError
from ..utils import RuntimeContext


class InputStep(BaseStep):
    """
    输入文本 Step
    - 使用 selector 字段指定目标元素
    - 使用 value 字段指定输入内容
    """
    
    step_type = "input"
    
    def execute(self, browser: BrowserAdapter, context: RuntimeContext) -> StepResult:
        """
        执行输入操作
        
        Args:
            browser: 浏览器适配器
            context: 运行时上下文
        
        Returns:
            StepResult: 执行结果
        """
        candidates = self._candidate_selectors(context)
        value = self._render_value(self.value, context)

        if not candidates:
            raise StepError(self.step_type, "selector 不能为空")

        if value is None:
            value = ""

        try:
            used = browser.input(candidates, value, timeout=self.timeout, frame=self.frame, intent=self.description)
            return StepResult(
                success=True,
                message=f"成功输入文本到: {used}"
            )
        except ElementNotFoundError as e:
            raise StepError(self.step_type, str(e))
        except Exception as e:
            raise StepError(self.step_type, f"输入失败: {candidates}, 错误: {str(e)}")
