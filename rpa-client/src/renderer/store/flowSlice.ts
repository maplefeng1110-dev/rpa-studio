/**
 * Flow 状态管理 Slice
 */
import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { FlowDefinition, StepConfig, StepType } from '../types/flow';
import { createDefaultFlow, createDefaultStep } from '../types/flow';

interface FlowState {
  currentFlow: FlowDefinition | null;
  selectedStepId: string | null;
  flows: FlowDefinition[];
  isDirty: boolean;
  isLoading: boolean;
  error: string | null;
}

const initialState: FlowState = {
  currentFlow: null,
  selectedStepId: null,
  flows: [],
  isDirty: false,
  isLoading: false,
  error: null,
};

// 递归寻找 Step 以及它所属的父级数组和索引
function findStepAndParent(
  steps: StepConfig[],
  id: string
): { step: StepConfig; parentArray: StepConfig[]; index: number } | null {
  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    if (step.id === id) {
      return { step, parentArray: steps, index: i };
    }
    if (step.type === 'if') {
      if (step.then) {
        const found = findStepAndParent(step.then, id);
        if (found) return found;
      }
      if (step.else) {
        const found = findStepAndParent(step.else, id);
        if (found) return found;
      }
    }
    if (step.type === 'loop' && step.steps) {
      const found = findStepAndParent(step.steps, id);
      if (found) return found;
    }
  }
  return null;
}

const flowSlice = createSlice({
  name: 'flow',
  initialState,
  reducers: {
    // 创建新 Flow
    createFlow: (state, action: PayloadAction<string>) => {
      state.currentFlow = createDefaultFlow(action.payload || '新流程');
      state.selectedStepId = null;
      state.isDirty = true;
      state.error = null;
    },

    // 设置当前 Flow
    setFlow: (state, action: PayloadAction<FlowDefinition>) => {
      state.currentFlow = action.payload;
      state.selectedStepId = null;
      state.isDirty = false;
      state.error = null;
    },

    // 更新 Flow 基本信息
    updateFlowInfo: (
      state,
      action: PayloadAction<{ name?: string; description?: string }>
    ) => {
      if (state.currentFlow) {
        state.currentFlow = {
          ...state.currentFlow,
          ...action.payload,
          updatedAt: new Date().toISOString(),
        };
        state.isDirty = true;
      }
    },

    // 添加 Step
    addStep: (
      state,
      action: PayloadAction<{
        type: StepType;
        parentId?: string;
        branch?: 'then' | 'else' | 'steps';
        index?: number;
      }>
    ) => {
      if (state.currentFlow) {
        const newStep = createDefaultStep(action.payload.type);
        const { parentId, branch, index } = action.payload;

        if (parentId && branch) {
          // 寻找指定的父级步骤
          const findParent = (steps: StepConfig[]): StepConfig | null => {
            for (const s of steps) {
              if (s.id === parentId) return s;
              if (s.type === 'if') {
                const r = findParent(s.then || []);
                if (r) return r;
                const r2 = findParent(s.else || []);
                if (r2) return r2;
              }
              if (s.type === 'loop') {
                const r = findParent(s.steps || []);
                if (r) return r;
              }
            }
            return null;
          };

          const parentStep = findParent(state.currentFlow.steps);
          if (parentStep) {
            if (!parentStep[branch]) {
              parentStep[branch] = [];
            }
            const arr = parentStep[branch] as StepConfig[];
            const idx = index ?? arr.length;
            arr.splice(idx, 0, newStep);
          }
        } else if (state.selectedStepId) {
          // 在当前选中的步骤后插入同级步骤
          const found = findStepAndParent(state.currentFlow.steps, state.selectedStepId);
          if (found) {
            found.parentArray.splice(found.index + 1, 0, newStep);
          } else {
            state.currentFlow.steps.push(newStep);
          }
        } else {
          // 直接添加到顶层末尾
          state.currentFlow.steps.push(newStep);
        }

        state.currentFlow.updatedAt = new Date().toISOString();
        state.selectedStepId = newStep.id;
        state.isDirty = true;
      }
    },

    // 删除 Step
    removeStep: (state, action: PayloadAction<string>) => {
      if (state.currentFlow) {
        const found = findStepAndParent(state.currentFlow.steps, action.payload);
        if (found) {
          found.parentArray.splice(found.index, 1);
          
          if (state.selectedStepId === action.payload) {
            state.selectedStepId = found.parentArray.length > 0 
              ? found.parentArray[Math.min(found.index, found.parentArray.length - 1)].id 
              : null;
          }
          state.currentFlow.updatedAt = new Date().toISOString();
          state.isDirty = true;
        }
      }
    },

    // 更新 Step
    updateStep: (
      state,
      action: PayloadAction<{ id: string; updates: Partial<StepConfig> }>
    ) => {
      if (state.currentFlow) {
        const found = findStepAndParent(state.currentFlow.steps, action.payload.id);
        if (found) {
          Object.assign(found.step, action.payload.updates);
          state.currentFlow.updatedAt = new Date().toISOString();
          state.isDirty = true;
        }
      }
    },

    // 移动 Step
    moveStep: (
      state,
      action: PayloadAction<{ id: string; direction: 'up' | 'down' }>
    ) => {
      if (state.currentFlow) {
        const found = findStepAndParent(state.currentFlow.steps, action.payload.id);
        if (found) {
          const { parentArray, index } = found;
          const { direction } = action.payload;
          if (direction === 'up' && index > 0) {
            const temp = parentArray[index];
            parentArray[index] = parentArray[index - 1];
            parentArray[index - 1] = temp;
            state.currentFlow.updatedAt = new Date().toISOString();
            state.isDirty = true;
          } else if (direction === 'down' && index < parentArray.length - 1) {
            const temp = parentArray[index];
            parentArray[index] = parentArray[index + 1];
            parentArray[index + 1] = temp;
            state.currentFlow.updatedAt = new Date().toISOString();
            state.isDirty = true;
          }
        }
      }
    },

    // 选中 Step
    selectStep: (state, action: PayloadAction<string | null>) => {
      state.selectedStepId = action.payload;
    },

    // 设置 Flow 列表
    setFlows: (state, action: PayloadAction<FlowDefinition[]>) => {
      state.flows = action.payload;
    },

    // 设置加载状态
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.isLoading = action.payload;
    },

    // 设置错误
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
    },

    // 清除脏标记
    clearDirty: (state) => {
      state.isDirty = false;
    },
  },
});

export const {
  createFlow,
  setFlow,
  updateFlowInfo,
  addStep,
  removeStep,
  updateStep,
  moveStep,
  selectStep,
  setFlows,
  setLoading,
  setError,
  clearDirty,
} = flowSlice.actions;

export default flowSlice.reducer;
