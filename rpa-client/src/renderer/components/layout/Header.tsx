/**
 * Header 组件
 */
import React from 'react';
import { useDispatch, useSelector } from 'react-redux';
import type { RootState, AppDispatch } from '../../store';
import { createFlow, clearDirty } from '../../store/flowSlice';
import { Button } from '../common/Button';
import { useIpc } from '../../hooks/useIpc';
import { useExecution } from '../../hooks/useExecution';

interface HeaderProps {}

export const Header: React.FC<HeaderProps> = () => {
  const dispatch = useDispatch<AppDispatch>();
  const { flow, python } = useIpc();
  const { executeFlow, status, pause, resume, stop } = useExecution();
  const currentFlow = useSelector((state: RootState) => state.flow.currentFlow);
  const isDirty = useSelector((state: RootState) => state.flow.isDirty);

  const handleNewFlow = () => {
    dispatch(createFlow('新流程'));
  };

  const handleSave = async () => {
    if (currentFlow) {
      const result = await flow.save(currentFlow);
      if (result.success) {
        dispatch(clearDirty());
      }
    }
  };

  const handleExecute = () => {
    if (currentFlow) {
      executeFlow(currentFlow);
    }
  };

  return (
    <header className="h-14 bg-white border-b border-gray-200 px-4 flex items-center justify-between shadow-sm">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🤖</span>
          <h1 className="text-lg font-semibold text-gray-800">RPA Client</h1>
        </div>
        <div className="h-6 w-px bg-gray-300" />
        {currentFlow && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">{currentFlow.name}</span>
            {isDirty && <span className="text-xs text-orange-500">● 未保存</span>}
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        {/* Python 状态 */}
        <div className="flex items-center gap-2 mr-4">
          <div
            className={`w-2 h-2 rounded-full ${
              python.status.running ? 'bg-green-500' : 'bg-red-500'
            }`}
          />
          <span className="text-xs text-gray-500">
            Python {python.status.running ? '运行中' : '未启动'}
          </span>
        </div>

        {/* 操作按钮 */}
        {/* 操作按钮 */}
        <Button variant="secondary" onClick={handleNewFlow} disabled={status === 'running' || status === 'paused'}>
          新建
        </Button>
        <Button variant="secondary" onClick={handleSave} disabled={!currentFlow || !isDirty || status === 'running' || status === 'paused'}>
          保存
        </Button>
        
        {status === 'running' && (
          <Button variant="secondary" onClick={pause}>
            暂停
          </Button>
        )}
        
        {status === 'paused' && (
          <Button variant="primary" onClick={resume}>
            恢复
          </Button>
        )}
        
        {(status === 'running' || status === 'paused') && (
          <Button variant="danger" onClick={stop}>
            停止
          </Button>
        )}

        {status !== 'running' && status !== 'paused' && (
          <Button
            variant="primary"
            onClick={handleExecute}
            disabled={!currentFlow || currentFlow.steps.length === 0}
          >
            执行
          </Button>
        )}
      </div>
    </header>
  );
};
