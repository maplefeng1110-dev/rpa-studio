"""
调度任务存储（SQLite）
持久化定时任务定义，支持跨重启恢复。
"""
import json
import sqlite3
import threading
import uuid
from contextlib import closing
from typing import Any, Dict, List, Optional

from ..storage import get_data_dir


class ScheduleStore:
    """定时任务的 SQLite 存储。线程安全。"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or (get_data_dir() / "schedules.db"))
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock, closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schedules (
                    id              TEXT PRIMARY KEY,
                    name            TEXT,
                    flow            TEXT,
                    initial_context TEXT,
                    schedule_type   TEXT,
                    schedule_value  TEXT,
                    enabled         INTEGER DEFAULT 1,
                    created_at      TEXT,
                    last_run        TEXT,
                    next_run        TEXT,
                    last_status     TEXT
                )
                """
            )

    def create(self, job: Dict[str, Any]) -> Dict[str, Any]:
        job = dict(job)
        job.setdefault("id", str(uuid.uuid4()))
        job.setdefault("enabled", 1)
        with self._lock, closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute(
                "INSERT INTO schedules (id, name, flow, initial_context, schedule_type, "
                "schedule_value, enabled, created_at, last_run, next_run, last_status) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    job["id"], job.get("name"),
                    json.dumps(job.get("flow"), ensure_ascii=False, default=str),
                    json.dumps(job.get("initial_context") or {}, ensure_ascii=False, default=str),
                    job.get("schedule_type"), str(job.get("schedule_value")),
                    1 if job.get("enabled", 1) else 0,
                    job.get("created_at"), job.get("last_run"),
                    job.get("next_run"), job.get("last_status"),
                ),
            )
        return self.get(job["id"])

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d["flow"] = json.loads(d["flow"]) if d.get("flow") else None
        d["initial_context"] = json.loads(d["initial_context"]) if d.get("initial_context") else {}
        d["enabled"] = bool(d["enabled"])
        return d

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock, closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM schedules WHERE id = ?", (job_id,)).fetchone()
            return self._row_to_dict(row) if row else None

    def list(self) -> List[Dict[str, Any]]:
        with self._lock, closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM schedules ORDER BY created_at DESC").fetchall()
            return [self._row_to_dict(r) for r in rows]

    def update_fields(self, job_id: str, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [job_id]
        with self._lock, closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute(f"UPDATE schedules SET {cols} WHERE id = ?", vals)

    def delete(self, job_id: str) -> bool:
        with self._lock, closing(sqlite3.connect(self.db_path)) as conn, conn:
            cur = conn.execute("DELETE FROM schedules WHERE id = ?", (job_id,))
            return cur.rowcount > 0
