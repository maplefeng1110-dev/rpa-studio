"""
Wait Step 模块
负责等待指定时间
"""
from typing import Any, Dict

from .base import BaseStep, StepResult
from ..browser import BrowserAdapter
from ..utils import RuntimeContext


class WaitStep(BaseStep):
    """
    等待 Step
    - 使用 value 字段指定等待秒数
    """
    
    step_type = "wait"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.seconds = float(config.get("value", 1))
    
    def execute(self, browser: BrowserAdapter, context: RuntimeContext) -> StepResult:
        """
        执行等待操作
        
        Args:
            browser: 浏览器适配器
            context: 运行时上下文
        
        Returns:
            StepResult: 执行结果
        """
        browser.wait(self.seconds)
        return StepResult(
            success=True,
            message=f"等待 {self.seconds} 秒完成"
        )
