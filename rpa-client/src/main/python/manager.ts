/**
 * Python 进程管理器
 * 管理 Python FastAPI 后端进程
 */
import { ChildProcess, spawn } from 'child_process';
import path from 'path';
import { app } from 'electron';
import kill from 'tree-kill';
import fs from 'fs';

const PYTHON_API_URL = 'http://127.0.0.1:8765';

export class PythonManager {
  private process: ChildProcess | null = null;
  private isRunning = false;
  private logs: string[] = [];
  private onLogCallback: ((log: string) => void) | null = null;
  private apiToken = '';

  private healthCheckInterval: NodeJS.Timeout | null = null;

  private readApiTokenFromFile(): string {
    try {
      const candidates = [
        '/Users/ffm1110/workapp/rpa/.rpa_token',
        path.join(process.cwd(), '.rpa_token'),
        path.join(process.cwd(), '../.rpa_token'),
        path.join(__dirname, '../../../../../.rpa_token'),
        path.join(__dirname, '../../../../.rpa_token'),
      ];

      try {
        candidates.push(path.join(app.getAppPath(), '../.rpa_token'));
        if (!app.isPackaged) {
          const projectRoot = path.join(__dirname, '../../../..');
          candidates.unshift(path.join(projectRoot, '.rpa_token'));
        }
      } catch {
        // app 可能尚未就绪
      }

      for (const file of candidates) {
        if (fs.existsSync(file)) {
          const token = fs.readFileSync(file, 'utf8').trim();
          if (token) {
            console.log(`[PythonManager] 从文件读取到 Token: ${file}`);
            return token;
          }
        }
      }
      console.log('[PythonManager] 未能从任何候选路径读取到 Token');
    } catch (err) {
      console.error('[PythonManager] readApiTokenFromFile 异常:', err);
    }
    return '';
  }

  constructor() {
    this.apiToken = process.env.RPA_API_TOKEN || this.readApiTokenFromFile();
    if (this.apiToken) {
      this.log(`加载到 API Token: ${this.apiToken}`);
    }
    this.startHealthCheck();
  }

