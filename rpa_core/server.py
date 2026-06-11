"""
RPA Core FastAPI Server
提供 HTTP API 接口供 Electron 客户端调用
"""
import sys
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager, contextmanager
import os
import uuid
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, Security, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, ConfigDict

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from rpa_core import FlowEngine, ExecutionResult
from rpa_core.browser import BrowserAdapter, BrowserPool
from rpa_core.storage import RunHistory
from rpa_core.scheduler import Scheduler, cron
from rpa_core.vault import get_vault
from rpa_core.ai import AILocator, FlowGenerator
from rpa_core.utils import setup_logger

# 配置日志
logger = setup_logger("FastAPIServer")

# ============================================
# API 令牌与安全配置
# ============================================
API_TOKEN = os.environ.get("RPA_API_TOKEN")
if not API_TOKEN:
    API_TOKEN = str(uuid.uuid4())
    logger.info(f"未检测到 RPA_API_TOKEN 环境变量，自动生成临时 API 令牌: {API_TOKEN}")
    # 打印特殊格式的 token 信息，供 Electron 主进程读取
    print(f"__RPA_API_TOKEN_START__={API_TOKEN}", flush=True)

# 将 Token 写入本地文件，供 Electron 客户端自愈匹配
try:
    token_file = Path(__file__).parent.parent / ".rpa_token"
    token_file.write_text(API_TOKEN)
    logger.info(f"已将 API Token 写入本地文件: {token_file}")
except Exception as e:
    logger.error(f"写入 Token 文件失败: {str(e)}")


security_header = APIKeyHeader(name="X-RPA-Token", auto_error=False)
security_bearer = HTTPBearer(auto_error=False)

async def verify_token(
    x_token: Optional[str] = Depends(security_header),
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)
):
    token = x_token or (auth.credentials if auth else None)
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid API Token")


# ============================================
# Pydantic 模型定义
# ============================================

class StepConfig(BaseModel):
    """
    Step 配置模型。
    extra='allow' 用于保留控制流字段（if 的 condition/then/else、
    loop 的 loop_type/steps/item_key/index_key，以及 retry 的 max_retries 等），
    否则 model_dump() 会把它们丢掉，导致 /execute 路径无法执行 if/loop。
    """
    model_config = ConfigDict(extra="allow")

    type: str = Field(..., description="Step 类型: open, click, input, wait, extract, if, loop")
    selector: Optional[str] = Field(None, description="选择器（CSS/XPath/text，无前缀默认按 CSS 解析）")
    selectors: Optional[List[str]] = Field(None, description="候选选择器列表，按优先级排序，运行时自愈回退")
    value: Optional[Any] = Field(None, description="值/URL")
    timeout: int = Field(10, description="超时时间（秒）")
    on_fail: str = Field("abort", description="失败策略: abort, skip, retry")
    save_path: Optional[str] = Field(None, description="保存路径（extract 专用）")
    context_key: Optional[str] = Field(None, description="上下文键名（extract 专用）")


class FlowDefinition(BaseModel):
    """Flow 定义模型"""
    name: str = Field("unnamed_flow", description="Flow 名称")
    description: Optional[str] = Field(None, description="Flow 描述")
    steps: List[StepConfig] = Field(..., description="Step 列表")


class ExecuteRequest(BaseModel):
    """执行请求模型"""
    flow: FlowDefinition = Field(..., description="Flow 定义")
    initial_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="初始上下文")


class ExecutionLogEntry(BaseModel):
    """执行日志条目"""
    step_index: int
    step_type: str
    start_time: str
    end_time: str
    duration_ms: float
    success: bool
    message: str
    screenshot: Optional[str] = None


class ExecuteResponse(BaseModel):
    """执行响应模型"""
    success: bool
    flow_name: str
    executed_steps: int
    total_steps: int
    context: Dict[str, Any]
    execution_log: List[ExecutionLogEntry]
    error: Optional[str] = None
    run_id: Optional[str] = None


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str


class ScheduleCreate(BaseModel):
    """定时任务创建模型"""
    name: str = Field(..., description="任务名称")
    flow: FlowDefinition = Field(..., description="要定时执行的 Flow")
    initial_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="初始上下文")
    schedule_type: str = Field(..., description="调度类型: cron | interval")
    schedule_value: str = Field(..., description="cron 表达式（5 字段）或 interval 秒数")
    enabled: bool = Field(True, description="是否启用")


