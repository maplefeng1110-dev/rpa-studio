"""
凭据保险库
用 Fernet（AES-128-CBC + HMAC 认证加密）加密存储账号密码/令牌等敏感值。
数据库里只存密文；明文仅在解密取用的瞬间出现在内存，不写入运行历史与日志。

密钥来源（优先级）：
  1. 环境变量 RPA_SECRET_KEY（urlsafe base64 的 32 字节 Fernet 密钥）
  2. 否则读取/生成 <data>/secret.key（权限 0600），随机生成并落盘

注意：方案 2 下密钥与密文同机，可防"流程 JSON / 运行历史泄露明文"，但无法防御
能读取该机文件的同用户。更强的隔离请通过 RPA_SECRET_KEY 注入由外部托管的密钥。
"""
import os
import sqlite3
import threading
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from cryptography.fernet import Fernet, InvalidToken

from ..storage import get_data_dir


def _load_or_create_key() -> bytes:
    env = os.environ.get("RPA_SECRET_KEY")
    if env:
        return env.encode() if isinstance(env, str) else env

    key_path = get_data_dir() / "secret.key"
    if key_path.exists():
        return key_path.read_bytes().strip()

    key = Fernet.generate_key()
    key_path.write_bytes(key)
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    return key


class SecretVault:
    """加密凭据存储。线程安全。"""

    def __init__(self, db_path: Optional[str] = None, key: Optional[bytes] = None):
        self.db_path = str(db_path or (get_data_dir() / "vault.db"))
        self._fernet = Fernet(key or _load_or_create_key())
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock, closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS secrets (
                    name        TEXT PRIMARY KEY,
                    ciphertext  BLOB NOT NULL,
                    updated_at  TEXT
                )
                """
            )

    def set(self, name: str, value: str) -> None:
        """新增或更新一个凭据。"""
        if not name:
            raise ValueError("凭据名不能为空")
        token = self._fernet.encrypt(value.encode("utf-8"))
        with self._lock, closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute(
                "INSERT INTO secrets (name, ciphertext, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET ciphertext=excluded.ciphertext, updated_at=excluded.updated_at",
                (name, token, datetime.now().isoformat()),
            )

    def get(self, name: str) -> Optional[str]:
        """取出并解密一个凭据；不存在返回 None。"""
        with self._lock, closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute("SELECT ciphertext FROM secrets WHERE name = ?", (name,)).fetchone()
        if not row:
            return None
        try:
            return self._fernet.decrypt(row[0]).decode("utf-8")
        except InvalidToken:
            # 密钥与密文不匹配（如更换了 RPA_SECRET_KEY）
            raise ValueError(f"凭据 '{name}' 解密失败：密钥不匹配")

    def list_names(self) -> List[str]:
        """只返回凭据名称，绝不返回明文。__rpa_ 开头的内部保留名（如 AI key）不展示。"""
        with self._lock, closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute("SELECT name, updated_at FROM secrets ORDER BY name").fetchall()
        return [{"name": r[0], "updated_at": r[1]} for r in rows if not r[0].startswith("__rpa_")]

    def delete(self, name: str) -> bool:
        with self._lock, closing(sqlite3.connect(self.db_path)) as conn, conn:
            cur = conn.execute("DELETE FROM secrets WHERE name = ?", (name,))
            return cur.rowcount > 0


_default_vault: Optional[SecretVault] = None
_vault_lock = threading.Lock()


def get_vault() -> SecretVault:
    """进程级共享的默认保险库实例。"""
    global _default_vault
    with _vault_lock:
        if _default_vault is None:
            _default_vault = SecretVault()
        return _default_vault
