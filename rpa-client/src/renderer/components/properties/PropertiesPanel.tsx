/**
 * PropertiesPanel 组件 - Step 属性编辑器
 */
import React from 'react';
import { useDispatch, useSelector } from 'react-redux';
import type { RootState, AppDispatch } from '../../store';
import { updateStep, removeStep } from '../../store/flowSlice';
import { STEP_TYPE_METAS, type StepConfig } from '../../types/flow';
import { Button } from '../common/Button';
import { Input } from '../common/Input';
import { Select } from '../common/Select';
import { Textarea } from '../common/Textarea';
import { useIpc } from '../../hooks/useIpc';

interface PropertiesPanelProps {}

export const PropertiesPanel: React.FC<PropertiesPanelProps> = () => {
  const dispatch = useDispatch<AppDispatch>();
  const currentFlow = useSelector((state: RootState) => state.flow.currentFlow);
  const selectedStepId = useSelector((state: RootState) => state.flow.selectedStepId);
  const [isPicking, setIsPicking] = React.useState(false);
  const { api } = useIpc();

  // 递归寻找步骤
  const findStepById = (steps: StepConfig[], id: string): StepConfig | null => {
    for (const step of steps) {
      if (step.id === id) return step;
      if (step.type === 'if') {
        const found = findStepById(step.then || [], id) || findStepById(step.else || [], id);
        if (found) return found;
      }
      if (step.type === 'loop') {
        const found = findStepById(step.steps || [], id);
        if (found) return found;
      }
    }
    return null;
  };

  const selectedStep = currentFlow ? findStepById(currentFlow.steps, selectedStepId || '') : null;

  if (!selectedStep) {
    return (
      <div className="h-full flex items-center justify-center bg-white">
        <div className="text-center text-gray-400">
          <div className="text-4xl mb-2">📝</div>
          <p>选择一个步骤以编辑属性</p>
        </div>
      </div>
    );
  }

  const meta = STEP_TYPE_METAS[selectedStep.type];

  const handleUpdate = (updates: Partial<StepConfig>) => {
    dispatch(updateStep({ id: selectedStep.id, updates }));
  };

  const handleDelete = () => {
    dispatch(removeStep(selectedStep.id));
  };

  const handlePickElement = async () => {
    setIsPicking(true);
    try {
      const startRes = await api.pickElementStart();
      if (!startRes.success) {
        alert('启动拾取失败: ' + (startRes.error || '未知错误'));
        setIsPicking(false);
        return;
      }

      // 开始轮询结果
      const interval = setInterval(async () => {
        try {
          const res = await api.pickElementResult();
          if (res && res.selector) {
            clearInterval(interval);
            // 同时保存候选列表，运行时支持选择器自愈回退
            handleUpdate({ selector: res.selector, selectors: res.selectors });
            setIsPicking(false);
          } else if (res && res.success === false && (res.message || '').includes('未启动')) {
            clearInterval(interval);
            alert('浏览器未启动，请先运行一个打开页面的步骤！');
            setIsPicking(false);
          }
        } catch (err) {
          clearInterval(interval);
          setIsPicking(false);
        }
      }, 1000);

      // 30秒后自动超时，防止无限轮询
      setTimeout(() => {
        clearInterval(interval);
        setIsPicking(false);
      }, 30000);

    } catch (err) {
      alert('拾取错误: ' + (err as Error).message);
      setIsPicking(false);
    }
  };

  // ===== 候选选择器（自愈回退）管理 =====
  const candidates: string[] = selectedStep.selectors || [];

  // 统一提交：保持 selector 与 selectors[0] 同步；列表为空则清空 selectors
  const commitSelectors = (next: string[]) => {
    handleUpdate({
      selectors: next.length > 0 ? next : undefined,
      selector: next.length > 0 ? next[0] : selectedStep.selector,
    });
  };

  // 编辑首选选择器输入框：有候选时同步更新 selectors[0]
  const setPrimarySelector = (val: string) => {
    if (candidates.length > 0) {
      const next = [...candidates];
      next[0] = val;
      commitSelectors(next);
    } else {
      handleUpdate({ selector: val });
    }
  };

  const addCandidate = () => {
    const base =
      candidates.length > 0 ? candidates : selectedStep.selector ? [selectedStep.selector] : [];
    commitSelectors([...base, '']);
  };
  const updateCandidate = (i: number, val: string) => {
    const next = [...candidates];
    next[i] = val;
    commitSelectors(next);
  };
  const removeCandidate = (i: number) => {
    commitSelectors(candidates.filter((_, idx) => idx !== i));
  };
  const promoteCandidate = (i: number) => {
    if (i <= 0) return;
    const next = [...candidates];
    [next[i - 1], next[i]] = [next[i], next[i - 1]];
    commitSelectors(next);
  };

  return (
    <div className="h-full flex flex-col bg-white">
      {/* 头部 */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{meta?.icon || '⚙️'}</span>
          <div>
            <h3 className="font-semibold text-gray-800">{meta?.name || '未知步骤'}</h3>
            <p className="text-xs text-gray-500">{meta?.description || ''}</p>
          </div>
        </div>
      </div>

      {/* 表单 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* 通用属性 */}
        {(selectedStep.type === 'open' || selectedStep.type === 'wait') && (
          <Input
            label="值"
            type={selectedStep.type === 'wait' ? 'number' : 'text'}
            value={selectedStep.value || ''}
            onChange={(e) => handleUpdate({ value: e.target.value })}
            placeholder={selectedStep.type === 'open' ? 'https://example.com' : '等待秒数'}
          />
        )}

        {(selectedStep.type === 'click' ||
          selectedStep.type === 'input' ||
          selectedStep.type === 'extract' ||
          selectedStep.type === 'select' ||
          selectedStep.type === 'download') && (
          <div className="space-y-1">
            <label className="block text-sm font-medium text-gray-700">选择器</label>
            <div className="flex gap-2">
              <input
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                value={selectedStep.selector || ''}
                onChange={(e) => setPrimarySelector(e.target.value)}
                placeholder="#id / css:.class / xpath://.. / text:登录"
              />
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={handlePickElement}
                disabled={isPicking}
              >
                {isPicking ? '🎯 拾取中...' : '🎯 拾取'}
              </Button>
            </div>

            {/* 候选选择器：运行时按顺序自愈回退 */}
            {candidates.length > 0 && (
              <div className="mt-2 space-y-1.5 rounded-lg border border-gray-100 bg-gray-50 p-2">
                <p className="text-xs text-gray-500">
                  候选选择器（失败时按 #1→#{candidates.length} 顺序自愈回退）
                </p>
                {candidates.map((c, i) => (
                  <div key={i} className="flex items-center gap-1">
                    <span
                      className={`w-4 text-center text-xs ${
                        i === 0 ? 'font-semibold text-blue-600' : 'text-gray-400'
                      }`}
                    >
                      {i + 1}
                    </span>
                    <input
                      className="flex-1 px-2 py-1 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-blue-400"
                      value={c}
                      onChange={(e) => updateCandidate(i, e.target.value)}
                      placeholder="css:.x / xpath://.. / text:登录"
                    />
                    <button
                      type="button"
                      title="提升优先级"
                      disabled={i === 0}
                      onClick={() => promoteCandidate(i)}
                      className="px-1 text-gray-400 hover:text-blue-600 disabled:opacity-30"
                    >
                      ▲
                    </button>
                    <button
                      type="button"
                      title="删除候选"
                      onClick={() => removeCandidate(i)}
                      className="px-1 text-gray-400 hover:text-red-600"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
            <button
              type="button"
              onClick={addCandidate}
              className="text-xs text-blue-600 hover:underline"
            >
              ＋ 添加候选选择器
            </button>

            <Input
              label="iframe 定位（可选）"
              value={selectedStep.frame || ''}
              onChange={(e) => handleUpdate({ frame: e.target.value || undefined })}
              placeholder="iframe 的选择器或下标，留空表示主文档"
            />
          </div>
        )}

        {selectedStep.type === 'input' && (
          <Textarea
            label="输入值"
            value={selectedStep.value || ''}
            onChange={(e) => handleUpdate({ value: e.target.value })}
            placeholder="要输入的文本..."
            rows={3}
          />
        )}

        {/* SELECT 下拉选择配置 */}
        {selectedStep.type === 'select' && (
          <>
            <Select
              label="选择方式"
              value={selectedStep.by || 'text'}
              onChange={(e) => handleUpdate({ by: e.target.value as 'text' | 'value' | 'index' })}
            >
              <option value="text">按可见文本</option>
              <option value="value">按 value 属性</option>
              <option value="index">按下标（从 0 开始）</option>
            </Select>
            <Input
              label="选项值"
              value={selectedStep.value || ''}
              onChange={(e) => handleUpdate({ value: e.target.value })}
              placeholder={selectedStep.by === 'index' ? '例如: 2' : '要选择的选项'}
            />
          </>
        )}

        {/* SWITCH_TAB 标签页切换配置 */}
        {selectedStep.type === 'switch_tab' && (
          <>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={!!selectedStep.new_tab}
                onChange={(e) => handleUpdate({ new_tab: e.target.checked })}
              />
              打开新标签页
            </label>
            {selectedStep.new_tab ? (
              <Input
                label="新标签页地址（可选）"
                value={selectedStep.url || ''}
                onChange={(e) => handleUpdate({ url: e.target.value })}
                placeholder="https://example.com，留空为空白页"
              />
            ) : (
              <Input
                label="目标标签页"
                value={selectedStep.value || ''}
                onChange={(e) => handleUpdate({ value: e.target.value })}
                placeholder="latest（最新）或下标，如 0、1"
              />
            )}
          </>
        )}

        {/* DOWNLOAD 文件下载配置 */}
        {selectedStep.type === 'download' && (
          <Input
            label="下载保存目录（可选）"
            value={selectedStep.save_path || ''}
            onChange={(e) => handleUpdate({ save_path: e.target.value })}
            placeholder="默认 downloads（限定在输出沙箱内）"
          />
        )}

        {selectedStep.type === 'extract' && (
          <>
            <Input
              label="保存路径（可选）"
              value={selectedStep.save_path || ''}
              onChange={(e) => handleUpdate({ save_path: e.target.value })}
              placeholder="/path/to/save.txt"
            />
            <Input
              label="上下文键名（可选）"
              value={selectedStep.context_key || ''}
              onChange={(e) => handleUpdate({ context_key: e.target.value })}
              placeholder="result"
            />
          </>
        )}

        {/* IF 条件配置 */}
        {selectedStep.type === 'if' && (
          <Input
            label="判断条件 (表达式)"
            value={selectedStep.condition || ''}
            onChange={(e) => handleUpdate({ condition: e.target.value })}
            placeholder="例如: {{status}} == 'success'"
          />
        )}

        {/* LOOP 循环配置 */}
        {selectedStep.type === 'loop' && (
          <>
            <Select
              label="循环类型"
              value={selectedStep.loop_type || 'count'}
              onChange={(e) => handleUpdate({ loop_type: e.target.value as 'count' | 'each' })}
            >
              <option value="count">按次数循环</option>
              <option value="each">遍历列表</option>
            </Select>

            <Input
              label={selectedStep.loop_type === 'each' ? '遍历目标列表变量' : '循环次数'}
              value={selectedStep.value || ''}
              onChange={(e) => handleUpdate({ value: e.target.value })}
              placeholder={selectedStep.loop_type === 'each' ? '例如: {{my_list}}' : '例如: 5'}
            />

            <Input
              label="当前项保存为变量名"
              value={selectedStep.item_key || ''}
              onChange={(e) => handleUpdate({ item_key: e.target.value })}
              placeholder="默认 item"
            />

            <Input
              label="当前索引保存为变量名"
              value={selectedStep.index_key || ''}
              onChange={(e) => handleUpdate({ index_key: e.target.value })}
              placeholder="默认 index"
            />
          </>
        )}

        <Input
          label="超时限制（秒）"
          type="number"
          value={selectedStep.timeout}
          onChange={(e) => handleUpdate({ timeout: parseInt(e.target.value) || 10 })}
          min={1}
        />

        <Select
          label="失败策略"
          value={selectedStep.on_fail}
          onChange={(e) => handleUpdate({ on_fail: e.target.value as 'abort' | 'skip' | 'retry' })}
        >
          <option value="abort">中止流程</option>
          <option value="skip">跳过并继续</option>
          <option value="retry">重试此步骤</option>
        </Select>

        {selectedStep.on_fail === 'retry' && (
          <div className="p-3 bg-yellow-50 rounded-lg border border-yellow-100 space-y-3">
            <Input
              label="最大重试次数"
              type="number"
              value={selectedStep.max_retries || 3}
              onChange={(e) => handleUpdate({ max_retries: parseInt(e.target.value) || 3 })}
              min={1}
            />
            <Input
              label="重试时间间隔（秒）"
              type="number"
              value={selectedStep.retry_delay || 2}
              onChange={(e) => handleUpdate({ retry_delay: parseInt(e.target.value) || 2 })}
              min={1}
            />
          </div>
        )}
      </div>

      {/* 底部操作 */}
      <div className="p-4 border-t border-gray-200">
        <Button variant="danger" className="w-full" onClick={handleDelete}>
          删除步骤
        </Button>
      </div>
    </div>
  );
};
