"""
RPA Core - 最小可运行 RPA 内核
基于 DrissionPage 的 Web 自动化框架
"""
from .engine import FlowEngine, ExecutionResult, FlowLoadError, FlowAbortError
from .browser import BrowserAdapter, ElementNotFoundError, PageLoadTimeoutError
from .steps import BaseStep, StepResult, StepError, OpenStep, ClickStep, InputStep
from .utils import RuntimeContext

__version__ = "0.1.0"

__all__ = [
    # Engine
    "FlowEngine",
    "ExecutionResult",
    "FlowLoadError",
    "FlowAbortError",
    # Browser
    "BrowserAdapter",
    "ElementNotFoundError",
    "PageLoadTimeoutError",
    # Steps
    "BaseStep",
    "StepResult",
    "StepError",
    "OpenStep",
    "ClickStep",
    "InputStep",
    # Utils
    "RuntimeContext",
]
