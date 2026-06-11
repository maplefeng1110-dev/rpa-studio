/**
 * Sidebar 组件 - Step 组件库
 */
import React from 'react';
import { useDispatch } from 'react-redux';
import type { AppDispatch } from '../../store';
import { addStep } from '../../store/flowSlice';
import { STEP_TYPE_METAS, type StepType } from '../../types/flow';

interface SidebarProps {}

export const Sidebar: React.FC<SidebarProps> = () => {
  const dispatch = useDispatch<AppDispatch>();

  const handleAddStep = (type: StepType) => {
    dispatch(addStep({ type }));
  };

  return (
    <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
      <div className="p-4 border-b border-gray-200">
        <h2 className="text-sm font-semibold text-gray-700">步骤组件</h2>
        <p className="text-xs text-gray-500 mt-1">拖拽或点击添加步骤</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {Object.values(STEP_TYPE_METAS).map((meta) => (
          <button
            key={meta.type}
            onClick={() => handleAddStep(meta.type)}
            className={`w-full p-3 rounded-lg border-2 border-gray-200 hover:border-blue-400 hover:bg-blue-50 transition-all text-left ${meta.color}`}
          >
            <div className="flex items-center gap-3">
              <span className="text-2xl">{meta.icon}</span>
              <div>
                <div className="font-medium text-gray-800">{meta.name}</div>
                <div className="text-xs text-gray-500">{meta.description}</div>
              </div>
            </div>
          </button>
        ))}
      </div>
    </aside>
  );
};
