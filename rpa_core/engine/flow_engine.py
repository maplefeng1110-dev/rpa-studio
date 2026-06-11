"""
Flow Engine 模块
负责加载和执行 Flow 定义
"""
import json
import logging
import operator
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from ..browser import BrowserAdapter
from ..steps import (
    BaseStep, StepResult, StepError, OpenStep, ClickStep, InputStep, WaitStep, ExtractStep,
    SelectStep, SwitchTabStep, DownloadStep,
)
from ..utils import RuntimeContext, setup_logger, get_output_base


def eval_condition(condition: str, context: RuntimeContext) -> bool:
    """
    评估条件字符串。支持 ==, !=, >=, <=, >, <, contains 等操作符。
    两边操作数会被自动渲染，如果渲染结果符合数值格式则自动转为数值进行比较。
    """
    if not isinstance(condition, str):
        return bool(condition)
        
    operators = {
        "==": operator.eq,
        "!=": operator.ne,
        ">=": operator.ge,
        "<=": operator.le,
        ">": operator.gt,
        "<": operator.lt,
        "contains": lambda a, b: str(b) in str(a)
    }
    
    # 查找并提取操作符两边的操作数
    for op_str, op_func in operators.items():
        if op_str in condition:
            left, right = condition.split(op_str, 1)
            # 渲染两边的操作数（如果是纯 "{{var}}"，保留其原始类型）
            left_val = context.render(left.strip())
            right_val = context.render(right.strip())
            
            # 尝试做数字类型转换以便进行大小比较
            try:
                if isinstance(left_val, (int, float)) or isinstance(right_val, (int, float)):
                    if isinstance(left_val, float) or isinstance(right_val, float):
                        left_val = float(left_val)
                        right_val = float(right_val)
                    else:
                        left_val = int(left_val)
                        right_val = int(right_val)
                elif isinstance(left_val, str) and isinstance(right_val, str):
                    if (left_val.isdigit() or (left_val.replace('.', '', 1).isdigit() and '.' in left_val)) and \
                       (right_val.isdigit() or (right_val.replace('.', '', 1).isdigit() and '.' in right_val)):
                        if '.' in left_val or '.' in right_val:
                            left_val = float(left_val)
                            right_val = float(right_val)
                        else:
                            left_val = int(left_val)
                            right_val = int(right_val)
            except (ValueError, TypeError):
                pass
            
            # 清除字符串两侧引号
            if isinstance(left_val, str):
                left_val = left_val.strip("\"'")
            if isinstance(right_val, str):
                right_val = right_val.strip("\"'")
                
            return op_func(left_val, right_val)
            
    # 如果没有任何运算符，渲染后判断其真值
    rendered = context.render(condition)
    if isinstance(rendered, bool):
        return rendered
    if isinstance(rendered, (int, float)):
        return bool(rendered)
    if isinstance(rendered, str):
        val = rendered.strip().lower()
        if val in ("true", "1", "yes", "ok"):
            return True
        if val in ("false", "0", "no", "none", ""):
            return False
        return bool(rendered)
    return bool(rendered)


# 配置日志（输出到控制台和文件）
logger = setup_logger("FlowEngine")


# Step 类型注册表
STEP_REGISTRY: Dict[str, Type[BaseStep]] = {
    "open": OpenStep,
    "click": ClickStep,
    "input": InputStep,
    "wait": WaitStep,
    "extract": ExtractStep,
    "select": SelectStep,
    "switch_tab": SwitchTabStep,
    "download": DownloadStep,
}


class FlowLoadError(Exception):
    """Flow 加载异常"""
    pass


class FlowAbortError(Exception):
    """Flow 中止异常"""
    pass


