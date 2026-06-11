# 最小可运行 RPA 内核开发文档（基于 DrissionPage）

## 1. 文档目标

本开发文档用于指导实现一个**最小可运行（MVP）的 Web RPA 内核**，该内核以 **DrissionPage** 作为浏览器控制基础，支持通过 **JSON 流程定义** 执行自动化网页操作。

设计目标不是一次性做成“通用 RPA 平台”，而是：

- 可运行
- 可扩展
- 可维护
- 可作为长期母项目演进

适用对象：
- 个人开发者
- 小团队
- AI + 自动化 + 内容/运营场景

---

## 2. 设计原则

### 2.1 核心原则

1. **流程与浏览器解耦**
2. **Step 原子化**
3. **失败可控，而非追求 100% 成功**
4. **优先代码驱动，其次配置化**

### 2.2 不做的事情（MVP 阶段）

- ~~不做可视化拖拽~~ ✅ 已实现（Electron 桌面客户端）
- 不做 BPMN / 复杂流程图
- 不做桌面级 RPA（仅 Web）
- 不做多租户权限系统

---

## 3. 系统整体架构

### 3.1 架构总览

```
Flow(JSON) → FlowEngine → StepExecutor → BrowserAdapter → DrissionPage
                               ↓
                          Runtime Context
```

### 3.2 模块职责说明

| 模块 | 职责 | 是否可替换 |
|---|---|---|
| Flow Definition | 定义自动化流程 | 是 |
| Flow Engine | 控制流程执行 | 是 |
| Step Executor | 执行单步动作 | 是 |
| Browser Adapter | 封装浏览器能力 | 是 |
| Runtime Context | 存储运行状态 | 否 |

---

## 4. 流程定义（Flow Definition）

### 4.1 Flow 的基本结构

一个 Flow 表示一个完整的 RPA 自动化流程。

```json
{
  "name": "login_and_export",
  "steps": []
}
```

### 4.2 Step 定义规范

```json
{
  "type": "click",
  "selector": "#submit",
  "value": null,
  "timeout": 10,
  "on_fail": "abort"
}
```

### 4.3 Step 字段说明

| 字段 | 说明 |
|---|---|
| type | 动作类型（open/click/input/...） |
| selector | 元素定位方式 |
| value | 输入值或参数 |
| timeout | 超时时间（秒） |
| on_fail | 失败策略（retry/skip/abort） |

---

## 5. Runtime Context（运行上下文）

### 5.1 作用

Runtime Context 是流程运行期间的共享状态容器，用于：

- 变量传递
- 页面数据缓存
- Step 执行结果存储

### 5.2 示例结构

```python
{
  "username": "admin",
  "password": "123456",
  "last_page_text": "登录成功",
  "export_path": "/tmp/data.xlsx"
}
```

### 5.3 变量渲染规则

在 Step 中允许使用：

```
{{variable_name}}
```

运行前由模板渲染模块替换为 Context 中的真实值。

---

## 6. Flow Engine（流程引擎）

### 6.1 职责

- 加载 Flow 定义
- 顺序执行 Step
- 捕获异常
- 根据 on_fail 决定后续行为
- 更新 Runtime Context

### 6.2 不属于 Flow Engine 的职责

- 浏览器操作细节
- AI 决策逻辑
- UI / API 层

---

## 7. Step Executor（步骤执行器）

### 7.1 Step 类型列表（MVP）

| Step | 说明 |
|---|---|
| open | 打开页面 |
| click | 点击元素 |
| input | 输入文本 |
| wait | 等待 |
| extract | 提取页面信息 |
| decision | 条件判断（可接 AI） |

### 7.2 Step 扩展原则

- 每新增一种行为，只新增一个 Step 类
- 不修改 Flow Engine 核心逻辑

---

## 8. Browser Adapter（浏览器适配层）

### 8.1 设计目的

Browser Adapter 用于**隔离 RPA 内核与具体浏览器实现**。

任何上层模块禁止直接使用 DrissionPage API。

### 8.2 对外暴露接口（示例）

- open(url)
- click(selector)
- input(selector, text)
- exists(selector)
- text(selector)
- wait(seconds)
- screenshot(path)

