"""
调度引擎
- 定时触发（cron / interval）定时任务
- 通过任务队列 + 单 worker 串行执行（与手动执行共用同一把浏览器执行锁）
- 执行逻辑通过注入的 run_callback 解耦，便于测试

线程模型：
  dispatcher 线程：周期性 poll，把到点的任务入队
  worker 线程：从队列取任务，调用 run_callback 串行执行
测试可不启动线程，直接调用 poll() + process_queue()。
"""
import logging
import queue
import threading
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

from . import cron
from .store import ScheduleStore

logger = logging.getLogger("Scheduler")

# run_callback(flow: dict, initial_context: dict) -> Any
RunCallback = Callable[[Dict[str, Any], Dict[str, Any]], Any]


class Scheduler:
    def __init__(
        self,
        run_callback: RunCallback,
        store: Optional[ScheduleStore] = None,
        tick_seconds: float = 5.0,
        now_fn: Callable[[], datetime] = datetime.now,
    ):
        self.run_callback = run_callback
        self.store = store or ScheduleStore()
        self.tick_seconds = tick_seconds
        self._now = now_fn
        self._queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._running = False
        self._dispatcher: Optional[threading.Thread] = None
        self._worker: Optional[threading.Thread] = None

    # ---- 调度计算 ----
    def compute_next_run(self, job: Dict[str, Any], from_dt: datetime) -> datetime:
        stype = job.get("schedule_type")
        sval = job.get("schedule_value")
        if stype == "cron":
            return cron.next_run(str(sval), from_dt)
        if stype == "interval":
            seconds = int(sval)
            if seconds <= 0:
                raise ValueError("interval 秒数必须为正")
            return from_dt + timedelta(seconds=seconds)
        raise ValueError(f"未知的调度类型: {stype}")

    # ---- 轮询：把到点任务入队 ----
    def poll(self, now: Optional[datetime] = None) -> int:
        now = now or self._now()
        enqueued = 0
        for job in self.store.list():
            if not job.get("enabled"):
                continue
            next_run_s = job.get("next_run")
            if not next_run_s:
                # 首次：从现在起算下一次触发，不立即执行
                nxt = self.compute_next_run(job, now)
                self.store.update_fields(job["id"], next_run=nxt.isoformat())
                continue
            try:
                next_run_dt = datetime.fromisoformat(next_run_s)
            except ValueError:
                next_run_dt = self.compute_next_run(job, now)
            if now >= next_run_dt:
                self._queue.put(job)
                enqueued += 1
                # 立即推进 next_run，避免重复入队
                nxt = self.compute_next_run(job, now)
                self.store.update_fields(job["id"], next_run=nxt.isoformat())
        return enqueued

    # ---- 执行单个任务 ----
    def _execute(self, job: Dict[str, Any]) -> None:
        job_id = job.get("id")
        started = self._now().isoformat()
        try:
            logger.info(f"调度执行任务: {job.get('name')} ({job_id})")
            self.run_callback(job.get("flow") or {}, job.get("initial_context") or {})
            self.store.update_fields(job_id, last_run=started, last_status="success")
        except Exception as e:
            logger.error(f"调度任务执行失败 {job_id}: {e}")
            self.store.update_fields(job_id, last_run=started, last_status=f"error: {e}")

    def process_queue(self) -> int:
        """同步排空队列（测试或单步驱动用）。返回执行的任务数。"""
        count = 0
        while True:
            try:
                job = self._queue.get_nowait()
            except queue.Empty:
                break
            self._execute(job)
            count += 1
        return count

    def run_now(self, job_id: str) -> bool:
        job = self.store.get(job_id)
        if not job:
            return False
        self._queue.put(job)
        return True

    # ---- 线程生命周期 ----
    def _dispatch_loop(self) -> None:
        while self._running:
            try:
                self.poll()
            except Exception as e:
                logger.error(f"调度轮询异常: {e}")
            # 可被 stop 提前唤醒
            self._stop_event.wait(self.tick_seconds)

    def _worker_loop(self) -> None:
        while self._running:
            try:
                job = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            self._execute(job)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event = threading.Event()
        self._dispatcher = threading.Thread(target=self._dispatch_loop, daemon=True, name="sched-dispatch")
        self._worker = threading.Thread(target=self._worker_loop, daemon=True, name="sched-worker")
        self._dispatcher.start()
        self._worker.start()
        logger.info("调度引擎已启动")

    def stop(self) -> None:
        self._running = False
        if getattr(self, "_stop_event", None):
            self._stop_event.set()
        logger.info("调度引擎已停止")
