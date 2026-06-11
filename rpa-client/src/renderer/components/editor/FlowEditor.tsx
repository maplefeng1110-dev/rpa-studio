import React from 'react';
import { useDispatch, useSelector } from 'react-redux';
import type { RootState, AppDispatch } from '../../store';
import { selectStep, moveStep, addStep } from '../../store/flowSlice';
import { STEP_TYPE_METAS, type StepConfig } from '../../types/flow';
import { Button } from '../common/Button';

interface FlowEditorProps {}

export const FlowEditor: React.FC<FlowEditorProps> = () => {
  const dispatch = useDispatch<AppDispatch>();
  const currentFlow = useSelector((state: RootState) => state.flow.currentFlow);
  const selectedStepId = useSelector((state: RootState) => state.flow.selectedStepId);

  if (!currentFlow) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="text-6xl mb-4">🚀</div>
          <h2 className="text-xl font-semibold text-gray-700 mb-2">欢迎使用 RPA Client</h2>
          <p className="text-gray-500 mb-6">点击"新建"创建你的第一个流程</p>
        </div>
      </div>
    );
  }

  // 递归统计总步骤数
  const countAllSteps = (steps: StepConfig[]): number => {
    let count = 0;
    for (const s of steps) {
      count++;
      if (s.type === 'if') {
        count += countAllSteps(s.then || []);
        count += countAllSteps(s.else || []);
      } else if (s.type === 'loop') {
        count += countAllSteps(s.steps || []);
      }
    }
    return count;
  };

  // 递归渲染步骤列表
  const renderSteps = (steps: StepConfig[], depth = 0): React.ReactNode => {
    return (
      <div className="space-y-3 w-full">
        {steps.map((step, index) => {
          const meta = STEP_TYPE_METAS[step.type];
          const isSelected = selectedStepId === step.id;

          return (
            <div key={step.id} className="space-y-2">
              <div
                onClick={(e) => {
                  e.stopPropagation();
                  dispatch(selectStep(step.id));
                }}
                className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                  isSelected
                    ? 'border-blue-500 bg-blue-50 shadow-md'
                    : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm'
                }`}
              >
                <div className="flex items-center gap-4">
                  {/* 序号 */}
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center text-sm font-medium text-gray-600">
                    {index + 1}
                  </div>

                  {/* 图标 */}
                  <div className="flex-shrink-0 text-3xl">{meta?.icon || '⚙️'}</div>

                  {/* 内容 */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-800">{meta?.name || '未知步骤'}</span>
                      {step.on_fail === 'retry' && (
                        <span className="text-xs bg-yellow-100 text-yellow-800 px-1.5 py-0.5 rounded font-normal">
                          🔄 重试 (最多 {step.max_retries || 3} 次)
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-gray-500 truncate mt-1">
                      {step.type === 'open' && `打开: ${step.value || '未配置'}`}
                      {step.type === 'click' && `点击: ${step.selector || '未配置'}`}
                      {step.type === 'input' && `向 [${step.selector || '未配置'}] 输入: ${step.value || '空'}`}
                      {step.type === 'wait' && `等待: ${step.value || '0'} 秒`}
                      {step.type === 'extract' && `提取: ${step.selector || '未配置'} -> 变量 [${step.context_key || step.save_path || 'result'}]`}
                      {step.type === 'if' && `判断条件: ${step.condition || '未配置'}`}
                      {step.type === 'loop' && `循环: ${step.loop_type === 'count' ? `次数 ${step.value || 0}` : `遍历 ${step.value || '空'}`} (当前项: ${step.item_key || 'item'})`}
                    </div>
                  </div>

                  {/* 操作按钮 */}
                  <div className="flex-shrink-0 flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        dispatch(moveStep({ id: step.id, direction: 'up' }));
                      }}
                      disabled={index === 0}
                    >
                      ↑
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        dispatch(moveStep({ id: step.id, direction: 'down' }));
                      }}
                      disabled={index === steps.length - 1}
                    >
                      ↓
                    </Button>
                  </div>
                </div>
              </div>

              {/* IF 条件分支嵌套 */}
              {step.type === 'if' && (
                <div className="ml-8 space-y-4 border-l-2 border-dashed border-orange-300 pl-4 py-1">
                  <div>
                    <div className="text-xs font-semibold text-orange-600 mb-2 flex items-center justify-between">
                      <span>THEN 分支 (当条件满足时)</span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          dispatch(addStep({ type: 'click', parentId: step.id, branch: 'then' }));
                        }}
                        className="text-xs text-blue-600 hover:text-blue-800 hover:underline flex items-center gap-1"
                      >
                        + 在此分支添加步骤
                      </button>
                    </div>
                    {step.then && step.then.length > 0 ? (
                      renderSteps(step.then, depth + 1)
                    ) : (
                      <div className="text-xs text-gray-400 py-3 bg-orange-50/30 rounded text-center border border-dashed border-orange-100">
                        分支内暂无步骤，点击上方链接添加
                      </div>
                    )}
                  </div>

                  <div>
                    <div className="text-xs font-semibold text-orange-600 mb-2 flex items-center justify-between">
                      <span>ELSE 分支 (当条件不满足时)</span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          dispatch(addStep({ type: 'click', parentId: step.id, branch: 'else' }));
                        }}
                        className="text-xs text-blue-600 hover:text-blue-800 hover:underline flex items-center gap-1"
                      >
                        + 在此分支添加步骤
                      </button>
                    </div>
                    {step.else && step.else.length > 0 ? (
                      renderSteps(step.else, depth + 1)
                    ) : (
                      <div className="text-xs text-gray-400 py-3 bg-orange-50/30 rounded text-center border border-dashed border-orange-100">
                        分支内暂无步骤，点击上方链接添加
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* LOOP 循环体嵌套 */}
              {step.type === 'loop' && (
                <div className="ml-8 space-y-2 border-l-2 border-dashed border-indigo-300 pl-4 py-1">
                  <div className="text-xs font-semibold text-indigo-600 mb-2 flex items-center justify-between">
                    <span>循环体 (重复执行的内容)</span>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        dispatch(addStep({ type: 'click', parentId: step.id, branch: 'steps' }));
                      }}
                      className="text-xs text-blue-600 hover:text-blue-800 hover:underline flex items-center gap-1"
                    >
                      + 在此循环添加步骤
                    </button>
                  </div>
                  {step.steps && step.steps.length > 0 ? (
                    renderSteps(step.steps, depth + 1)
                  ) : (
                    <div className="text-xs text-gray-400 py-3 bg-indigo-50/30 rounded text-center border border-dashed border-indigo-100">
                      循环体暂无步骤，点击上方链接添加
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* 流程信息 */}
      <div className="p-4 bg-white border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-800">{currentFlow.name}</h2>
            <p className="text-sm text-gray-500">
              {currentFlow.description || '暂无描述'}
            </p>
          </div>
          <div className="text-sm text-gray-500 font-medium">
            共计 {countAllSteps(currentFlow.steps)} 个步骤
          </div>
        </div>
      </div>

      {/* 步骤列表 */}
      <div className="flex-1 overflow-y-auto p-4">
        {currentFlow.steps.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <div className="text-4xl mb-2">📋</div>
            <p>从左侧添加步骤开始</p>
          </div>
        ) : (
          renderSteps(currentFlow.steps, 0)
        )}
      </div>
    </div>
  );
};
