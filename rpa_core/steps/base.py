"""
Step 基类模块
定义所有 Step 的抽象接口
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from ..browser import BrowserAdapter
from ..utils import RuntimeContext


class StepResult:
    """
    Step 执行结果
    """
    
    def __init__(self, success: bool, message: str = "", data: Optional[Dict[str, Any]] = None):
        self.success = success
        self.message = message
        self.data = data or {}
    
    def __repr__(self) -> str:
        return f"StepResult(success={self.success}, message='{self.message}')"


class BaseStep(ABC):
    """
    Step 抽象基类
    - 所有具体 Step 必须继承此类
    - 实现 execute 方法
    """
    
    # Step 类型名称，子类必须定义
    step_type: str = ""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化 Step
        
        Args:
            config: Step 配置字典，包含 selector, value, timeout 等
        """
        self.config = config
        self.selector: Optional[str] = config.get("selector")
        self.value: Optional[str] = config.get("value")
        self.timeout: int = config.get("timeout", 10)
        self.on_fail: str = config.get("on_fail", "abort")
    
    @abstractmethod
    def execute(self, browser: BrowserAdapter, context: RuntimeContext) -> StepResult:
        """
        执行 Step
        
        Args:
            browser: 浏览器适配器实例
            context: 运行时上下文
        
        Returns:
            StepResult: 执行结果
        """
        pass
    
    def _render_value(self, value: Optional[str], context: RuntimeContext) -> Optional[str]:
        """渲染模板变量"""
        if value is None:
            return None
        return context.render(value)
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(type={self.step_type}, selector={self.selector})"


class StepError(Exception):
    """Step 执行异常"""
    
    def __init__(self, step_type: str, message: str):
        self.step_type = step_type
        self.message = message
        super().__init__(f"[{step_type}] {message}")
