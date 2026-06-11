"""
RPA Core 示例入口
演示如何加载和执行 Flow
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径（rpa_core 的父目录）
sys.path.insert(0, str(Path(__file__).parent.parent))

from rpa_core import FlowEngine


def main():
    """
    主函数：加载并执行示例 Flow
    """
    # 示例 Flow 文件路径 - 使用绝对路径
    flow_path = Path(__file__).parent / "flows" / "baidu_search_extract.json"
    
    # 输出文件路径
    output_file = Path(__file__).parent / "output" / "search_results.txt"
    
    # 初始上下文变量
    initial_context = {
        "search_keyword": "DrissionPage 自动化",
        "output_file": str(output_file)
    }
    
    print("=" * 50)
    print("RPA Core - 最小可运行内核示例")
    print("=" * 50)
    print(f"\n加载 Flow: {flow_path}")
    print(f"初始变量: {initial_context}")
    print()
    
    # 使用 with 语句自动管理浏览器生命周期
    with FlowEngine() as engine:
        # 加载 Flow 定义
        flow = engine.load_flow(str(flow_path))
        print(f"Flow 名称: {flow.get('name')}")
        print(f"步骤数量: {len(flow.get('steps', []))}")
        print()
        
        # 执行 Flow
        print("开始执行...")
        print("-" * 50)
        result = engine.execute(flow, initial_context)
        print("-" * 50)
        
        # 输出结果
        print(f"\n执行结果: {result}")
        print(f"执行步骤: {result.executed_steps}/{result.total_steps}")
        
        if result.error:
            print(f"错误信息: {result.error}")
        
        # 输出执行日志
        print("\n执行日志:")
        for log in result.execution_log:
            status = "✓" if log["success"] else "✗"
            print(f"  [{status}] Step {log['step_index']+1} ({log['step_type']}): {log['message']}")
            print(f"      耗时: {log['duration_ms']:.2f}ms")
    
    print("\n浏览器已关闭")
    print("=" * 50)


if __name__ == "__main__":
    main()