  /**
   * 启动后台健康检查，自动检测并监控 Python 服务状态
   */
  startHealthCheck(): void {
    if (this.healthCheckInterval) return;

    this.healthCheckInterval = setInterval(async () => {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 1000);

        const response = await fetch(`${PYTHON_API_URL}/health`, {
          signal: controller.signal,
        });
        clearTimeout(timeoutId);

        if (response.ok) {
          if (!this.isRunning) {
            this.isRunning = true;
            this.log('检测到 Python 后端服务已启动并处于活跃状态');
          }
          if (!this.apiToken) {
            this.apiToken = process.env.RPA_API_TOKEN || this.readApiTokenFromFile();
          }
        } else {
          if (!this.process && this.isRunning) {
            this.isRunning = false;
            this.log('检测到 Python 后端服务非正常响应');
          }
        }
      } catch (err) {
        if (!this.process && this.isRunning) {
          this.isRunning = false;
          this.log('Python 后端连接断开');
        }
      }
    }, 2000);
  }

  /**
   * 获取 API 令牌 (每次调用时若为空则重新尝试读取)
   */
  getApiToken(): string {
    if (!this.apiToken) {
      this.apiToken = process.env.RPA_API_TOKEN || this.readApiTokenFromFile();
      if (this.apiToken) {
        this.log(`延迟加载到 API Token: ${this.apiToken}`);
      }
    }
    return this.apiToken;
  }

  /**
   * 启动 Python 后端进程
   */
  async start(): Promise<boolean> {
    if (this.isRunning) {
      this.log('Python 后端已经在运行');
      return true;
    }

    try {
      // 找到 Python 解释器和 server.py 路径
      const pythonPath = await this.findPython();
      const serverPath = this.findServerScript();

      if (!pythonPath) {
        throw new Error('未找到 Python 解释器');
      }
      if (!serverPath) {
        throw new Error('未找到 server.py');
      }

      // 生成随机 Token
      this.apiToken = Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);

      this.log(`启动 Python 后端: ${pythonPath} ${serverPath}`);

      // 启动子进程
      this.process = spawn(pythonPath, [serverPath], {
        cwd: path.dirname(serverPath),
        stdio: ['ignore', 'pipe', 'pipe'],
        env: {
          ...process.env,
          RPA_API_TOKEN: this.apiToken,
        },
      });

      // 监听输出
      this.process.stdout?.on('data', (data) => {
        const log = data.toString();
        const tokenMatch = log.match(/__RPA_API_TOKEN_START__=(.+)/);
        if (tokenMatch) {
          this.apiToken = tokenMatch[1].trim();
        }
        this.log(log);
      });

      this.process.stderr?.on('data', (data) => {
        const log = data.toString();
        this.log(log);
      });

      this.process.on('close', (code) => {
        this.log(`Python 进程退出，代码: ${code}`);
        this.isRunning = false;
        this.process = null;
      });

      this.process.on('error', (err) => {
        this.log(`Python 进程错误: ${err.message}`);
        this.isRunning = false;
        this.process = null;
      });

      // 等待服务启动
      await this.waitForServer();
      this.isRunning = true;
      this.log('Python 后端启动成功');
      return true;
    } catch (err) {
      this.log(`启动 Python 后端失败: ${(err as Error).message}`);
      return false;
    }
  }

  /**
   * 停止 Python 后端进程
   */
  async stop(): Promise<void> {
    if (!this.process) {
      return;
    }

    this.log('正在停止 Python 后端...');

    return new Promise((resolve) => {
      if (this.process?.pid) {
        kill(this.process.pid, (err) => {
          if (err) {
            this.log(`停止进程失败: ${err.message}`);
          }
          this.isRunning = false;
          this.process = null;
          resolve();
        });
      } else {
        this.process?.kill();
        this.isRunning = false;
        this.process = null;
        resolve();
      }
    });
  }

  /**
   * 获取运行状态
   */
  getStatus(): { running: boolean; logs: string[] } {
    return {
      running: this.isRunning,
      logs: [...this.logs],
    };
  }

  /**
   * 设置日志回调
   */
  setOnLogCallback(callback: (log: string) => void): void {
    this.onLogCallback = callback;
  }

  /**
   * 获取 API URL
   */
  getApiUrl(): string {
    return PYTHON_API_URL;
  }

  // ============ 私有方法 ============

  private log(message: string): void {
    const timestamp = new Date().toISOString();
    const logLine = `[${timestamp}] ${message}`;
    this.logs.push(logLine);
    // 只保留最近 100 条日志
    if (this.logs.length > 100) {
      this.logs.shift();
    }
    if (this.onLogCallback) {
      this.onLogCallback(logLine);
    }
  }

  private async findPython(): Promise<string | null> {
    // 尝试常见的 Python 路径
    const candidates = [
      // 项目虚拟环境
      path.join(app.getAppPath(), '../../.venv/bin/python'),
      path.join(app.getAppPath(), '../../.venv/Scripts/python.exe'),
      // 开发模式（相对于项目根目录）
      path.join(__dirname, '../../../../.venv/bin/python'),
      path.join(__dirname, '../../../../.venv/Scripts/python.exe'),
      // 系统 Python
      'python3',
      'python',
    ];

    // 开发环境特殊处理
    if (!app.isPackaged) {
      const projectRoot = path.join(__dirname, '../../../..');
      candidates.unshift(path.join(projectRoot, '.venv/bin/python'));
      candidates.unshift(path.join(projectRoot, '.venv/Scripts/python.exe'));
    }

    for (const candidate of candidates) {
      try {
        // 简单检查（不实际执行，避免权限问题）
        return candidate;
      } catch {
        continue;
      }
    }

    return 'python3'; // 回退到系统 python3
  }

  private findServerScript(): string | null {
    // 查找 server.py
    const candidates = [
      // 开发模式
      path.join(__dirname, '../../../../rpa_core/server.py'),
      // 打包后
      path.join(app.getAppPath(), '../../rpa_core/server.py'),
    ];

    if (!app.isPackaged) {
      const projectRoot = path.join(__dirname, '../../../..');
      candidates.unshift(path.join(projectRoot, 'rpa_core/server.py'));
    }

    for (const candidate of candidates) {
      return candidate; // 直接返回，让 Python 去处理错误
    }

    return null;
  }

  private async waitForServer(maxRetries = 30, interval = 1000): Promise<void> {
    for (let i = 0; i < maxRetries; i++) {
      try {
        const response = await fetch(`${PYTHON_API_URL}/health`);
        if (response.ok) {
          return;
        }
      } catch {
        // 继续等待
      }
      await new Promise((resolve) => setTimeout(resolve, interval));
    }
    throw new Error('等待 Python 服务超时');
  }
}

// 单例实例
export const pythonManager = new PythonManager();
