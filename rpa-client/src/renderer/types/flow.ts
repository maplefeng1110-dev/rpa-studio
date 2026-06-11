/**
 * Flow/Step 类型定义
 */

// Step 类型
export type StepType =
  | 'open'
  | 'click'
  | 'input'
  | 'wait'
  | 'extract'
  | 'if'
  | 'loop'
  | 'select'
  | 'switch_tab'
  | 'download';

// Step 配置
export interface StepConfig {
  id: string;
  type: StepType;
  selector?: string;
  selectors?: string[];  // 候选选择器（按优先级排序），运行时自愈回退
  value?: string;
  timeout: number;
  on_fail: 'abort' | 'skip' | 'retry';
  save_path?: string;
  context_key?: string;
  frame?: string;        // 可选 iframe 定位（选择器或下标）

  // select 下拉选择
  by?: 'text' | 'value' | 'index';

  // switch_tab 标签页切换
  new_tab?: boolean;
  url?: string;
  
  // 重试机制
  max_retries?: number;
  retry_delay?: number;

  // If 条件分支
  condition?: string;
  then?: StepConfig[];
  else?: StepConfig[];

  // Loop 循环
  loop_type?: 'count' | 'each';
  item_key?: string;
  index_key?: string;
  steps?: StepConfig[];
}

// Flow 定义
export interface FlowDefinition {
  id: string;
  name: string;
  description?: string;
  steps: StepConfig[];
  createdAt: string;
  updatedAt: string;
}

// 执行日志条目
export interface ExecutionLogEntry {
  step_index: number;
  step_type: string;
  start_time: string;
  end_time: string;
  duration_ms: number;
  success: boolean;
  message: string;
  screenshot?: string | null;  // 失败时自动截图的本地路径
}

// 执行响应
export interface ExecutionResponse {
  success: boolean;
  flow_name: string;
  executed_steps: number;
  total_steps: number;
  context: Record<string, unknown>;
  execution_log: ExecutionLogEntry[];
  error?: string;
}

// Step 类型元数据
export interface StepTypeMeta {
  type: StepType;
  name: string;
  description: string;
  icon: string;
  color: string;
  requiredFields: string[];
  optionalFields: string[];
}

// Step 类型元数据配置
export const STEP_TYPE_METAS: Record<StepType, StepTypeMeta> = {
  open: {
    type: 'open',
    name: '打开页面',
    description: '打开指定 URL',
    icon: '🌐',
    color: 'bg-blue-100 border-blue-300',
    requiredFields: ['value'],
    optionalFields: ['timeout', 'on_fail'],
  },
  click: {
    type: 'click',
    name: '点击元素',
    description: '点击指定选择器的元素',
    icon: '👆',
    color: 'bg-green-100 border-green-300',
    requiredFields: ['selector'],
    optionalFields: ['timeout', 'on_fail'],
  },
  input: {
    type: 'input',
    name: '输入文本',
    description: '向指定元素输入文本',
    icon: '⌨️',
    color: 'bg-yellow-100 border-yellow-300',
    requiredFields: ['selector', 'value'],
    optionalFields: ['timeout', 'on_fail'],
  },
  wait: {
    type: 'wait',
    name: '等待',
    description: '等待指定秒数',
    icon: '⏳',
    color: 'bg-purple-100 border-purple-300',
    requiredFields: ['value'],
    optionalFields: ['on_fail'],
  },
  extract: {
    type: 'extract',
    name: '提取内容',
    description: '提取元素内容并保存',
    icon: '📥',
    color: 'bg-pink-100 border-pink-300',
    requiredFields: ['selector'],
    optionalFields: ['save_path', 'context_key', 'timeout', 'on_fail'],
  },
  if: {
    type: 'if',
    name: '条件判断 (If)',
    description: '根据条件执行不同的分支步骤',
    icon: '🔀',
    color: 'bg-orange-100 border-orange-300',
    requiredFields: ['condition'],
    optionalFields: ['on_fail'],
  },
  loop: {
    type: 'loop',
    name: '循环控制 (Loop)',
    description: '按次数或迭代列表重复执行步骤',
    icon: '🔁',
    color: 'bg-indigo-100 border-indigo-300',
    requiredFields: ['loop_type', 'value'],
    optionalFields: ['item_key', 'index_key', 'on_fail'],
  },
  select: {
    type: 'select',
    name: '下拉选择',
    description: '操作下拉框，按文本/值/下标选择',
    icon: '🔽',
    color: 'bg-teal-100 border-teal-300',
    requiredFields: ['selector', 'value'],
    optionalFields: ['by', 'timeout', 'on_fail', 'frame'],
  },
  switch_tab: {
    type: 'switch_tab',
    name: '切换标签页',
    description: '切换标签页或打开新标签页',
    icon: '🗂️',
    color: 'bg-cyan-100 border-cyan-300',
    requiredFields: [],
    optionalFields: ['value', 'new_tab', 'url', 'on_fail'],
  },
  download: {
    type: 'download',
    name: '文件下载',
    description: '点击触发下载并等待完成',
    icon: '⬇️',
    color: 'bg-lime-100 border-lime-300',
    requiredFields: ['selector'],
    optionalFields: ['save_path', 'timeout', 'on_fail', 'frame'],
  },
};

// 创建默认 Step
export function createDefaultStep(type: StepType): StepConfig {
  const baseStep: StepConfig = {
    id: `step_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    type,
    timeout: 10,
    on_fail: 'abort',
  };

  if (type === 'if') {
    return {
      ...baseStep,
      condition: '{{status}} == success',
      then: [],
      else: [],
    };
  }

  if (type === 'loop') {
    return {
      ...baseStep,
      loop_type: 'count',
      value: '5',
      item_key: 'item',
      index_key: 'index',
      steps: [],
    };
  }

  if (type === 'select') {
    return { ...baseStep, by: 'text' };
  }

  if (type === 'switch_tab') {
    return { ...baseStep, value: 'latest' };
  }

  return baseStep;
}

// 创建默认 Flow
export function createDefaultFlow(name: string = '新流程'): FlowDefinition {
  const now = new Date().toISOString();
  return {
    id: `flow_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    name,
    description: '',
    steps: [],
    createdAt: now,
    updatedAt: now,
  };
}
