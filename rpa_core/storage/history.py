"""
运行历史存储模块
用 SQLite（标准库，无新增依赖）持久化每一次 Flow 执行记录，供审计、复盘与调试。
每条记录包含执行结果摘要 + 完整步骤日志（含失败截图路径）。
"""
import json
import os
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_data_dir() -> Path:
    """运行历史等数据的存放目录。可用环境变量 RPA_DATA_DIR 覆盖，默认 <rpa_core>/data。"""
    env = os.environ.get("RPA_DATA_DIR")
    base = Path(env) if env else Path(__file__).resolve().parents[1] / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base


class RunHistory:
    """Flow 运行历史的 SQLite 存储。线程安全（同进程内串行写）。"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or (get_data_dir() / "history.db"))
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock, closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id         TEXT PRIMARY KEY,
                    flow_name      TEXT,
                    success        INTEGER,
                    executed_steps INTEGER,
                    total_steps    INTEGER,
                    error          TEXT,
                    started_at     TEXT,
                    finished_at    TEXT,
                    execution_log  TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at DESC)")

    def record(self, result: Any) -> None:
        """记录一次执行结果（接受 ExecutionResult，duck-typed）。失败不应影响主流程。"""
        with self._lock, closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(run_id, flow_name, success, executed_steps, total_steps, error, started_at, finished_at, execution_log) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    getattr(result, "run_id", None),
                    result.flow_name,
                    1 if result.success else 0,
                    result.executed_steps,
                    result.total_steps,
                    result.error,
                    getattr(result, "started_at", None),
                    getattr(result, "finished_at", None),
                    json.dumps(result.execution_log, ensure_ascii=False, default=str),
                ),
            )

    def list_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """返回最近的运行摘要（不含完整日志）。"""
        with self._lock, closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT run_id, flow_name, success, executed_steps, total_steps, error, started_at, finished_at "
                "FROM runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """返回单次运行详情（含完整步骤日志）。不存在返回 None。"""
        with self._lock, closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["execution_log"] = json.loads(d["execution_log"]) if d["execution_log"] else []
            return d