class SecretSet(BaseModel):
    """凭据写入模型（明文仅在写入时出现，绝不回读）"""
    name: str = Field(..., description="凭据名，流程中用 {{secret:name}} 引用")
    value: str = Field(..., description="凭据明文值（将被加密存储）")


class GenerateFlowRequest(BaseModel):
    """自然语言生成 Flow 的请求"""
    instruction: str = Field(..., description="自然语言需求描述")
    url_hint: Optional[str] = Field(None, description="可选的起始网址提示")


# ============================================
# 全局状态
#
# 设计说明：
# - 共享一个浏览器实例（桌面单用户场景：拾取元素与运行流程用同一个 Chrome 窗口）。
# - 但「执行状态」不再共享：每次执行都新建一个 FlowEngine，拥有独立的
#   Context / 计数器 / 暂停-停止标志 / 日志回调，避免并发执行互相串改状态。
# - 由于只有一个浏览器，物理上无法真正并行驱动两个流程，因此用执行锁串行化：
#   已有流程在跑时，新的执行请求会被拒绝（HTTP 409 / WS error）。
# ============================================

_executor = ThreadPoolExecutor(max_workers=5)

_shared_browser: Optional[BrowserAdapter] = None
_browser_init_lock = threading.Lock()
_execution_lock = threading.Lock()

# 并发执行：RPA_BROWSER_POOL_SIZE > 1 时启用 headless 浏览器池，解除单浏览器串行。
# 默认 1 —— 沿用「单个可见浏览器 + 执行锁串行」（可观察、拾取共用同一窗口，零行为变化）。
_pool_size = max(1, int(os.environ.get("RPA_BROWSER_POOL_SIZE", "1")))
_browser_pool: Optional[BrowserPool] = None


class BrowserBusy(Exception):
    """没有空闲浏览器可供执行（串行模式下已有流程在跑，或池已满）。"""
    pass

# 运行历史（SQLite）
_history = RunHistory()

# 凭据保险库（加密）
_vault = get_vault()

# AI 视觉兜底定位（按 RPA_AI_FALLBACK 开关 + ANTHROPIC_API_KEY 决定是否真正可用）
_ai_locator = AILocator()

# 自然语言生成 Flow（用户主动触发，仅需 ANTHROPIC_API_KEY）
_flow_generator = FlowGenerator()


def _record_run(result: ExecutionResult) -> None:
    """把一次执行结果写入运行历史；记录失败不影响主流程。"""
    try:
        _history.record(result)
    except Exception as e:
        logger.error(f"写入运行历史失败: {str(e)}")


def _run_scheduled_flow(flow: Dict[str, Any], initial_context: Dict[str, Any]) -> ExecutionResult:
    """
    调度器执行流程的回调：在 worker 线程中阻塞借浏览器执行。
    串行模式下与手动执行共用执行锁；池模式下从池借一个 headless 浏览器。
    """
    with execution_browser(block=True) as browser:
        engine = FlowEngine(browser=browser, secret_resolver=_vault.get)
        result = engine.execute(flow, initial_context)
        _record_run(result)
        return result


# 调度引擎（cron / interval）
_scheduler = Scheduler(run_callback=_run_scheduled_flow)


def get_shared_browser() -> BrowserAdapter:
    """获取（必要时惰性创建）共享浏览器实例。拾取元素与串行执行共用它。线程安全。"""
    global _shared_browser
    with _browser_init_lock:
        if _shared_browser is None:
            _shared_browser = BrowserAdapter(ai_locator=_ai_locator)
        return _shared_browser


def _get_pool() -> Optional[BrowserPool]:
    global _browser_pool
    if _pool_size <= 1:
        return None
    if _browser_pool is None:
        with _browser_init_lock:
            if _browser_pool is None:
                _browser_pool = BrowserPool(
                    _pool_size,
                    factory=lambda: BrowserAdapter(headless=True, ai_locator=_ai_locator),
                )
    return _browser_pool


