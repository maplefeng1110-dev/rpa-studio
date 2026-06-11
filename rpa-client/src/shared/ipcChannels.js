"use strict";
/**
 * IPC 通道定义
 * 用于 Electron 主进程与渲染进程之间的通信
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.EXECUTION_CHANNELS = exports.FLOW_CHANNELS = exports.PYTHON_CHANNELS = void 0;
// Python 进程管理
exports.PYTHON_CHANNELS = {
    START: 'python:start',
    STOP: 'python:stop',
    STATUS: 'python:status',
    LOG: 'python:log',
};
// Flow 管理
exports.FLOW_CHANNELS = {
    SAVE: 'flow:save',
    LOAD: 'flow:load',
    LIST: 'flow:list',
    DELETE: 'flow:delete',
    EXPORT: 'flow:export',
    IMPORT: 'flow:import',
};
// 执行管理
exports.EXECUTION_CHANNELS = {
    START: 'execution:start',
    STOP: 'execution:stop',
    STATUS: 'execution:status',
    LOG: 'execution:log',
};
