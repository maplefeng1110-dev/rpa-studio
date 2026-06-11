"""
日志模块
配置统一的日志管理，输出到控制台和文件
"""
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "RPA",
    log_dir: Optional[str] = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG
) -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        log_dir: 日志文件目录路径，默认为 rpa_core/logs
        console_level: 控制台日志级别
        file_level: 文件日志级别
    
    Returns:
        配置好的 Logger 实例
    """
    # 获取或创建 logger
    logger = logging.getLogger(name)
    
    # 如果已经配置过，直接返回
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # 确定日志目录
    if log_dir is None:
        log_dir = Path(__file__).parent.parent / "logs"
    else:
        log_dir = Path(log_dir)
    
    # 确保日志目录存在
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成日志文件名（按日期）
    log_filename = datetime.now().strftime("rpa_%Y%m%d.log")
    log_file = log_dir / log_filename
    
    # 日志格式
    detailed_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    simple_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(simple_format)
    logger.addHandler(console_handler)
    
    # 文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(file_level)
    file_handler.setFormatter(detailed_format)
    logger.addHandler(file_handler)
    
    logger.info(f"日志文件: {log_file}")
    
    return logger


def get_logger(name: str = "RPA") -> logging.Logger:
    """
    获取已配置的日志记录器
    
    Args:
        name: 日志记录器名称
    
    Returns:
        Logger 实例
    """
    return logging.getLogger(name)
