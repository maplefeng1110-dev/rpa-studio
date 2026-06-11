/**
 * Header 组件
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import type { RootState, AppDispatch } from '../../store';
import type { FlowDefinition } from '../../types/flow';
import { createFlow, clearDirty, setFlow, setFlows, updateFlowInfo } from '../../store/flowSlice';
import { Button } from '../common/Button';
import { SecretsModal } from '../secrets/SecretsModal';
import { GenerateFlowModal } from '../generate/GenerateFlowModal';
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
  const [generateOpen, setGenerateOpen] = useState(false);
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

  // 从文件导入（原生打开对话框；导入后赋新 id 并落盘）
  const handleImport = async () => {
    const res = await flow.import();
    if (res?.success && res.flow) {
      const saved = await flow.save(res.flow);
      if (saved?.success) {
        dispatch(setFlow(res.flow));
        await refreshFlows();
      }
    }
  };

  // 导出当前流程到文件（原生保存对话框，默认按流程名命名）
  const handleExport = async () => {
    if (currentFlow) await flow.export(currentFlow);
  };

  // 删除一个已保存流程
  const handleDeleteFlow = async (id: string, name: string) => {
    if (!confirm(`确定删除流程「${name || '未命名'}」？`)) return;
    await flow.delete(id);
    if (currentFlow?.id === id) dispatch(createFlow('新流程'));
    await refreshFlows();
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
            <input
              className="text-sm text-gray-700 font-medium bg-transparent border border-transparent hover:border-gray-300 focus:border-blue-400 focus:bg-white rounded px-1.5 py-0.5 focus:outline-none w-44"
              value={currentFlow.name}
              title="点击编辑流程名称"
              placeholder="未命名流程"
              onChange={(e) => dispatch(updateFlowInfo({ name: e.target.value }))}
            />
            {isDirty && <span className="text-xs text-orange-500 whitespace-nowrap">● 未保存</span>}
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
        <Button variant="secondary" onClick={() => setGenerateOpen(true)} disabled={status === 'running' || status === 'paused'}>
          ✨ AI 生成
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
                    <div
                      key={f.id}
                      className={`group flex items-center justify-between px-3 py-2 hover:bg-blue-50 ${
                        currentFlow?.id === f.id ? 'bg-blue-50' : ''
                      }`}
                    >
                      <button onClick={() => handleOpenFlow(f.id)} className="flex-1 text-left text-sm min-w-0">
                        <div className="font-medium text-gray-800 truncate">{f.name || '未命名流程'}</div>
                        <div className="text-xs text-gray-400">
                          {f.updatedAt ? new Date(f.updatedAt).toLocaleString() : ''}
                          {' · '}
                          {(f.steps?.length ?? 0)} 步
                        </div>
                      </button>
                      <button
                        onClick={() => handleDeleteFlow(f.id, f.name)}
                        title="删除"
                        className="ml-2 text-gray-300 hover:text-red-600 opacity-0 group-hover:opacity-100"
                      >
                        🗑
                      </button>
                    </div>
                  ))
                )}
              </div>
            </>
          )}
        </div>

        <Button variant="secondary" onClick={handleSave} disabled={!currentFlow || !isDirty || status === 'running' || status === 'paused'}>
          保存
        </Button>
        <Button variant="secondary" onClick={handleImport} disabled={status === 'running' || status === 'paused'}>
          导入
        </Button>
        <Button variant="secondary" onClick={handleExport} disabled={!currentFlow || status === 'running' || status === 'paused'}>
          导出
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
      {generateOpen && <GenerateFlowModal onClose={() => setGenerateOpen(false)} />}
    </header>
  );
};
