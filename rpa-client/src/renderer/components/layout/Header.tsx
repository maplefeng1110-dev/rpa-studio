/**
 * Header 组件
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import type { RootState, AppDispatch } from '../../store';
import type { FlowDefinition } from '../../types/flow';
import { createFlow, clearDirty, setFlow, setFlows } from '../../store/flowSlice';
import { Button } from '../common/Button';
import { SecretsModal } from '../secrets/SecretsModal';
import { useIpc } from '../../hooks/useIpc';
import { useExecution } from '../../hooks/useExecution';

interface HeaderProps {}

export const Header: React.FC<HeaderProps> = () => {
  const dispatch = useDispatch<AppDispatch>();
  const { flow, python } = useIpc();
  const { executeFlow, status, pause, resume, stop } = useExecution();
  const currentFlow = useSelector((state: RootState) => state.flow.currentFlow);
  const isDirty = useSelector((state: RootState) => state.flow.isDirty);
  const flows = useSelector((state: RootState) => state.flow.flows);

  const [openMenu, setOpenMenu] = useState(false);
  const [secretsOpen, setSecretsOpen] = useState(false);
  const didInit = useRef(false);

  // 拉取已保存流程列表（后端按更新时间倒序返回）
  const refreshFlows = useCallback(async (): Promise<FlowDefinition[]> => {
    const res = await flow.list();
    const list: FlowDefinition[] = res?.flows || [];
    dispatch(setFlows(list));
    return list;
  }, [flow, dispatch]);

  // 启动时加载列表；若当前没有打开的流程，自动打开最近一个
  useEffect(() => {
    if (didInit.current) return;
    didInit.current = true;
    (async () => {
      const list = await refreshFlows();
      if (!currentFlow && list.length > 0) {
        const res = await flow.load(list[0].id);
        if (res?.success && res.flow) dispatch(setFlow(res.flow));
      }
    })();
  }, [refreshFlows, flow, dispatch, currentFlow]);

  const handleOpenFlow = async (id: string) => {
    const res = await flow.load(id);
    if (res?.success && res.flow) dispatch(setFlow(res.flow));
    setOpenMenu(false);
  };

  const handleToggleMenu = async () => {
    if (!openMenu) await refreshFlows();
    setOpenMenu((v) => !v);
  };

  const handleNewFlow = () => {
    dispatch(createFlow('新流程'));
  };

  const handleSave = async () => {
    if (currentFlow) {
      const result = await flow.save(currentFlow);
      if (result.success) {
        dispatch(clearDirty());
        await refreshFlows();
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

        {/* 打开已保存的流程 */}
        <div className="relative">
          <Button
            variant="secondary"
            onClick={handleToggleMenu}
            disabled={status === 'running' || status === 'paused'}
          >
            打开 ▾
          </Button>
          {openMenu && (
            <>
              {/* 点击空白处关闭 */}
              <div className="fixed inset-0 z-10" onClick={() => setOpenMenu(false)} />
              <div className="absolute right-0 mt-1 w-72 max-h-80 overflow-y-auto bg-white border border-gray-200 rounded-lg shadow-lg z-20 py-1">
                {flows.length === 0 ? (
                  <div className="px-3 py-3 text-sm text-gray-400 text-center">暂无已保存的流程</div>
                ) : (
                  flows.map((f) => (
                    <button
                      key={f.id}
                      onClick={() => handleOpenFlow(f.id)}
                      className={`w-full text-left px-3 py-2 hover:bg-blue-50 text-sm ${
                        currentFlow?.id === f.id ? 'bg-blue-50' : ''
                      }`}
                    >
                      <div className="font-medium text-gray-800 truncate">{f.name || '未命名流程'}</div>
                      <div className="text-xs text-gray-400">
                        {f.updatedAt ? new Date(f.updatedAt).toLocaleString() : ''}
                        {' · '}
                        {(f.steps?.length ?? 0)} 步
                      </div>
                    </button>
                  ))
                )}
              </div>
            </>
          )}
        </div>

        <Button variant="secondary" onClick={handleSave} disabled={!currentFlow || !isDirty || status === 'running' || status === 'paused'}>
          保存
        </Button>

        <Button variant="secondary" onClick={() => setSecretsOpen(true)}>
          🔐 凭据
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

      {secretsOpen && <SecretsModal onClose={() => setSecretsOpen(false)} />}
    </header>
  );
};