def acquire_execution_browser(block: bool = False):
    """
    借一个用于执行的浏览器。返回 (adapter, release_fn)；无空闲则抛 BrowserBusy。
    适合需要跨 await 持有浏览器的异步入口（/execute、/ws）。
    - 池模式（RPA_BROWSER_POOL_SIZE>1）：从 headless 池借/还，支持真并发。
    - 串行模式（默认）：用执行锁串行化，借出共享的可见浏览器（可观察、与拾取共用）。
    """
    pool = _get_pool()
    if pool is not None:
        adapter = pool.acquire(block=block)
        if adapter is None:
            raise BrowserBusy()
        return adapter, (lambda: pool.release(adapter))
    acquired = _execution_lock.acquire(blocking=block)
    if not acquired:
        raise BrowserBusy()
    return get_shared_browser(), _execution_lock.release


@contextmanager
def execution_browser(block: bool = False):
    """借浏览器的上下文管理器（同步场景，如调度 worker 线程）。"""
    adapter, release = acquire_execution_browser(block=block)
    try:
        yield adapter
    finally:
        release()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global _shared_browser
    logger.info("启动 RPA Server...")
    if _pool_size > 1:
        logger.info(f"浏览器池已启用，容量 = {_pool_size}（headless 并发执行）")
    _scheduler.start()

    yield

    # 清理资源：停止调度、关闭共享浏览器与浏览器池
    logger.info("关闭 RPA Server...")
    _scheduler.stop()
    with _browser_init_lock:
        if _shared_browser is not None:
            _shared_browser.close()
            _shared_browser = None
    if _browser_pool is not None:
        _browser_pool.close_all()


# ============================================
# FastAPI 应用
# ============================================

