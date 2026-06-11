/**
 * 执行 Hook
 * 封装流程执行逻辑
 */
import { useCallback, useRef } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import type { RootState, AppDispatch } from '../store';
import {
  startExecution,
  pauseExecution,
  resumeExecution,
  addExecutionLog,
  executionSuccess,
  executionError,
  stopExecution,
  resetExecution,
  addRawLog,
} from '../store/executionSlice';
import { useIpc } from './useIpc';
import type { FlowDefinition } from '../types/flow';

export function useExecution() {
  const dispatch = useDispatch<AppDispatch>();
  const { python } = useIpc();
  const socketRef = useRef<WebSocket | null>(null);

  const execution = useSelector((state: RootState) => state.execution);

  // 执行 Flow (通过 WebSocket 实时推送日志和状态)
  const executeFlow = useCallback(
    async (flow: FlowDefinition, context?: Record<string, unknown>) => {
      dispatch(startExecution());
      dispatch(addRawLog('正在建立实时执行通道...'));

      try {
        let token = await python.getToken();
        
        // 如果 Electron IPC 返回空 token，尝试从 .rpa_token 文件读取
        if (!token) {
          dispatch(addRawLog('警告: 未获取到 API Token，尝试从文件读取...'));
          try {
            // 在非 Electron 环境下，直接请求 health 不需要 token
            const healthResp = await fetch('http://127.0.0.1:8765/health');
            if (healthResp.ok) {
              dispatch(addRawLog('Python 服务运行正常，但无法获取认证令牌'));
            }
          } catch {
            dispatch(executionError('Python 后端服务未运行'));
            dispatch(addRawLog('错误: 无法连接 Python 后端'));
            return;
          }
        }

        dispatch(addRawLog(`正在连接 WebSocket (token: ${token ? token.substring(0, 8) + '...' : '空'})...`));
        const wsUrl = `ws://127.0.0.1:8765/ws/execute?token=${token}`;
        
        const ws = new WebSocket(wsUrl);
        socketRef.current = ws;

        ws.onopen = () => {
          dispatch(addRawLog('执行通道建立成功，启动流程...'));
          ws.send(
            JSON.stringify({
              action: 'start',
              flow,
              initial_context: context || {},
            })
          );
        };

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            
            if (message.type === 'step_start') {
              const { step_index, step_type } = message.data;
              dispatch(addRawLog(`[Step ${step_index + 1}] 开始执行 ${step_type} 步骤...`));
            } else if (message.type === 'step_end') {
              const logEntry = message.data;
              dispatch(addExecutionLog(logEntry));
              dispatch(
                addRawLog(
                  `[Step ${logEntry.step_index + 1}] ${logEntry.message} (${logEntry.duration_ms.toFixed(1)}ms)`
                )
              );
            } else if (message.type === 'status') {
              const { status: currentStatus, message: logMsg } = message.data;
              dispatch(addRawLog(`系统提示: ${logMsg}`));
              
              if (currentStatus === 'paused') {
                dispatch(pauseExecution());
              } else if (currentStatus === 'running') {
                dispatch(resumeExecution());
              }
            } else if (message.type === 'result') {
              const result = message.data;
              dispatch(addRawLog(`流程执行结束: success=${result.success}`));
              
              if (result.success) {
                dispatch(
                  executionSuccess({
                    executedSteps: result.executed_steps,
                    totalSteps: result.total_steps,
                    context: result.context,
                  })
                );
              } else {
                dispatch(executionError(result.error || '执行失败'));
              }
              ws.close();
            } else if (message.type === 'error') {
              dispatch(executionError(message.message));
              dispatch(addRawLog(`错误: ${message.message}`));
              ws.close();
            }
          } catch (e) {
            dispatch(addRawLog(`解析日志异常: ${(e as Error).message}`));
          }
        };

        ws.onerror = (event) => {
          console.error('WebSocket error:', event);
          dispatch(executionError('WebSocket 连接失败 (可能是 Token 不匹配或服务未运行)'));
          dispatch(addRawLog('系统错误: WebSocket 连接被拒绝，请检查 Python 服务状态'));
        };

        ws.onclose = (event) => {
          socketRef.current = null;
          if (event.code === 1008) {
            dispatch(executionError('WebSocket 认证失败: Token 无效'));
            dispatch(addRawLog('错误: API Token 认证失败，请重启应用'));
          } else if (event.code !== 1000 && event.code !== 1005) {
            dispatch(addRawLog(`WebSocket 已关闭 (code: ${event.code})`));
          }
        };

      } catch (err) {
        dispatch(executionError((err as Error).message));
        dispatch(addRawLog(`启动失败: ${(err as Error).message}`));
      }
    },
    [dispatch, python]
  );

  // 暂停执行
  const pause = useCallback(() => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ action: 'pause' }));
    }
  }, []);

  // 恢复执行
  const resume = useCallback(() => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ action: 'resume' }));
    }
  }, []);

  // 中止执行
  const stop = useCallback(() => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ action: 'stop' }));
    }
    dispatch(stopExecution());
  }, [dispatch]);

  // 重置
  const reset = useCallback(() => {
    dispatch(resetExecution());
  }, [dispatch]);

  return {
    ...execution,
    executeFlow,
    pause,
    resume,
    stop,
    reset,
  };
}
