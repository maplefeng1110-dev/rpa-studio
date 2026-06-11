/**
 * IPC 类型定义
 */
import type { ElectronAPI } from '../../main/preload';

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