app = FastAPI(
    title="RPA Core API",
    description="RPA 流程引擎 HTTP API",
    version="0.1.0",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# API 路由
# ============================================

@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """健康检查"""
    return HealthResponse(
        status="ok",
        version="0.1.0"
    )


@app.post("/pick-element/start", dependencies=[Depends(verify_token)])
async def pick_element_start() -> Dict[str, Any]:
    """开始元素拾取模式"""
    try:
        browser = get_shared_browser()
        browser._ensure_page()
        browser.pick_element_start()
        return {"success": True, "message": "元素拾取模式已启动"}
    except Exception as e:
        logger.error(f"启动元素拾取失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pick-element/result", dependencies=[Depends(verify_token)])
async def pick_element_result() -> Dict[str, Any]:
    """获取元素拾取结果"""
    try:
        if _shared_browser is None:
            return {"success": False, "selector": None, "selectors": [], "message": "浏览器未启动"}
        result = _shared_browser.pick_element_result()
        if not result:
            return {"success": True, "selector": None, "selectors": []}
        # result: {"selector": 首选, "selectors": [候选...]}
        return {"success": True, "selector": result["selector"], "selectors": result["selectors"]}
    except Exception as e:
        logger.error(f"获取元素拾取结果失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def make_log_callback(websocket: WebSocket, loop: asyncio.AbstractEventLoop):
    """创建线程安全的 WebSocket 日志回调"""
    def log_callback(msg: Dict[str, Any]):
        async def send():
            try:
                await websocket.send_json(msg)
            except Exception:
                pass
        asyncio.run_coroutine_threadsafe(send(), loop)
    return log_callback


@app.websocket("/ws/execute")
async def ws_execute_flow(websocket: WebSocket, token: Optional[str] = None):
    """
    通过 WebSocket 执行 Flow 并实时获取进度和控制
    支持 query 参数中的 token 鉴权
    """
    global _executor

    # 先接受连接，再验证 Token（Starlette 不允许在 accept 前 close）
    await websocket.accept()
    logger.info("WebSocket 连接已建立")

    # 验证 Token
    if token != API_TOKEN:
        logger.warning(f"WebSocket Token 验证失败: 收到='{token}', 期望='{API_TOKEN}'")
        await websocket.send_json({"type": "error", "message": "认证失败: API Token 无效"})
        await websocket.close(code=1008)
        return

    logger.info("WebSocket Token 验证通过")

    engine: Optional[FlowEngine] = None
    release_browser = None
    try:
        # 等待客户端发送初始运行配置
        init_data = await websocket.receive_json()
        action = init_data.get("action")

        if action != "start":
            await websocket.send_json({"type": "error", "message": "首个消息动作必须为 'start'"})
            await websocket.close(code=1003)
            return

        flow_data = init_data.get("flow")
        initial_context = init_data.get("initial_context", {})

        if not flow_data or "steps" not in flow_data:
            await websocket.send_json({"type": "error", "message": "缺失有效的 'flow' 定义"})
            await websocket.close(code=1003)
            return

        # 借一个执行浏览器（串行模式=共享可见浏览器；池模式=headless 并发）
        try:
            browser, release_browser = acquire_execution_browser(block=False)
        except BrowserBusy:
            await websocket.send_json({"type": "error", "message": "无空闲浏览器，请稍后再试"})
            await websocket.close(code=1013)
            return

        # 每次执行新建独立引擎：拥有自己的 Context / 计数器 / 暂停-停止标志
        loop = asyncio.get_running_loop()
        engine = FlowEngine(browser=browser, secret_resolver=_vault.get)
        engine.log_callback = make_log_callback(websocket, loop)

        # 在线程池中执行流程
        logger.info(f"在线程池中启动流程: {flow_data.get('name')}")
        future = loop.run_in_executor(_executor, engine.execute, flow_data, initial_context)

        # 轮询等待流程结束，同时读取客户端可能下发的控制指令
        while not future.done():
            try:
                # 轮询读取控制指令（超时 100ms）
                command = await asyncio.wait_for(websocket.receive_json(), timeout=0.1)
                cmd_action = command.get("action")

                if cmd_action == "pause":
                    engine.pause()
                elif cmd_action == "resume":
                    engine.resume()
                elif cmd_action == "stop":
                    engine.stop()
            except asyncio.TimeoutError:
                # 轮询无控制指令，继续等待
                continue
            except WebSocketDisconnect:
                # 用户断开连接，中止流程执行
                logger.warning("客户端断开连接，中止流程")
                engine.stop()
                break
            except Exception as e:
                logger.error(f"WebSocket 处理指令异常: {str(e)}")
                engine.stop()
                break

        # 执行完成，发送结果
        if not future.cancelled():
            result = await future
            _record_run(result)
            await websocket.send_json({
                "type": "result",
                "data": {
                    "success": result.success,
                    "flow_name": result.flow_name,
                    "executed_steps": result.executed_steps,
                    "total_steps": result.total_steps,
                    "error": result.error,
                    "context": result.context,
                    "run_id": result.run_id
                }
            })

    except WebSocketDisconnect:
        logger.info("WebSocket 连接正常关闭")
    except Exception as e:
        logger.error(f"WebSocket 流程执行异常: {str(e)}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": f"系统错误: {str(e)}"})
        except Exception:
            pass
    finally:
        if engine is not None:
            engine.log_callback = None
        if release_browser is not None:
            release_browser()


@app.post("/execute", response_model=ExecuteResponse, dependencies=[Depends(verify_token)])
async def execute_flow(request: ExecuteRequest) -> ExecuteResponse:
    """执行 Flow"""
    # 借一个执行浏览器（串行模式=共享可见浏览器；池模式=headless 并发）
    try:
        browser, release_browser = acquire_execution_browser(block=False)
    except BrowserBusy:
        raise HTTPException(status_code=409, detail="无空闲浏览器，请稍后再试")

    try:
        # 将 Pydantic 模型转换为字典（extra='allow' 保留 if/loop 等控制流字段）
        flow_dict = request.flow.model_dump(exclude_none=True)

        logger.info(f"收到执行请求: {flow_dict['name']}, {len(flow_dict['steps'])} 个步骤")

        # 每次执行新建独立引擎，避免并发串改状态
        engine = FlowEngine(browser=browser, secret_resolver=_vault.get)

        # 在线程池中执行，避免阻塞事件循环
        loop = asyncio.get_running_loop()
        result: ExecutionResult = await loop.run_in_executor(
            _executor, engine.execute, flow_dict, request.initial_context
        )

        # 写入运行历史
        _record_run(result)

        # 转换执行日志
        execution_log = [
            ExecutionLogEntry(**log_entry)
            for log_entry in result.execution_log
        ]

        logger.info(f"执行完成: run_id={result.run_id}, success={result.success}, executed={result.executed_steps}/{result.total_steps}")

        return ExecuteResponse(
            success=result.success,
            flow_name=result.flow_name,
            executed_steps=result.executed_steps,
            total_steps=result.total_steps,
            context=result.context,
            execution_log=execution_log,
            error=result.error,
            run_id=result.run_id
        )

    except Exception as e:
        logger.error(f"执行出错: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        release_browser()


@app.post("/validate", dependencies=[Depends(verify_token)])
async def validate_flow(flow: FlowDefinition) -> Dict[str, Any]:
    """验证 Flow 定义"""
    valid_step_types = {"open", "click", "input", "wait", "extract", "if", "loop",
                        "select", "switch_tab", "download"}
    errors: List[str] = []

    for i, step in enumerate(flow.steps):
        if step.type not in valid_step_types:
            errors.append(f"Step {i+1}: 未知类型 '{step.type}'")

        # 验证必填字段
        if step.type == "open" and not step.value:
            errors.append(f"Step {i+1} (open): 需要 value (URL)")
        if step.type in {"click", "input"} and not step.selector:
            errors.append(f"Step {i+1} ({step.type}): 需要 selector")
        if step.type == "input" and step.value is None:
            errors.append(f"Step {i+1} (input): 需要 value")
        if step.type == "wait" and step.value is None:
            errors.append(f"Step {i+1} (wait): 需要 value (秒数)")

    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


@app.get("/step-types", dependencies=[Depends(verify_token)])
async def get_step_types() -> Dict[str, Any]:
    """获取可用的 Step 类型"""
    return {
        "step_types": [
            {
                "type": "open",
                "name": "打开页面",
                "description": "打开指定 URL",
                "required_fields": ["value"],
                "optional_fields": ["timeout", "on_fail"]
            },
            {
                "type": "click",
                "name": "点击元素",
                "description": "点击指定选择器的元素",
                "required_fields": ["selector"],
                "optional_fields": ["timeout", "on_fail"]
            },
            {
                "type": "input",
                "name": "输入文本",
                "description": "向指定元素输入文本",
                "required_fields": ["selector", "value"],
                "optional_fields": ["timeout", "on_fail"]
            },
            {
                "type": "wait",
                "name": "等待",
                "description": "等待指定秒数",
                "required_fields": ["value"],
                "optional_fields": ["on_fail"]
            },
            {
                "type": "extract",
                "name": "提取内容",
                "description": "提取元素内容并保存",
                "required_fields": ["selector"],
                "optional_fields": ["save_path", "context_key", "timeout", "on_fail", "frame"]
            },
            {
                "type": "select",
                "name": "下拉选择",
                "description": "操作 <select> 下拉框，按文本/值/下标选择",
                "required_fields": ["selector", "value"],
                "optional_fields": ["by", "timeout", "on_fail", "frame"]
            },
            {
                "type": "switch_tab",
                "name": "切换标签页",
                "description": "切换当前操作的标签页或打开新标签页",
                "required_fields": [],
                "optional_fields": ["value", "new_tab", "url", "on_fail"]
            },
            {
                "type": "download",
                "name": "文件下载",
                "description": "点击触发下载并等待完成（保存到沙箱目录）",
                "required_fields": ["selector"],
                "optional_fields": ["save_path", "timeout", "on_fail", "frame"]
            }
        ]
    }


# ============================================
# 运行历史
# ============================================

@app.get("/runs", dependencies=[Depends(verify_token)])
async def list_runs(limit: int = 50) -> Dict[str, Any]:
    """列出最近的运行记录（摘要）。"""
    limit = max(1, min(limit, 500))
    return {"runs": _history.list_runs(limit=limit)}


@app.get("/runs/{run_id}", dependencies=[Depends(verify_token)])
async def get_run(run_id: str) -> Dict[str, Any]:
    """获取单次运行详情（含完整步骤日志与失败截图路径）。"""
    run = _history.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return run


# ============================================
# 定时任务调度
# ============================================

def _validate_schedule(schedule_type: str, schedule_value: str) -> None:
    """校验调度配置；非法则抛 HTTPException(400)。"""
    if schedule_type == "cron":
        try:
            cron.parse_cron(schedule_value)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"cron 表达式非法: {e}")
    elif schedule_type == "interval":
        try:
            if int(schedule_value) <= 0:
                raise ValueError
        except ValueError:
            raise HTTPException(status_code=400, detail="interval 必须为正整数秒数")
    else:
        raise HTTPException(status_code=400, detail="schedule_type 必须为 cron 或 interval")


@app.post("/schedules", dependencies=[Depends(verify_token)])
async def create_schedule(req: ScheduleCreate) -> Dict[str, Any]:
    """创建定时任务。"""
    _validate_schedule(req.schedule_type, req.schedule_value)
    from datetime import datetime
    job = _scheduler.store.create({
        "name": req.name,
        "flow": req.flow.model_dump(exclude_none=True),
        "initial_context": req.initial_context or {},
        "schedule_type": req.schedule_type,
        "schedule_value": req.schedule_value,
        "enabled": req.enabled,
        "created_at": datetime.now().isoformat(),
    })
    return job


@app.get("/schedules", dependencies=[Depends(verify_token)])
async def list_schedules() -> Dict[str, Any]:
    """列出所有定时任务。"""
    return {"schedules": _scheduler.store.list()}


@app.get("/schedules/{job_id}", dependencies=[Depends(verify_token)])
async def get_schedule(job_id: str) -> Dict[str, Any]:
    job = _scheduler.store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="定时任务不存在")
    return job


