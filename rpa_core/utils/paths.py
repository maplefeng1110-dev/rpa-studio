"""
路径安全模块
约束流程定义里的文件写入路径，防止 ../ 穿越或绝对路径写穿磁盘。
所有 extract 等步骤的落盘路径都必须经过 safe_output_path 解析。
"""
import os
from pathlib import Path


def get_output_base() -> Path:
    """
    返回允许写入的输出根目录。
    可通过环境变量 RPA_OUTPUT_DIR 覆盖，默认 <rpa_core>/output。
    """
    env = os.environ.get("RPA_OUTPUT_DIR")
    if env:
        base = Path(env)
    else:
        # paths.py 位于 rpa_core/utils/，根目录回退一级到 rpa_core/
        base = Path(__file__).resolve().parents[1] / "output"
    base.mkdir(parents=True, exist_ok=True)
    return base.resolve()


def safe_output_path(save_path: str) -> Path:
    """
    将流程提供的 save_path 解析为一个被限制在输出根目录内的安全路径。

    - 相对路径：拼到输出根目录下。
    - 绝对路径：剥离根，按相对路径处理（不允许任意绝对位置）。
    - 解析后若仍逃逸出输出根目录（如通过 ../ 软链），抛出 ValueError。

    Args:
        save_path: 流程定义中给出的保存路径

    Returns:
        位于输出根目录内的安全 Path

    Raises:
        ValueError: 路径非法或逃逸出沙箱
    """
    if not save_path or not isinstance(save_path, str):
        raise ValueError("save_path 不能为空")

    base = get_output_base()

    candidate = Path(save_path)
    # 绝对路径降级为相对：去掉锚点（盘符 / 根斜杠）
    if candidate.is_absolute():
        candidate = Path(*candidate.parts[1:]) if len(candidate.parts) > 1 else Path()

    resolved = (base / candidate).resolve()

    # 校验解析后的真实路径仍在沙箱根目录内
    try:
        resolved.relative_to(base)
    except ValueError:
        raise ValueError(f"非法的输出路径（逃逸出沙箱）: {save_path}")

    return resolved
