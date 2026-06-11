/**
 * IPC Hook
 * 封装与 Electron 主进程的通信
 * 如果在浏览器环境中运行，则直接调用 HTTP API
 */
import { useCallback, useEffect, useState } from 'react';
import type { FlowDefinition } from '../types/flow';

const PYTHON_API_URL = 'http://127.0.0.1:8765';

// 检查是否在 Electron 环境中
const hasElectronAPI = typeof window !== 'undefined' && !!(window as any).electronAPI;

// 直接 HTTP API 调用（备用方案）
async function httpRequest(path: string, options?: RequestInit): Promise<any> {
  const response = await fetch(`${PYTHON_API_URL}${path}`, options);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

export function useIpc() {
  const [pythonStatus, setPythonStatus] = useState<{ running: boolean; logs: string[] }>({
    running: true, // 假设已手动启动
    logs: [],
  });

  // 检查并获取 Python 状态
  const refreshPythonStatus = useCallback(async () => {
    if (hasElectronAPI) {
      try {
        const status = await (window as any).electronAPI.python.getStatus();
        setPythonStatus(status);
      } catch {
        // 忽略错误
      }
    } else {
      // 直接检查 HTTP
      try {
        await httpRequest('/health');
        setPythonStatus({ running: true, logs: [] });
      } catch {
        setPythonStatus({ running: false, logs: [] });
      }
    }
  }, []);

  // 启动 Python
  const startPython = useCallback(async () => {
    if (hasElectronAPI) {
      const result = await (window as any).electronAPI.python.start();
      await refreshPythonStatus();
      return result;
    }
    return { success: false };
  }, [refreshPythonStatus]);

  // 停止 Python
  const stopPython = useCallback(async () => {
    if (hasElectronAPI) {
      await (window as any).electronAPI.python.stop();
      await refreshPythonStatus();
    }
  }, [refreshPythonStatus]);

  // Flow 操作
  const saveFlow = useCallback(async (flow: FlowDefinition) => {
    if (hasElectronAPI) {
      return await (window as any).electronAPI.flow.save(flow);
    }
    return { success: false, error: 'API not available' };
  }, []);

  const loadFlow = useCallback(async (id: string) => {
    if (hasElectronAPI) {
      return await (window as any).electronAPI.flow.load(id);
    }
    return { success: false, error: 'API not available' };
  }, []);

  const listFlows = useCallback(async () => {
    if (hasElectronAPI) {
      return await (window as any).electronAPI.flow.list();
    }
    return { success: false, flows: [], error: 'API not available' };
  }, []);

  const deleteFlow = useCallback(async (id: string) => {
    if (hasElectronAPI) {
      return await (window as any).electronAPI.flow.delete(id);
    }
    return { success: false, error: 'API not available' };
  }, []);

  const exportFlow = useCallback(async (flow: FlowDefinition) => {
    if (hasElectronAPI) {
      return await (window as any).electronAPI.flow.export(flow);
    }
    return { success: false, error: 'API not available' };
  }, []);

  const importFlow = useCallback(async () => {
    if (hasElectronAPI) {
      return await (window as any).electronAPI.flow.import();
    }
    return { success: false, error: 'API not available' };
  }, []);

  // API 操作
  const apiHealth = useCallback(async () => {
    if (hasElectronAPI) {
      return await (window as any).electronAPI.api.health();
    }
    try {
      const data = await httpRequest('/health');
      return { success: true, ...data };
    } catch (err) {
      return { success: false, error: (err as Error).message };
    }
  }, []);

  const apiExecute = useCallback(
    async (flow: FlowDefinition, context?: Record<string, unknown>) => {
      if (hasElectronAPI) {
        return await (window as any).electronAPI.api.execute(flow, context);
      }
      try {
        const data = await httpRequest('/execute', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ flow, initial_context: context || {} }),
        });
        return { success: true, result: data };
      } catch (err) {
        return { success: false, error: (err as Error).message };
      }
    },
    []
  );

  const apiValidate = useCallback(async (flow: FlowDefinition) => {
    if (hasElectronAPI) {
      return await (window as any).electronAPI.api.validate(flow);
    }
    try {
      const data = await httpRequest('/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(flow),
      });
      return { success: true, ...data };
    } catch (err) {
      return { success: false, error: (err as Error).message };
    }
  }, []);

  const apiGetStepTypes = useCallback(async () => {
    if (hasElectronAPI) {
      return await (window as any).electronAPI.api.getStepTypes();
    }
    try {
      const data = await httpRequest('/step-types');
      return { success: true, ...data };
    } catch (err) {
      return { success: false, error: (err as Error).message };
    }
  }, []);

  const apiPickElementStart = useCallback(async () => {
    if (hasElectronAPI) {
      return await (window as any).electronAPI.api.pickElementStart();
    }
    try {
      const data = await httpRequest('/pick-element/start', {
        method: 'POST',
      });
      return { success: true, ...data };
    } catch (err) {
      return { success: false, error: (err as Error).message };
    }
  }, []);

  const apiPickElementResult = useCallback(async () => {
    if (hasElectronAPI) {
      return await (window as any).electronAPI.api.pickElementResult();
    }
    try {
      const data = await httpRequest('/pick-element/result');
      return { success: true, ...data };
    } catch (err) {
      return { success: false, error: (err as Error).message };
    }
  }, []);

  // 获取 Python Token
  const getTokenPython = useCallback(async () => {
    if (hasElectronAPI) {
      return await (window as any).electronAPI.python.getToken();
    }
    return '';
  }, []);

  // 凭据保险库
  const secretsList = useCallback(async () => {
    if (hasElectronAPI) {
      return await (window as any).electronAPI.api.secretsList();
    }
    return httpRequest('/secrets');
  }, []);
  const secretsSet = useCallback(async (name: string, value: string) => {
    if (hasElectronAPI) {
      return await (window as any).electronAPI.api.secretsSet(name, value);
    }
    return { success: false, error: 'API not available' };
  }, []);
  const secretsDelete = useCallback(async (name: string) => {
    if (hasElectronAPI) {
      return await (window as any).electronAPI.api.secretsDelete(name);
    }
    return { success: false, error: 'API not available' };
  }, []);

  // 监听 Python 日志
  useEffect(() => {
    if (hasElectronAPI) {
      try {
        (window as any).electronAPI.python.onLog((log: string) => {
          setPythonStatus((prev) => ({
            ...prev,
            logs: [...prev.logs.slice(-50), log],
          }));
        });
      } catch {
        // 忽略错误
      }
    }
  }, []);

  // 初始化时获取状态，并启动定时轮询以同步运行状态
  useEffect(() => {
    refreshPythonStatus();
    const interval = setInterval(refreshPythonStatus, 2000);
    return () => clearInterval(interval);
  }, [refreshPythonStatus]);

  return {
    python: {
      status: pythonStatus,
      start: startPython,
      stop: stopPython,
      refresh: refreshPythonStatus,
      getToken: getTokenPython,
    },
    flow: {
      save: saveFlow,
      load: loadFlow,
      list: listFlows,
      delete: deleteFlow,
      export: exportFlow,
      import: importFlow,
    },
    api: {
      health: apiHealth,
      execute: apiExecute,
      validate: apiValidate,
      getStepTypes: apiGetStepTypes,
      pickElementStart: apiPickElementStart,
      pickElementResult: apiPickElementResult,
      secretsList,
      secretsSet,
      secretsDelete,
    },
  };
}
