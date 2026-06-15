# RPA Studio

> AI 原生的轻量 **Web RPA**（个人版）。可视化拖拽编排，选择器自愈 + AI 视觉兜底，自然语言生成流程，定时调度，加密凭据。
> 内核 Python（DrissionPage）+ 桌面客户端 Electron。

[![打包客户端](https://github.com/maplefeng1110-dev/rpa-studio/actions/workflows/build.yml/badge.svg)](https://github.com/maplefeng1110-dev/rpa-studio/actions/workflows/build.yml)
[![Release](https://img.shields.io/github/v/release/maplefeng1110-dev/rpa-studio?include_prereleases)](https://github.com/maplefeng1110-dev/rpa-studio/releases)

---

## 这是什么

一个面向**个人 / 小团队**的网页自动化工具：在可视化画布上拖出"打开页面 → 输入 → 点击 → 提取"这样的流程并执行。定位上不追桌面/OCR/控制中心那套企业护城河，专注把**开源、本地、AI 原生的轻量 Web RPA**做扎实。

## 核心能力

- 🎨 **可视化编排** —— Electron + React + ReactFlow 拖拽画布；元素可视化拾取（一次拾取生成多个候选选择器）。
- 🧩 **控制流** —— `if` 条件、`loop` 循环（按次数 / 遍历列表）、`{{变量}}` 上下文插值。
- 🩹 **选择器自愈** —— 候选选择器按优先级回退；支持 CSS / XPath / 文本定位。
- 👁️ **AI 视觉兜底** —— DOM 候选全失效时，截图 + 精简 DOM 交给多模态 LLM，返回修好的选择器或点击坐标。
- ✨ **自然语言生成流程** —— 一句话描述 → 生成可编辑的 Flow。
- ⏰ **定时调度** —— 内置 cron / interval 调度 + 任务队列。
- 🔐 **加密凭据保险库** —— 账号密码加密存储，流程里用 `{{secret:名称}}` 引用，明文不入历史/日志。
- 📜 **运行历史 + 失败截图** —— 每次运行落 SQLite，步骤失败自动截图。
- 🧱 **丰富步骤** —— open / click / input / wait / extract / select(下拉) / switch_tab(多标签) / download / if / loop，支持 iframe 内定位、失败重试。
- 🖥️ **跨平台桌面包** —— Windows / macOS 独立安装包，**内置后端，无需装 Python**。

## 架构

```
Flow(JSON) → FlowEngine → Step → BrowserAdapter → DrissionPage → Chrome
                                        ↑ 选择器自愈 / AI 视觉兜底
Electron 客户端 ──(HTTP/WebSocket)──▶ FastAPI 后端(rpa_core)
```

- `rpa_core/` —— Python 引擎 + FastAPI 服务（流程引擎、浏览器适配、调度、保险库、AI）。
- `rpa-client/` —— Electron + React 可视化客户端。

## 快速开始

### 方式一：下载安装包（推荐）

到 [Releases](https://github.com/maplefeng1110-dev/rpa-studio/releases) 下载对应平台的安装包：
- **Windows**：`...Setup...exe`（安装版）或 `...Portable...exe`（免安装）
- **macOS**：`...arm64.dmg`（Apple Silicon）

> ⚠️ 目标机需安装 **Google Chrome**（驱动系统 Chrome，未打入包内）。首次打开未签名应用会被系统拦截，按提示放行即可（详见操作手册）。

### 方式二：从源码运行（开发）

```bash
# 后端
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r rpa_core/requirements.txt

# 前端
cd rpa-client && npm install

# 一键启动（根目录）
./start.sh
```

## 使用 AI（可选）

AI 是可选的。要用「✨ AI 生成流程」和「视觉兜底」，在客户端点 **「⚙️ AI 设置」** 填自己的 API key / 地址 / 模型即可（key 加密存储、不回显）。默认走官方 Claude（`claude-opus-4-8`），也可填代理 / 自托管地址。

## 自己打包

在**对应目标系统**上：
```bash
cd rpa-client
npm run package:mac      # macOS → .dmg / .zip
npm run package:win      # Windows → 安装包 / 免安装 exe
```
> PyInstaller 只能产出运行它的系统的可执行文件，需在各平台分别打包，或用仓库内的 GitHub Actions（推 `v*` 标签自动出三平台 Release）。

## 文档

完整使用、接口、数据存储位置、打包细节见 **[操作手册.md](操作手册.md)**。

## 数据存储

| 内容 | 位置 |
|------|------|
| 流程定义 | 客户端用户数据目录 `.../rpa-client/flows/` |
| 运行历史 / 调度 / 加密凭据 | `rpa_core/data/` |
| 失败截图 / 输出 | `rpa_core/output/` |

---

个人项目，按需自用。欢迎参考。
