"""
浏览器池
管理一组 BrowserAdapter，支持多个流程并发执行（解除单浏览器串行限制）。
浏览器实例懒创建（开销大），acquire/release 借还，close_all 统一回收。
线程安全。
"""
import queue
import threading
from typing import Callable, List, Optional


class BrowserPool:
    def __init__(self, size: int, factory: Callable[[], object]):
        """
        Args:
            size: 池容量（可并发的浏览器数）
            factory: 无参工厂，返回一个 BrowserAdapter（通常 headless）
        """
        if size < 1:
            raise ValueError("浏览器池容量必须 >= 1")
        self.size = size
        self.factory = factory
        # 用 None 占位表示「尚未创建的空槽」，借出时才真正创建
        self._slots: "queue.Queue" = queue.Queue()
        for _ in range(size):
            self._slots.put(None)
        self._created: List[object] = []
        self._lock = threading.Lock()

    def acquire(self, block: bool = True, timeout: Optional[float] = None):
        """借一个浏览器。池满且 block=False 时返回 None。"""
        try:
            slot = self._slots.get(block=block, timeout=timeout)
        except queue.Empty:
            return None
        if slot is None:  # 懒创建
            slot = self.factory()
            with self._lock:
                self._created.append(slot)
        return slot

    def release(self, adapter) -> None:
        """归还一个浏览器到池中。"""
        self._slots.put(adapter)

    def close_all(self) -> None:
        """关闭所有已创建的浏览器。"""
        with self._lock:
            for a in self._created:
                try:
                    a.close()
                except Exception:
                    pass
            self._created.clear()
