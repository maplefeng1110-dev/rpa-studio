/**
 * IPC 处理器注册
 * 防止重复注册（macOS activate 事件可能触发多次）
 */
import { BrowserWindow, ipcMain } from 'electron';
import { registerFlowHandlers } from './flowHandlers';
import { registerPythonHandlers } from './pythonHandlers';

// 所有需要注册的 IPC 通道名称（用于清理旧的处理器）
const IPC_CHANNELS = [
  'flow:save', 'flow:load', 'flow:list', 'flow:delete', 'flow:export', 'flow:import',
  'python:start', 'python:stop', 'python:status', 'python:token',
  'api:health', 'api:execute', 'api:validate', 'api:step-types',
  'api:pick-element-start', 'api:pick-element-result',
  'api:secrets-list', 'api:secrets-set', 'api:secrets-delete',
  'api:flow-generate',
  'api:ai-config-get', 'api:ai-config-set', 'api:ai-config-test',
];

export function registerIpcHandlers(mainWindow: BrowserWindow | null): void {
  // 先移除所有旧的 handle 处理器，防止重复注册导致崩溃
  for (const channel of IPC_CHANNELS) {
    try {
      ipcMain.removeHandler(channel);
    } catch {
      // 忽略不存在的处理器
    }
  }

  registerFlowHandlers();
  registerPythonHandlers(mainWindow);
}
