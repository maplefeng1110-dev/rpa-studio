/**
 * Electron 主进程入口
 */
import { app, BrowserWindow } from 'electron';
import path from 'path';
import { registerIpcHandlers } from './ipc';
import { pythonManager } from './python/manager';

let mainWindow: BrowserWindow | null = null;
let ipcHandlersRegistered = false;

const isDev = !app.isPackaged;

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false,
    },
  });

  // IPC 处理器只注册一次，防止 macOS activate 重复注册导致崩溃
  if (!ipcHandlersRegistered) {
    registerIpcHandlers(mainWindow);
    ipcHandlersRegistered = true;
  }

  if (isDev) {
    // 开发模式 - 加载 Vite 开发服务器
    mainWindow.loadURL('http://localhost:5173');
    // 不自动打开 DevTools，需要时可以用 Cmd+Option+I 手动打开
  } else {
    // 生产模式 - 加载构建后的文件
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// 应用就绪
app.whenReady().then(async () => {
  createWindow();

  // 检查 Python 后端服务是否已在运行，若未运行则自动启动
  setTimeout(async () => {
    try {
      const response = await fetch('http://127.0.0.1:8765/health');
      if (response.ok) {
        console.log('检测到外部 Python 后端已在运行，不进行自动启动。');
      }
    } catch {
      console.log('未检测到活跃的 Python 后端，正在尝试自动启动...');
      pythonManager.start().catch((err) => {
        console.error('自动启动 Python 后端失败:', err);
      });
    }
  }, 1000);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// 所有窗口关闭时退出应用
app.on('window-all-closed', async () => {
  // 停止 Python 后端
  await pythonManager.stop();

  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// 应用退出前
app.on('before-quit', async (e) => {
  e.preventDefault();
  await pythonManager.stop();
  app.exit();
});