@app.patch("/schedules/{job_id}", dependencies=[Depends(verify_token)])
async def update_schedule(job_id: str, enabled: bool) -> Dict[str, Any]:
    """启用/停用定时任务。"""
    if _scheduler.store.get(job_id) is None:
        raise HTTPException(status_code=404, detail="定时任务不存在")
    _scheduler.store.update_fields(job_id, enabled=1 if enabled else 0)
    return _scheduler.store.get(job_id)


@app.delete("/schedules/{job_id}", dependencies=[Depends(verify_token)])
async def delete_schedule(job_id: str) -> Dict[str, Any]:
    if not _scheduler.store.delete(job_id):
        raise HTTPException(status_code=404, detail="定时任务不存在")
    return {"success": True}


@app.post("/schedules/{job_id}/run-now", dependencies=[Depends(verify_token)])
async def run_schedule_now(job_id: str) -> Dict[str, Any]:
    """立即触发一次定时任务（入队，由 worker 串行执行）。"""
    if not _scheduler.run_now(job_id):
        raise HTTPException(status_code=404, detail="定时任务不存在")
    return {"success": True, "message": "已入队，将尽快执行"}


# ============================================
# 凭据保险库
# ============================================

@app.post("/secrets", dependencies=[Depends(verify_token)])
async def set_secret(req: SecretSet) -> Dict[str, Any]:
    """新增或更新一个加密凭据。流程中用 {{secret:name}} 引用，明文不会回读。"""
    if not req.name:
        raise HTTPException(status_code=400, detail="凭据名不能为空")
    _vault.set(req.name, req.value)
    return {"success": True, "name": req.name}


