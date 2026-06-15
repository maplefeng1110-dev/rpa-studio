/**
 * Electron Preload 脚本
 * 安全地暴露 IPC 接口给渲染进程
 */
import { contextBridge, ipcRenderer } from 'electron';
import type {
  FlowDefinition,
} from '../renderer/types/flow';

// 暴露给渲染进程的 API
const api = {
  // Python 进程管理
  python: {
    start: () => ipcRenderer.invoke('python:start'),
    stop: () => ipcRenderer.invoke('python:stop'),
    getStatus: () => ipcRenderer.invoke('python:status'),
    getToken: () => ipcRenderer.invoke('python:token'),
    onLog: (callback: (log: string) => void) => {
      ipcRenderer.on('python:log', (_event, log) => callback(log));
    },
  },

  // Flow 管理
  flow: {
    save: (flow: FlowDefinition) => ipcRenderer.invoke('flow:save', flow),
    load: (id: string) => ipcRenderer.invoke('flow:load', id),
    list: () => ipcRenderer.invoke('flow:list'),
    delete: (id: string) => ipcRenderer.invoke('flow:delete', id),
    export: (flow: FlowDefinition, path: string) =>
      ipcRenderer.invoke('flow:export', flow, path),
    import: (path: string) => ipcRenderer.invoke('flow:import', path),
  },

  // 执行管理
  execution: {
    start: (flow: FlowDefinition, context?: Record<string, unknown>) =>
      ipcRenderer.invoke('execution:start', flow, context),
    stop: () => ipcRenderer.invoke('execution:stop'),
    getStatus: () => ipcRenderer.invoke('execution:status'),
    onLog: (callback: (log: string) => void) => {
      ipcRenderer.on('execution:log', (_event, log) => callback(log));
    },
  },

  // HTTP API（直接调用 Python 后端）
  api: {
    health: () => ipcRenderer.invoke('api:health'),
    execute: (flow: FlowDefinition, context?: Record<string, unknown>) =>
      ipcRenderer.invoke('api:execute', flow, context),
    validate: (flow: FlowDefinition) => ipcRenderer.invoke('api:validate', flow),
    getStepTypes: () => ipcRenderer.invoke('api:step-types'),
    pickElementStart: () => ipcRenderer.invoke('api:pick-element-start'),
    pickElementResult: () => ipcRenderer.invoke('api:pick-element-result'),
    secretsList: () => ipcRenderer.invoke('api:secrets-list'),
    secretsSet: (name: string, value: string) => ipcRenderer.invoke('api:secrets-set', name, value),
    secretsDelete: (name: string) => ipcRenderer.invoke('api:secrets-delete', name),
    generateFlow: (instruction: string, urlHint?: string) =>
      ipcRenderer.invoke('api:flow-generate', instruction, urlHint),
    aiConfigGet: () => ipcRenderer.invoke('api:ai-config-get'),
    aiConfigSet: (cfg: Record<string, unknown>) => ipcRenderer.invoke('api:ai-config-set', cfg),
    aiConfigTest: () => ipcRenderer.invoke('api:ai-config-test'),
  },
};

// 类型定义
export type ElectronAPI = typeof api;

// 暴露 API
contextBridge.exposeInMainWorld('electronAPI', api);
