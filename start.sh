#!/bin/bash
# RPA 一键启动脚本
# 用法：./start.sh

set -e
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 生成并导出随机安全 Token，供 Python 后端和 Electron 共享
export RPA_API_TOKEN="token_$(date +%s)_$RANDOM"

echo "=============================="
echo "  RPA 启动中... (安全 Token: $RPA_API_TOKEN)"
echo "=============================="

# 1. 启动 Python 后端
echo "[1/2] 启动 Python 后端 (端口 8765)..."
source "$ROOT_DIR/.venv/bin/activate"
python "$ROOT_DIR/rpa_core/server.py" > /tmp/rpa_server.log 2>&1 &
SERVER_PID=$!
echo "      后端 PID: $SERVER_PID"

# 等待后端就绪
echo "      等待后端就绪..."
for i in {1..15}; do
  if curl -s http://127.0.0.1:8765/health > /dev/null 2>&1; then
    echo "      ✅ 后端已就绪"
    break
  fi
  sleep 1
done

# 2. 启动 Electron 客户端
echo "[2/2] 启动 Electron 客户端..."
cd "$ROOT_DIR/rpa-client"
npm run electron:dev

# 退出时清理后端进程
echo ""
echo "正在关闭后端服务 (PID: $SERVER_PID)..."
kill $SERVER_PID 2>/dev/null || true
echo "已关闭。"
