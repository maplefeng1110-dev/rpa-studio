/**
 * 执行状态管理 Slice
 */
import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { ExecutionLogEntry } from '../types/flow';

type ExecutionStatus = 'idle' | 'running' | 'paused' | 'success' | 'error';

interface ExecutionState {
  status: ExecutionStatus;
  logs: ExecutionLogEntry[];
  rawLogs: string[];
  currentStepIndex: number | null;
  error: string | null;
  result: {
    success: boolean;
    executedSteps: number;
    totalSteps: number;
    context: Record<string, unknown>;
  } | null;
}

const initialState: ExecutionState = {
  status: 'idle',
  logs: [],
  rawLogs: [],
  currentStepIndex: null,
  error: null,
  result: null,
};

const executionSlice = createSlice({
  name: 'execution',
  initialState,
  reducers: {
    // 开始执行
    startExecution: (state) => {
      state.status = 'running';
      state.logs = [];
      state.rawLogs = [];
      state.currentStepIndex = null;
      state.error = null;
      state.result = null;
    },

    // 暂停执行
    pauseExecution: (state) => {
      state.status = 'paused';
    },

    // 恢复执行
    resumeExecution: (state) => {
      state.status = 'running';
    },

    // 添加执行日志
    addExecutionLog: (state, action: PayloadAction<ExecutionLogEntry>) => {
      state.logs.push(action.payload);
      state.currentStepIndex = action.payload.step_index;
    },

    // 添加原始日志
    addRawLog: (state, action: PayloadAction<string>) => {
      state.rawLogs.push(action.payload);
    },

    // 执行成功
    executionSuccess: (
      state,
      action: PayloadAction<{
        executedSteps: number;
        totalSteps: number;
        context: Record<string, unknown>;
      }>
    ) => {
      state.status = 'success';
      state.result = {
        success: true,
        ...action.payload,
      };
    },

    // 执行失败
    executionError: (state, action: PayloadAction<string>) => {
      state.status = 'error';
      state.error = action.payload;
      state.result = {
        success: false,
        executedSteps: state.currentStepIndex ?? 0,
        totalSteps: state.logs.length,
        context: {},
      };
    },

    // 停止执行
    stopExecution: (state) => {
      state.status = 'idle';
      state.currentStepIndex = null;
    },

    // 重置状态
    resetExecution: () => initialState,
  },
});

export const {
  startExecution,
  pauseExecution,
  resumeExecution,
  addExecutionLog,
  addRawLog,
  executionSuccess,
  executionError,
  stopExecution,
  resetExecution,
} = executionSlice.actions;

export default executionSlice.reducer;
