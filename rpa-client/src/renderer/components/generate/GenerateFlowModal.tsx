/**
 * AI 生成流程弹窗
 * 输入自然语言需求（可选起始网址）→ 调用后端 LLM 生成 Flow → 载入编辑器供审阅。
 */
import React, { useState } from 'react';
import { useDispatch } from 'react-redux';
import type { AppDispatch } from '../../store';
import { setFlow } from '../../store/flowSlice';
import type { FlowDefinition } from '../../types/flow';
import { Button } from '../common/Button';
import { useIpc } from '../../hooks/useIpc';

interface GenerateFlowModalProps {
  onClose: () => void;
}

export const GenerateFlowModal: React.FC<GenerateFlowModalProps> = ({ onClose }) => {
  const dispatch = useDispatch<AppDispatch>();
  const { api } = useIpc();
  const [instruction, setInstruction] = useState('');
  const [urlHint, setUrlHint] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!instruction.trim()) {
      setError('请先描述你想要的流程');
      return;
    }
    setBusy(true);
    setError(null);
    const res = await api.generateFlow(instruction.trim(), urlHint.trim() || undefined);
    setBusy(false);
    if (res?.success && res.flow) {
      // 赋新 id/时间戳，作为一个新流程载入编辑器
      const now = new Date().toISOString();
      const flow: FlowDefinition = {
        ...res.flow,
        id: `flow_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        steps: ensureStepIds(res.flow.steps || []),
        createdAt: now,
        updatedAt: now,
      };
      dispatch(setFlow(flow));
      onClose();
    } else {
      const errs = (res?.errors || []).join('；');
      setError(res?.error ? `${res.error}${errs ? '：' + errs : ''}` : '生成失败');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-[560px] max-h-[85vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="px-5 py-3 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-800">✨ AI 生成流程</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-xl leading-none">×</button>
        </div>

        <div className="px-5 py-4 space-y-3">
          <p className="text-xs text-gray-500">
            用自然语言描述你要自动化的流程，AI 会生成可编辑的步骤。生成后请检查选择器是否正确。
          </p>
          <textarea
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows={5}
            placeholder="例如：打开百度，搜索『RPA 自动化』，提取第一条结果的标题并保存到文件"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
          />
          <input
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="起始网址（可选），如 https://www.baidu.com"
            value={urlHint}
            onChange={(e) => setUrlHint(e.target.value)}
          />
          {error && <div className="text-xs text-red-500 break-all">{error}</div>}
        </div>

        <div className="px-5 py-3 border-t border-gray-100 flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>取消</Button>
          <Button variant="primary" onClick={handleGenerate} disabled={busy}>
            {busy ? '生成中…' : '生成'}
          </Button>
        </div>
      </div>
    </div>
  );
};

// 给生成的步骤（含嵌套 if/loop）补上前端需要的唯一 id
function ensureStepIds(steps: any[]): any[] {
  return (steps || []).map((s) => {
    const step = { ...s, id: s.id || `step_${Date.now()}_${Math.random().toString(36).substr(2, 9)}` };
    if (Array.isArray(step.then)) step.then = ensureStepIds(step.then);
    if (Array.isArray(step.else)) step.else = ensureStepIds(step.else);
    if (Array.isArray(step.steps)) step.steps = ensureStepIds(step.steps);
    return step;
  });
}
