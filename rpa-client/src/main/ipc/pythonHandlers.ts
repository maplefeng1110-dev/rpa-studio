/**
 * Python 进程管理 IPC 处理器
 */
import { ipcMain, BrowserWindow } from 'electron';
import { pythonManager } from '../python/manager';
import type { FlowDefinition, ExecutionResponse } from '../../renderer/types/flow';

// 注册 Python 相关的 IPC 处理器
export function registerPythonHandlers(mainWindow: BrowserWindow | null): void {
  // 设置日志回调
  pythonManager.setOnLogCallback((log: string) => {
    if (mainWindow) {
      mainWindow.webContents.send('python:log', log);
    }
  });

  // 启动 Python 后端
  ipcMain.handle('python:start', async () => {
    const success = await pythonManager.start();
    return { success };
  });

  // 停止 Python 后端
  ipcMain.handle('python:stop', async () => {
    await pythonManager.stop();
    return { success: true };
  });

  // 获取 Python 状态
  ipcMain.handle('python:status', () => {
    return pythonManager.getStatus();
  });

  // 获取 Python 令牌
  ipcMain.handle('python:token', () => {
    return pythonManager.getApiToken();
  });

  // ============ API 代理 ============

  // 健康检查
  ipcMain.handle('api:health', async () => {
    try {
      const response = await fetch(`${pythonManager.getApiUrl()}/health`, {
        headers: {
          'X-RPA-Token': pythonManager.getApiToken(),
        },
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return await response.json();
    } catch (err) {
      return { success: false, error: (err as Error).message };
    }
  });

  // 开始元素拾取
  ipcMain.handle('api:pick-element-start', async () => {
    try {
      const response = await fetch(`${pythonManager.getApiUrl()}/pick-element/start`, {
        method: 'POST',
        headers: {
          'X-RPA-Token': pythonManager.getApiToken(),
        },
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return await response.json();
    } catch (err) {
      return { success: false, error: (err as Error).message };
    }
  });

  // 获取元素拾取结果
  ipcMain.handle('api:pick-element-result', async () => {
    try {
      const response = await fetch(`${pythonManager.getApiUrl()}/pick-element/result`, {
        headers: {
          'X-RPA-Token': pythonManager.getApiToken(),
        },
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return await response.json();
    } catch (err) {
      return { success: false, error: (err as Error).message };
    }
  });

  // 执行 Flow
  ipcMain.handle('api:execute', async (_event, flow: FlowDefinition, context?: Record<string, unknown>) => {
    try {
      const response = await fetch(`${pythonManager.getApiUrl()}/execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-RPA-Token': pythonManager.getApiToken(),
        },
        body: JSON.stringify({
          flow,
          initial_context: context || {},
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const result = (await response.json()) as ExecutionResponse;
      return { success: true, result };
    } catch (err) {
      return { success: false, error: (err as Error).message };
    }
  });

  // 验证 Flow
  ipcMain.handle('api:validate', async (_event, flow: FlowDefinition) => {
    try {
      const response = await fetch(`${pythonManager.getApiUrl()}/validate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-RPA-Token': pythonManager.getApiToken(),
        },
        body: JSON.stringify(flow),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      return await response.json();
    } catch (err) {
      return { success: false, error: (err as Error).message };
    }
  });

  // 获取 Step 类型
  ipcMain.handle('api:step-types', async () => {
    try {
      const response = await fetch(`${pythonManager.getApiUrl()}/step-types`, {
        headers: {
          'X-RPA-Token': pythonManager.getApiToken(),
        },
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return await response.json();
    } catch (err) {
      return { success: false, error: (err as Error).message };
    }
  });

  // 凭据保险库：列出名称（不含明文）
  ipcMain.handle('api:secrets-list', async () => {
    try {
      const response = await fetch(`${pythonManager.getApiUrl()}/secrets`, {
        headers: { 'X-RPA-Token': pythonManager.getApiToken() },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (err) {
      return { success: false, error: (err as Error).message };
    }
  });

  // 凭据保险库：新增/更新
  ipcMain.handle('api:secrets-set', async (_event, name: string, value: string) => {
    try {
      const response = await fetch(`${pythonManager.getApiUrl()}/secrets`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-RPA-Token': pythonManager.getApiToken(),
        },
        body: JSON.stringify({ name, value }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (err) {
      return { success: false, error: (err as Error).message };
    }
  });

  // 凭据保险库：删除
  ipcMain.handle('api:secrets-delete', async (_event, name: string) => {
    try {
      const response = await fetch(`${pythonManager.getApiUrl()}/secrets/${encodeURIComponent(name)}`, {
        method: 'DELETE',
        headers: { 'X-RPA-Token': pythonManager.getApiToken() },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (err) {
      return { success: false, error: (err as Error).message };
    }
  });

  // 自然语言生成 Flow
  ipcMain.handle('api:flow-generate', async (_event, instruction: string, urlHint?: string) => {
    try {
      const response = await fetch(`${pythonManager.getApiUrl()}/flows/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-RPA-Token': pythonManager.getApiToken(),
        },
        body: JSON.stringify({ instruction, url_hint: urlHint || null }),
      });
      const data = (await response.json()) as { detail?: string };
      if (!response.ok) {
        return { success: false, error: data?.detail || `HTTP ${response.status}` };
      }
      return data;
    } catch (err) {
      return { success: false, error: (err as Error).message };
    }
  });
}
