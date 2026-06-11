/**
 * 凭据保险库管理弹窗
 * 新增/列出/删除加密凭据。明文仅在录入时存在，列表只显示名称。
 * 流程中用 {{secret:名称}} 引用。
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Button } from '../common/Button';
import { useIpc } from '../../hooks/useIpc';

interface SecretsModalProps {
  onClose: () => void;
}

interface SecretMeta {
  name: string;
  updated_at?: string;
}

export const SecretsModal: React.FC<SecretsModalProps> = ({ onClose }) => {
  const { api } = useIpc();
  const [secrets, setSecrets] = useState<SecretMeta[]>([]);
  const [name, setName] = useState('');
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const res = await api.secretsList();
    setSecrets(res?.secrets || []);
  }, [api]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleAdd = async () => {
    setError(null);
    if (!name.trim()) {
      setError('凭据名不能为空');
      return;
    }
    setBusy(true);
    const res = await api.secretsSet(name.trim(), value);
    setBusy(false);
    if (res?.success) {
      setName('');
      setValue('');
      await refresh();
    } else {
      setError(res?.error || '保存失败');
    }
  };

  const handleDelete = async (n: string) => {
    if (!confirm(`确定删除凭据「${n}」？`)) return;
    await api.secretsDelete(n);
    await refresh();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl shadow-xl w-[520px] max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-3 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-800">🔐 凭据保险库</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-xl leading-none">×</button>
        </div>

        <div className="px-5 py-4 space-y-3 border-b border-gray-100">
          <p className="text-xs text-gray-500">
            凭据加密存储，列表只显示名称。流程任意值里用 <code className="bg-gray-100 px-1 rounded">{'{{secret:名称}}'}</code> 引用，
            明文不会写入运行历史或日志。
          </p>
          <div className="flex gap-2">
            <input
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="名称，如 login_pw"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <input
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="值（将被加密）"
              type="password"
              value={value}
              onChange={(e) => setValue(e.target.value)}
            />
            <Button variant="primary" onClick={handleAdd} disabled={busy}>
              保存
            </Button>
          </div>
          {error && <div className="text-xs text-red-500">{error}</div>}
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-3">
          {secrets.length === 0 ? (
            <div className="text-sm text-gray-400 text-center py-6">暂无凭据</div>
          ) : (
            <ul className="space-y-1">
              {secrets.map((s) => (
                <li key={s.name} className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50">
                  <div>
                    <div className="text-sm font-medium text-gray-800">{s.name}</div>
                    <div className="text-xs text-gray-400">
                      {s.updated_at ? `更新于 ${new Date(s.updated_at).toLocaleString()}` : ''}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(s.name)}
                    className="text-xs text-red-500 hover:text-red-700"
                  >
                    删除
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};
