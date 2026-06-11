/**
 * Flow 管理 IPC 处理器
 */
import { ipcMain, app, dialog } from 'electron';
import path from 'path';
import fs from 'fs/promises';
import type { FlowDefinition } from '../../renderer/types/flow';

// 获取 Flow 存储目录
function getFlowDir(): string {
  const userData = app.getPath('userData');
  const flowDir = path.join(userData, 'flows');
  return flowDir;
}

// 确保存储目录存在
async function ensureFlowDir(): Promise<string> {
  const flowDir = getFlowDir();
  try {
    await fs.access(flowDir);
  } catch {
    await fs.mkdir(flowDir, { recursive: true });
  }
  return flowDir;
}

// 获取 Flow 文件路径
function getFlowFilePath(id: string): string {
  return path.join(getFlowDir(), `${id}.json`);
}

// 注册 Flow 相关的 IPC 处理器
export function registerFlowHandlers(): void {
  // 保存 Flow
  ipcMain.handle('flow:save', async (_event, flow: FlowDefinition) => {
    try {
      const flowDir = await ensureFlowDir();
      const filePath = getFlowFilePath(flow.id);

      // 更新时间戳
      flow.updatedAt = new Date().toISOString();

      await fs.writeFile(filePath, JSON.stringify(flow, null, 2), 'utf-8');
      return { success: true, flow };
    } catch (err) {
      return { success: false, error: (err as Error).message };
    }
  });

  // 加载 Flow
  ipcMain.handle('flow:load', async (_event, id: string) => {
    try {
      const filePath = getFlowFilePath(id);
      const content = await fs.readFile(filePath, 'utf-8');
      const flow = JSON.parse(content) as FlowDefinition;
      return { success: true, flow };
    } catch (err) {
      return { success: false, error: (err as Error).message };
    }
  });

  // 列出所有 Flow
  ipcMain.handle('flow:list', async () => {
    try {
      const flowDir = await ensureFlowDir();
      const files = await fs.readdir(flowDir);
      const flows: FlowDefinition[] = [];

      for (const file of files) {
        if (file.endsWith('.json')) {
          try {
            const content = await fs.readFile(path.join(flowDir, file), 'utf-8');
            flows.push(JSON.parse(content));
          } catch {
            // 忽略无效文件
          }
        }
      }

      // 按更新时间排序
      flows.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());

      return { success: true, flows };
    } catch (err) {
      return { success: false, error: (err as Error).message, flows: [] };
    }
  });

  // 删除 Flow
  ipcMain.handle('flow:delete', async (_event, id: string) => {
    try {
      const filePath = getFlowFilePath(id);
      await fs.unlink(filePath);
      return { success: true };
    } catch (err) {
      return { success: false, error: (err as Error).message };
    }
  });

  // 导出 Flow
  ipcMain.handle('flow:export', async (_event, flow: FlowDefinition, defaultPath?: string) => {
    try {
      const result = await dialog.showSaveDialog({
        defaultPath: defaultPath || `${flow.name}.json`,
        filters: [{ name: 'JSON Files', extensions: ['json'] }],
      });

      if (result.canceled || !result.filePath) {
        return { success: false, canceled: true };
      }

      await fs.writeFile(result.filePath, JSON.stringify(flow, null, 2), 'utf-8');
      return { success: true, path: result.filePath };
    } catch (err) {
      return { success: false, error: (err as Error).message };
    }
  });

  // 导入 Flow
  ipcMain.handle('flow:import', async () => {
    try {
      const result = await dialog.showOpenDialog({
        filters: [{ name: 'JSON Files', extensions: ['json'] }],
        properties: ['openFile'],
      });

      if (result.canceled || !result.filePaths.length) {
        return { success: false, canceled: true };
      }

      const content = await fs.readFile(result.filePaths[0], 'utf-8');
      const flow = JSON.parse(content) as FlowDefinition;

      // 生成新的 ID 避免冲突
      flow.id = `flow_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      flow.createdAt = new Date().toISOString();
      flow.updatedAt = flow.createdAt;

      return { success: true, flow };
    } catch (err) {
      return { success: false, error: (err as Error).message };
    }
  });
}