### 8.3 DrissionPage 实现说明

- 使用 ChromiumPage
- 支持接管已有浏览器（可选）
- 支持有头 / 无头切换

---

## 9. 异常与失败策略

### 9.1 常见异常类型

- 元素不存在
- 页面加载超时
- 页面结构变化

### 9.2 on_fail 策略说明

| 策略 | 行为 |
|---|---|
| retry | 重试当前 Step |
| skip | 跳过当前 Step |
| abort | 终止流程 |

---

## 10. 日志与回放

### 10.1 日志内容

- Step 开始 / 结束时间
- Step 执行结果
- 异常信息

### 10.2 回放能力（建议）

- 每个 Step 截图
- 保存 DOM 关键文本

该能力可直接作为：
- Debug 工具
- 教程 / 内容素材

---

## 11. 项目目录结构

```
rpa/
├── rpa_core/                # Python 后端引擎（pip 包）
│   ├── main.py
│   ├── server.py            # FastAPI HTTP 服务（端口 8765）
│   ├── requirements.txt
│   ├── flows/               # JSON 流程定义
│   ├── engine/              # 流程引擎
│   ├── steps/               # Step 执行器
│   ├── browser/             # 浏览器适配层
│   ├── utils/               # 工具模块（Context、Logger）
│   ├── output/              # 输出文件
│   └── logs/                # 运行日志
└── rpa-client/              # Electron 桌面客户端（可视化前端）
    ├── src/
    │   ├── main/            # Electron 主进程（管理 Python 子进程）
    │   └── renderer/        # React 渲染进程（ReactFlow 拖拽编辑器）
    │       ├── components/  # editor / properties / execution / layout
    │       ├── store/       # Redux 状态管理
    │       └── types/       # TypeScript 类型定义
    └── package.json
```

---

## 12. MVP 实现里程碑

### 阶段一：可运行

- 浏览器可打开页面
- Flow 顺序执行
- open / click / input 可用

### 阶段二：可失败

- on_fail 生效
- 日志可追踪

### 阶段三：可扩展

- 新增 Step 不改核心
- decision Step 接 AI

---

## 13. 可视化客户端（Electron）

### 13.1 技术栈

| 层次 | 技术 |
|---|---|
| 桌面容器 | Electron 28 |
| UI 框架 | React 18 + TypeScript |
| 拖拽画布 | ReactFlow |
| 状态管理 | Redux Toolkit |
| 样式 | TailwindCSS |
| API 通信 | Axios → FastAPI（`127.0.0.1:8765`） |

### 13.2 架构说明

```
Electron 主进程
  └── 自动启动 rpa_core/server.py（Python 子进程）
Electron 渲染进程（React）
  ├── 拖拽编辑 Flow（ReactFlow 画布）
  ├── 右侧属性面板（编辑 Step 参数）
  ├── 执行日志面板（实时查看结果）
  └── HTTP 请求 → FastAPI → FlowEngine → DrissionPage
```

### 13.3 启动方式

```bash
# 开发模式
cd rpa-client
npm run electron:dev

# 打包发布
npm run electron:build
```

### 13.4 支持的 Step 类型

| 组件 | 说明 |
|---|---|
| 🌐 open | 打开页面 |
| 👆 click | 点击元素 |
| ⌨️ input | 输入文本 |
| ⏱️ wait | 等待 |
| 📋 extract | 提取文本 |

---

## 14. 后续演进方向

- ~~Flow 可视化编辑~~ ✅ 已实现（Electron 桌面客户端）
- ~~AI 自动生成 Flow~~ ✅ 已实现（基础版）
- ~~FastAPI 服务化~~ ✅ 已实现（`server.py`，端口 8765）
- `on_fail: retry` 重试策略实现
- 无头模式（headless）支持
- 并发任务调度
- 商业化 SaaS 封装

---

## 15. 总结

该 RPA 内核以**稳定、克制、可进化**为核心设计思想，适合作为：

- 长期自动化基础设施
- AI + RPA 产品原型
- 内容输出与产品共生项目

优先把它跑起来，而不是一次性做大。

