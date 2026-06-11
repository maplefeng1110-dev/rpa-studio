import React from 'react';
import { useSelector } from 'react-redux';
import type { RootState } from '../../store';

interface ExecutionLogProps {}

export const ExecutionLog: React.FC<ExecutionLogProps> = () => {
  const { logs, rawLogs, status, error } = useSelector((state: RootState) => state.execution);

  const getStatusIcon = (success: boolean) => (success ? '✓' : '✗');
  const getStatusColor = (success: boolean) =>
    success ? 'text-green-600' : 'text-red-600';

  return (
    <div className="h-full flex flex-col bg-white">
      {/* 头部控制栏 */}
      <div className="p-3 border-b border-gray-200 flex justify-between items-center bg-gray-50 flex-shrink-0">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-gray-700">运行执行控制台</h3>
        </div>
        {status !== 'idle' && (
          <span className={`text-xs px-2 py-0.5 rounded font-medium ${
            status === 'running' ? 'bg-green-100 text-green-850 animate-pulse' :
            status === 'paused' ? 'bg-yellow-100 text-yellow-850' :
            status === 'success' ? 'bg-blue-100 text-blue-850' :
            status === 'error' ? 'bg-red-100 text-red-850' : 'bg-gray-100 text-gray-800'
          }`}>
            {status === 'running' ? '● 正在执行...' :
             status === 'paused' ? '● 已暂停' :
             status === 'success' ? '✓ 执行成功' :
             status === 'error' ? '✗ 执行失败' : '空闲'}
          </span>
        )}
      </div>

      {/* 内容区域 (左右分栏) */}
      <div className="flex-1 flex gap-4 p-3 overflow-hidden min-h-0 bg-gray-50/20">
        {/* 左栏：结构化步骤运行情况 */}
        <div className="flex-1 overflow-y-auto border border-gray-200 rounded-lg p-3 bg-white flex flex-col">
          <h4 className="text-xs font-semibold text-gray-400 mb-2 uppercase tracking-wider">步骤执行报告</h4>
          
          {logs.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-400 text-sm py-8">
              {status === 'running' ? (
                <div className="text-center">
                  <div className="animate-spin inline-block w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full mb-2" />
                  <div>正在运行首个步骤...</div>
                </div>
              ) : (
                '暂无步骤报告'
              )}
            </div>
          ) : (
            <div className="space-y-2">
              {logs.map((log, index) => (
                <div
                  key={index}
                  className={`p-3 rounded-lg border text-sm transition-all ${
                    log.success ? 'bg-green-50/50 border-green-200' : 'bg-red-50/50 border-red-200'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <span className={`font-mono font-bold text-base leading-none ${getStatusColor(log.success)}`}>
                      {getStatusIcon(log.success)}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-gray-700">
                          步骤 {log.step_index + 1}
                        </span>
                        <span className="text-xs bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded font-mono">
                          {log.step_type}
                        </span>
                        <span className="text-xs text-gray-400 ml-auto font-medium">
                          {log.duration_ms.toFixed(0)}ms
                        </span>
                      </div>
                      <div className="text-gray-600 mt-1 text-xs break-all leading-relaxed">{log.message}</div>
                      {log.screenshot && (
                        <div className="text-[11px] text-gray-400 mt-1 break-all" title={log.screenshot}>
                          📷 失败截图：{log.screenshot}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 右栏：实时终端控制台 */}
        <div className="w-[480px] flex flex-col border border-gray-800 rounded-lg overflow-hidden bg-gray-950 text-gray-200 font-mono text-xs">
          <div className="p-2 bg-gray-900 border-b border-gray-800 flex items-center justify-between text-gray-400 select-none">
            <span>实时系统终端 (Logs)</span>
            <span className="text-[10px] text-gray-500">WEBSOCKET FEED</span>
          </div>
          
          <div className="flex-1 overflow-y-auto p-3 space-y-1.5 min-h-0 select-text">
            {error && (
              <div className="text-red-400 font-bold border-l-4 border-red-500 pl-2 py-1 my-1 bg-red-950/20 rounded-r">
                [SYSTEM ERROR] {error}
              </div>
            )}
            
            {rawLogs.length === 0 ? (
              <div className="text-gray-600 italic py-12 text-center select-none">
                {status === 'running' ? '建立实时数据通道中...' : '等待执行流程...'}
              </div>
            ) : (
              rawLogs.map((raw, i) => (
                <div key={i} className="whitespace-pre-wrap leading-relaxed break-all">
                  <span className="text-blue-500 select-none">&gt;</span> {raw}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