class ExecutionResult:
    """Flow 执行结果"""
    
    def __init__(
        self,
        success: bool,
        flow_name: str,
        executed_steps: int,
        total_steps: int,
        context: Dict[str, Any],
        execution_log: List[Dict[str, Any]],
        error: Optional[str] = None,
        run_id: Optional[str] = None,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None
    ):
        self.success = success
        self.flow_name = flow_name
        self.executed_steps = executed_steps
        self.total_steps = total_steps
        self.context = context
        self.execution_log = execution_log
        self.error = error
        self.run_id = run_id
        self.started_at = started_at
        self.finished_at = finished_at
    
    def __repr__(self) -> str:
        status = "成功" if self.success else "失败"
        return f"ExecutionResult({self.flow_name}: {status}, {self.executed_steps}/{self.total_steps})"


class FlowEngine:
    """
    流程引擎
    - 加载 Flow 定义（JSON）
    - 顺序执行 Step
    - 捕获异常并根据 on_fail 策略处理
    - 更新 Runtime Context
    """
    
    def __init__(self, browser: Optional[BrowserAdapter] = None, log_callback=None, secret_resolver=None):
        """
        初始化流程引擎

        Args:
            browser: 浏览器适配器实例，如果不提供则自动创建
            log_callback: 实时日志和进度回调函数，接收 Dict
            secret_resolver: 凭据解析回调 name -> value，用于 {{secret:name}}
        """
        self._browser = browser
        self._owns_browser = browser is None
        self._secret_resolver = secret_resolver
        self._context: Optional[RuntimeContext] = None
        self._execution_log: List[Dict[str, Any]] = []
        self.log_callback = log_callback

        # 运行标识与时间（每次 execute 重置）
        self.run_id: Optional[str] = None
        self.started_at: Optional[str] = None

        # 控制状态
        self._is_paused = False
        self._is_stopped = False
    
    def pause(self) -> None:
        """暂停流程执行"""
        self._is_paused = True
        logger.info("流程引擎已暂停")
        if self.log_callback:
            self.log_callback({"type": "status", "data": {"status": "paused", "message": "流程已暂停"}})

    def resume(self) -> None:
        """恢复流程执行"""
        self._is_paused = False
        logger.info("流程引擎已恢复")
        if self.log_callback:
            self.log_callback({"type": "status", "data": {"status": "running", "message": "流程已恢复"}})

    def stop(self) -> None:
        """中止流程执行"""
        self._is_stopped = True
        self._is_paused = False
        logger.info("流程引擎已中止")
        if self.log_callback:
            self.log_callback({"type": "status", "data": {"status": "stopped", "message": "流程已中止"}})

    def _check_pause_stop(self) -> None:
        """检查流程执行的暂停或中止状态"""
        if self._is_stopped:
            raise FlowAbortError("流程已被用户中止")
            
        while self._is_paused:
            if self._is_stopped:
                raise FlowAbortError("流程已被用户中止")
            time.sleep(0.5)
    
    def _ensure_browser(self) -> BrowserAdapter:
        """确保浏览器实例存在"""
        if self._browser is None:
            self._browser = BrowserAdapter()
        return self._browser

    def _capture_failure_screenshot(self, index: int) -> Optional[str]:
        """
        步骤失败时抓取当前页面截图，存到 <output>/runs/<run_id>/。
        截图失败（如浏览器尚未启动）不应影响主流程，返回 None。
        """
        try:
            if self._browser is None or self._browser._page is None:
                return None
            run_dir = get_output_base() / "runs" / (self.run_id or "unknown")
            run_dir.mkdir(parents=True, exist_ok=True)
            path = run_dir / f"step_{index + 1}_fail.png"
            self._browser.screenshot(str(path))
            logger.info(f"[Step {index+1}] 已保存失败截图: {path}")
            return str(path)
        except Exception as e:
            logger.warning(f"[Step {index+1}] 失败截图抓取失败: {str(e)}")
            return None
    
    def load_flow(self, flow_path: str) -> Dict[str, Any]:
        """
        从 JSON 文件加载 Flow 定义
        
        Args:
            flow_path: Flow JSON 文件路径
        
        Returns:
            Flow 定义字典
        """
        path = Path(flow_path)
        if not path.exists():
            raise FlowLoadError(f"Flow 文件不存在: {flow_path}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                flow = json.load(f)
        except json.JSONDecodeError as e:
            raise FlowLoadError(f"Flow JSON 解析失败: {str(e)}")
        
        if "steps" not in flow:
            raise FlowLoadError("Flow 定义缺少 'steps' 字段")
        
        return flow
    
    def execute(
        self, 
        flow: Dict[str, Any], 
        initial_context: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """
        执行 Flow
        
        Args:
            flow: Flow 定义字典
            initial_context: 初始上下文数据
        
        Returns:
            ExecutionResult: 执行结果
        """
        flow_name = flow.get("name", "unnamed_flow")
        steps = flow.get("steps", [])

        # 初始化运行标识、上下文和计数器
        self.run_id = str(uuid.uuid4())
        self.started_at = datetime.now().isoformat()
        self._context = RuntimeContext(initial_context, secret_resolver=self._secret_resolver)
        self._execution_log = []
        self._step_counter = 0
        self._executed_step_count = 0

        logger.info(f"开始执行 Flow: {flow_name} (run_id={self.run_id}), 共 {len(steps)} 个步骤")

        browser = self._ensure_browser()

        def _build_result(success: bool, error: Optional[str], total_override: Optional[int] = None) -> ExecutionResult:
            return ExecutionResult(
                success=success,
                flow_name=flow_name,
                executed_steps=self._executed_step_count,
                total_steps=total_override if total_override is not None else self._step_counter,
                context=self._context.to_dict(),
                execution_log=self._execution_log,
                error=error,
                run_id=self.run_id,
                started_at=self.started_at,
                finished_at=datetime.now().isoformat(),
            )

        try:
            success = self._execute_step_list(steps, browser)

            if not success:
                return _build_result(False, "Flow 执行过程中有步骤失败")

            logger.info(f"Flow {flow_name} 执行完成")
            return _build_result(True, None)

        except FlowAbortError as e:
            logger.error(f"Flow 中止: {str(e)}")
            return _build_result(False, str(e), total_override=max(self._step_counter, 1))

    def _execute_step_list(self, steps: List[Dict[str, Any]], browser: BrowserAdapter) -> bool:
        """递归执行步骤列表"""
        for step_config in steps:
            self._check_pause_stop()
            current_index = self._step_counter
            self._step_counter += 1
            
            step_result = self._execute_step(current_index, step_config, browser)
            
            if step_result is None:
                # Step 被跳过
                continue
                
            if step_result.success:
                self._executed_step_count += 1
            else:
                # 执行失败且未被 on_fail 处理
                return False
        return True
    
    def _execute_step(
        self, 
        index: int, 
        step_config: Dict[str, Any], 
        browser: BrowserAdapter
    ) -> Optional[StepResult]:
        """
        执行单个 Step
        
        Args:
            index: Step 索引
            step_config: Step 配置
            browser: 浏览器适配器
        
        Returns:
            StepResult 或 None（如果被跳过）
        """
        step_type = step_config.get("type")
        on_fail = step_config.get("on_fail", "abort")
        
        # 特殊处理控制流步骤
        if step_type == "if":
            return self._execute_if_step(index, step_config, browser)
        elif step_type == "loop":
            return self._execute_loop_step(index, step_config, browser)
        
        if step_type not in STEP_REGISTRY:
            raise FlowAbortError(f"未知的 Step 类型: {step_type}")
        
        step_class = STEP_REGISTRY[step_type]
        step = step_class(step_config)
        
        logger.info(f"[Step {index+1}] 执行 {step_type}: {step_config.get('selector', step_config.get('value', ''))}")
        if self.log_callback:
            self.log_callback({
                "type": "step_start",
                "data": {
                    "step_index": index,
                    "step_type": step_type,
                    "selector": step_config.get("selector"),
                    "value": step_config.get("value"),
                    "message": f"正在执行 {step_type} 步骤..."
                }
            })
        
        start_time = datetime.now()
        max_retries = step_config.get("max_retries", 3)
        retry_delay = step_config.get("retry_delay", 2)
        
        # 支持失败重试
        for attempt in range(max_retries + 1):
            try:
                result = step.execute(browser, self._context)
                self._log_step_execution(index, step_type, start_time, result)
                
                # 如果是重试成功的，日志加上重试标识
                if attempt > 0:
                    result.message = f"{result.message} (在第 {attempt} 次重试后成功)"
                logger.info(f"[Step {index+1}] {result.message}")
                return result
                
            except StepError as e:
                if on_fail == "retry" and attempt < max_retries:
                    logger.warning(f"[Step {index+1}] 执行失败，正在进行第 {attempt+1}/{max_retries} 次重试... 错误: {str(e)}")
                    time.sleep(retry_delay)
                    continue
                
                logger.warning(f"[Step {index+1}] 执行失败: {str(e)}")
                screenshot = self._capture_failure_screenshot(index)
                self._log_step_execution(
                    index, step_type, start_time,
                    StepResult(success=False, message=str(e)),
                    screenshot=screenshot
                )
                return self._handle_failure(index, step_type, on_fail, str(e))
            except Exception as e:
                # 捕获其他非 StepError 系统异常
                if on_fail == "retry" and attempt < max_retries:
                    logger.warning(f"[Step {index+1}] 系统异常，正在进行第 {attempt+1}/{max_retries} 次重试... 错误: {str(e)}")
                    time.sleep(retry_delay)
                    continue

                logger.warning(f"[Step {index+1}] 系统异常: {str(e)}")
                screenshot = self._capture_failure_screenshot(index)
                self._log_step_execution(
                    index, step_type, start_time,
                    StepResult(success=False, message=str(e)),
                    screenshot=screenshot
                )
                return self._handle_failure(index, step_type, on_fail, str(e))

    def _execute_if_step(self, index: int, step_config: Dict[str, Any], browser: BrowserAdapter) -> StepResult:
        """执行条件分支步骤"""
        condition = step_config.get("condition", "")
        then_steps = step_config.get("then", [])
        else_steps = step_config.get("else", [])
        
        logger.info(f"[Step {index+1}] 执行 if 条件判断: {condition}")
        start_time = datetime.now()
        
        try:
            # 评估条件
            condition_result = eval_condition(condition, self._context)
            logger.info(f"[Step {index+1}] 条件 [{condition}] 评估结果为: {condition_result}")
            
            # 选择分支
            branch_steps = then_steps if condition_result else else_steps
            branch_name = "then" if condition_result else "else"
            
            if branch_steps:
                logger.info(f"[Step {index+1}] 执行 {branch_name} 分支, 共 {len(branch_steps)} 个子步骤")
                success = self._execute_step_list(branch_steps, browser)
                if not success:
                    result = StepResult(success=False, message=f"if {branch_name} 分支执行失败")
                    self._log_step_execution(index, "if", start_time, result)
                    return result
            else:
                logger.info(f"[Step {index+1}] {branch_name} 分支无子步骤，跳过")
                
            result = StepResult(success=True, message=f"if 条件判断执行完成，走向 {branch_name} 分支")
            self._log_step_execution(index, "if", start_time, result)
            return result
            
        except Exception as e:
            logger.error(f"[Step {index+1}] if 条件执行出错: {str(e)}")
            result = StepResult(success=False, message=f"if 执行出错: {str(e)}")
            self._log_step_execution(index, "if", start_time, result)
            return result

    def _execute_loop_step(self, index: int, step_config: Dict[str, Any], browser: BrowserAdapter) -> StepResult:
        """执行循环控制步骤"""
        loop_type = step_config.get("loop_type", "count")
        loop_value = step_config.get("value")
        loop_steps = step_config.get("steps", [])
        item_key = step_config.get("item_key", "item")
        index_key = step_config.get("index_key", "index")
        
        logger.info(f"[Step {index+1}] 执行 loop 循环: type={loop_type}")
        start_time = datetime.now()
        
        try:
            items = []
            if loop_type == "count":
                try:
                    count_str = self._context.render(str(loop_value))
                    count = int(count_str)
                    items = list(range(count))
                except (ValueError, TypeError):
                    raise FlowAbortError(f"无效的循环次数: {loop_value}")
            elif loop_type == "each":
                # 获取渲染后的列表
                raw_list = self._context.render(loop_value)
                if isinstance(raw_list, list):
                    items = raw_list
                else:
                    raise FlowAbortError(f"循环变量不是一个可迭代列表: {loop_value}")
            else:
                raise FlowAbortError(f"未知的循环类型: {loop_type}")
                
            logger.info(f"[Step {index+1}] 循环开始，共 {len(items)} 次迭代")
            
            for idx, item in enumerate(items):
                # 更新上下文变量
                self._context.set(index_key, idx)
                if loop_type == "each":
                    self._context.set(item_key, item)
                    logger.info(f"[Step {index+1}] 迭代 #{idx+1}/{len(items)}: {item_key}={item}")
                else:
                    logger.info(f"[Step {index+1}] 迭代 #{idx+1}/{len(items)}")
                
                # 执行循环体步骤
                success = self._execute_step_list(loop_steps, browser)
                if not success:
                    result = StepResult(success=False, message=f"loop 迭代 #{idx+1} 执行失败")
                    self._log_step_execution(index, "loop", start_time, result)
                    return result
                    
            result = StepResult(success=True, message=f"loop 循环执行成功，共完成 {len(items)} 次迭代")
            self._log_step_execution(index, "loop", start_time, result)
            return result
            
        except Exception as e:
            logger.error(f"[Step {index+1}] loop 循环执行出错: {str(e)}")
            result = StepResult(success=False, message=f"loop 执行出错: {str(e)}")
            self._log_step_execution(index, "loop", start_time, result)
            return result
    
    def _handle_failure(
        self, 
        index: int, 
        step_type: str, 
        on_fail: str, 
        error_msg: str
    ) -> Optional[StepResult]:
        """
        处理 Step 执行失败
        
        Args:
            index: Step 索引
            step_type: Step 类型
            on_fail: 失败策略
            error_msg: 错误信息
        
        Returns:
            StepResult 或 None
        """
        if on_fail == "skip":
            logger.info(f"[Step {index+1}] 按策略跳过")
            return None
        elif on_fail == "abort" or on_fail == "retry":
            # 如果是 retry 策略，在此处已耗尽重试次数，仍作为 abort 中止处理
            raise FlowAbortError(f"Step {index+1} ({step_type}) 失败: {error_msg}")
        else:
            raise FlowAbortError(f"Step {index+1} ({step_type}) 失败: {error_msg}")
    
    def _log_step_execution(
        self,
        index: int,
        step_type: str,
        start_time: datetime,
        result: StepResult,
        screenshot: Optional[str] = None
    ) -> None:
        """记录 Step 执行日志"""
        end_time = datetime.now()
        log_entry = {
            "step_index": index,
            "step_type": step_type,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_ms": (end_time - start_time).total_seconds() * 1000,
            "success": result.success,
            "message": result.message,
            "screenshot": screenshot
        }
        self._execution_log.append(log_entry)
        if self.log_callback:
            try:
                self.log_callback({
                    "type": "step_end",
                    "data": log_entry
                })
            except Exception:
                pass
    
    def close(self) -> None:
        """关闭引擎，释放资源"""
        if self._owns_browser and self._browser is not None:
            self._browser.close()
            self._browser = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
