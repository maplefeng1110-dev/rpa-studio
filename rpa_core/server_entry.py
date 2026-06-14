"""
打包后的后端入口。
server.py 的 __main__ 用的是 import-string 'server:app'，PyInstaller 冻结后不可用；
这里以编程方式直接把 app 对象交给 uvicorn 托管，供冻结的可执行文件使用。

端口可用环境变量 RPA_PORT 覆盖（默认 8765）。
"""
import os

import uvicorn

from rpa_core.server import app


def main() -> None:
    port = int(os.environ.get("RPA_PORT", "8765"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
