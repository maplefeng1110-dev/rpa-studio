/**
 * IPC 通道定义
 * 用于 Electron 主进程与渲染进程之间的通信
 */

// Python 进程管理
export const PYTHON_CHANNELS = {
  START: 'python:start',
  STOP: 'python:stop',
  STATUS: 'python:status',
  LOG: 'python:log',
} as const;

// Flow 管理
export const FLOW_CHANNELS = {
  SAVE: 'flow:save',
  LOAD: 'flow:load',
  LIST: 'flow:list',
  DELETE: 'flow:delete',
  EXPORT: 'flow:export',
  IMPORT: 'flow:import',
} as const;

// 执行管理
export const EXECUTION_CHANNELS = {
  START: 'execution:start',
  STOP: 'execution:stop',
  STATUS: 'execution:status',
  LOG: 'execution:log',
} as const;

// 所有通道类型
export type IpcChannel =
  | typeof PYTHON_CHANNELS[keyof typeof PYTHON_CHANNELS]
  | typeof FLOW_CHANNELS[keyof typeof FLOW_CHANNELS]
  | typeof EXECUTION_CHANNELS[keyof typeof EXECUTION_CHANNELS];
