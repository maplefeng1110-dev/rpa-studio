"""
Runtime Context 模块
负责存储流程运行期间的共享状态，包括变量传递、Step执行结果等
"""
import re
from typing import Any, Dict, Optional


class RuntimeContext:
    """
    运行时上下文容器
    - 存储变量和运行状态
    - 支持模板变量渲染 {{variable_name}}
    """
    
    def __init__(self, initial_data: Optional[Dict[str, Any]] = None):
        self._data: Dict[str, Any] = initial_data.copy() if initial_data else {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取变量值"""
        return self._data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """设置变量值"""
        self._data[key] = value
    
    def update(self, data: Dict[str, Any]) -> None:
        """批量更新变量"""
        self._data.update(data)
    
    def render(self, template: Any) -> Any:
        """
        渲染模板字符串，将 {{variable_name}} 替换为实际值。
        如果模板字符串恰好是单个 "{{variable_name}}"，则保留原始类型（如列表、字典、整型等）。
        如果包含多个模板或有其他混合文本，则替换为字符串合并结果。
        """
        if not template or not isinstance(template, str):
            return template
        
        # 检查是否为单一变量精确匹配
        exact_pattern = r'^\{\{(\w+)\}\}$'
        exact_match = re.match(exact_pattern, template)
        if exact_match:
            key = exact_match.group(1)
            if key in self._data:
                return self._data[key]
            return template
        
        # 否则作为普通字符串替换
        pattern = r'\{\{(\w+)\}\}'
        
        def replace(match):
            key = match.group(1)
            value = self._data.get(key, match.group(0))
            return str(value) if value is not None else match.group(0)
        
        return re.sub(pattern, replace, template)
    
    def to_dict(self) -> Dict[str, Any]:
        """返回上下文数据的副本"""
        return self._data.copy()
    
    def __repr__(self) -> str:
        return f"RuntimeContext({self._data})"
