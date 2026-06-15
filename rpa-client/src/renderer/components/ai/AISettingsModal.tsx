/**
 * AI 设置弹窗（个人版：用户自配 API）
 * 填 API key / API 地址(base_url) / 模型 / 是否开启执行时的视觉兜底。
 * key 加密存储、绝不回读；保存后测试连接。
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Button } from '../common/Button';
import { useIpc } from '../../hooks/useIpc';

interface AISettingsModalProps {
  onClose: () => void;
}

export const AISettingsModal: React.FC<AISettingsModalProps> = ({ onClose }) => {
  const { api } = useIpc();
  const [hasKey, setHasKey] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [model, setModel] = useState('claude-opus-4-8');
  const [fallback, setFallback] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(async () => {
    const c = await api.aiConfigGet();
    if (c && !c.error) {
      setHasKey(!!c.has_key);
      setBaseUrl(c.base_url || '');
      setModel(c.model || 'claude-opus-4-8');
      setFallback(!!c.fallback_enabled);
    }
  }, [api]);

  useEffect(() => {
    load();
  }, [load]);

  const save = async (extra?: Record<string, unknown>) => {
    setBusy(true);
    setMsg(null);
    const payload: Record<string, unknown> = {
      base_url: baseUrl,
      model: model || 'claude-opus-4-8',
      fallback_enabled: fallback,
      ...extra,
    };
    if (apiKey.trim()) payload.api_key = apiKey.trim();
    const res = await api.aiConfigSet(payload);
    setBusy(false);
    if (res && !res.error) {
      setApiKey('');
      await load();
      return true;
    }
    setMsg({ ok: false, text: res?.error || '保存失败' });
    return false;
  };

  const handleSaveAndTest = async () => {
    const ok = await save();
    if (!ok) return;
    setBusy(true);
    const t = await api.aiConfigTest();
    setBusy(false);
    setMsg({ ok: !!t?.success, text: t?.message || (t?.success ? '连接成功' : '连接失败') });
  };

  const handleClearKey = async () => {
    if (!confirm('确定清除已保存的 API key？')) return;
    await save({ clear_key: true, api_key: undefined });
    setMsg({ ok: true, text: 'API key 已清除' });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-[540px] flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="px-5 py-3 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-800">⚙️ AI 设置</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-xl leading-none">×</button>
        </div>

        <div className="px-5 py-4 space-y-3">
          <p className="text-xs text-gray-500">
            AI 是可选的。要用「✨ AI 生成流程」和「执行时视觉兜底」，在这里填你自己的 API。
            key 加密存储、不会回显。
          </p>

          <label className="block text-sm text-gray-700">
            API Key {hasKey && <span className="text-xs text-green-600">（已配置，留空则不修改）</span>}
            <input
              className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              type="password"
              placeholder={hasKey ? '••••••••（已保存）' : 'sk-ant-...'}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </label>

          <label className="block text-sm text-gray-700">
            API 地址（可选，base_url）
            <input
              className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="默认官方；可填代理 / 自托管地址"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
            />
          </label>

          <label className="block text-sm text-gray-700">
            模型
            <input
              className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="claude-opus-4-8"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            />
          </label>

          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input type="checkbox" checked={fallback} onChange={(e) => setFallback(e.target.checked)} />
            执行时开启 AI 视觉兜底（DOM 选择器全失效时用截图定位）
          </label>

          {msg && (
            <div className={`text-xs ${msg.ok ? 'text-green-600' : 'text-red-500'} break-all`}>{msg.text}</div>
          )}
        </div>

        <div className="px-5 py-3 border-t border-gray-100 flex justify-between items-center">
          <button
            onClick={handleClearKey}
            disabled={!hasKey || busy}
            className="text-xs text-red-500 hover:text-red-700 disabled:opacity-40"
          >
            清除 key
          </button>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={onClose}>取消</Button>
            <Button variant="secondary" onClick={() => save()} disabled={busy}>保存</Button>
            <Button variant="primary" onClick={handleSaveAndTest} disabled={busy}>
              {busy ? '处理中…' : '保存并测试'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
