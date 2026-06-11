"""
Extract Step 模块
负责提取页面文本并保存到文件
"""
from pathlib import Path
from typing import Any, Dict

from .base import BaseStep, StepResult, StepError
from ..browser import BrowserAdapter, ElementNotFoundError
from ..utils import RuntimeContext, safe_output_path


class ExtractStep(BaseStep):
    """
    提取文本 Step
    - 使用 selector 字段指定目标元素
    - 使用 value 字段指定保存路径（可选）
    - 使用 context_key 字段指定存储到 Context 的键名（可选）
    """
    
    step_type = "extract"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.save_path = config.get("save_path")
        self.context_key = config.get("context_key", "extracted_text")
    
    def execute(self, browser: BrowserAdapter, context: RuntimeContext) -> StepResult:
        """
        执行文本提取操作
        
        Args:
            browser: 浏览器适配器
            context: 运行时上下文
        
        Returns:
            StepResult: 执行结果
        """
        selector = self._render_value(self.selector, context)
        save_path = self._render_value(self.save_path, context)
        
        if not selector:
            raise StepError(self.step_type, "selector 不能为空")
        
        try:
            # 提取文本
            text = browser.text(selector, timeout=self.timeout)
            
            # 存储到 Context
            context.set(self.context_key, text)
            
            # 保存到文件（如果指定了路径）
            if save_path:
                try:
                    path = safe_output_path(save_path)
                except ValueError as e:
                    raise StepError(self.step_type, str(e))
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(text)

                return StepResult(
                    success=True,
                    message=f"成功提取文本并保存到: {path}",
                    data={"text_length": len(text), "save_path": str(path)}
                )
            else:
                return StepResult(
                    success=True,
                    message=f"成功提取文本，长度: {len(text)} 字符",
                    data={"text_length": len(text)}
                )
                
        except ElementNotFoundError:
            raise StepError(self.step_type, f"元素未找到: {selector}")
        except Exception as e:
            raise StepError(self.step_type, f"提取失败: {selector}, 错误: {str(e)}")