@app.get("/secrets", dependencies=[Depends(verify_token)])
async def list_secrets() -> Dict[str, Any]:
    """列出凭据名称（绝不返回明文）。"""
    return {"secrets": _vault.list_names()}


@app.delete("/secrets/{name}", dependencies=[Depends(verify_token)])
async def delete_secret(name: str) -> Dict[str, Any]:
    if not _vault.delete(name):
        raise HTTPException(status_code=404, detail="凭据不存在")
    return {"success": True}


# ============================================
# 自然语言生成 Flow
# ============================================

@app.post("/flows/generate", dependencies=[Depends(verify_token)])
async def generate_flow(req: GenerateFlowRequest) -> Dict[str, Any]:
    """根据自然语言需求生成一个 Flow（在线程池中调用 LLM，避免阻塞事件循环）。"""
    if not _flow_generator.available:
        raise HTTPException(
            status_code=400,
            detail="AI 生成不可用：请安装 anthropic 并配置 ANTHROPIC_API_KEY",
        )
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        _executor, _flow_generator.generate, req.instruction, req.url_hint
    )
    return result


# ============================================
# 主入口
# ============================================

if __name__ == "__main__":
    import uvicorn

    logger.info("=" * 50)
    logger.info("RPA Core FastAPI Server")
    logger.info("=" * 50)

    uvicorn.run(
        "server:app",
        host="127.0.0.1",
        port=8765,
        log_level="info"
    )
