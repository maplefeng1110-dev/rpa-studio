"""
Open Step 模块
负责打开指定 URL
"""
from typing import Any, Dict
from urllib.parse import urlparse

from .base import BaseStep, StepResult, StepError
from ..browser import BrowserAdapter
from ..utils import RuntimeContext

# 仅允许的 URL 协议，阻止 file:// / javascript: / data: 等本地读写或注入向量
ALLOWED_SCHEMES = {"http", "https", ""}


class OpenStep(BaseStep):
    """
    打开页面 Step
    - 使用 value 字段指定 URL
    """
    
    step_type = "open"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.url = config.get("value") or config.get("url")
    
    def execute(self, browser: BrowserAdapter, context: RuntimeContext) -> StepResult:
        """
        执行打开页面操作
        
        Args:
            browser: 浏览器适配器
            context: 运行时上下文
        
        Returns:
            StepResult: 执行结果
        """
        url = self._render_value(self.url, context)

        if not url:
            raise StepError(self.step_type, "URL 不能为空")

        # 协议白名单校验，阻止 file:// 等危险协议
        scheme = urlparse(str(url)).scheme.lower()
        if scheme not in ALLOWED_SCHEMES:
            raise StepError(self.step_type, f"不允许的 URL 协议 '{scheme}': {url}")

        try:
            browser.open(url, timeout=self.timeout)
            return StepResult(
                success=True,
                message=f"成功打开页面: {url}"
            )
        except Exception as e:
            raise StepError(self.step_type, f"打开页面失败: {url}, 错误: {str(e)}")
