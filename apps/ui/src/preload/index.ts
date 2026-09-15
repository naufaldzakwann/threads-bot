import { contextBridge, ipcRenderer } from 'electron';
contextBridge.exposeInMainWorld('thb', {
  onCoreReady: (cb: (info: unknown) => void) => ipcRenderer.on('core-ready', (_e, v) => cb(v)),
  onKill: (cb: (info: unknown) => void) => ipcRenderer.on('kill', (_e, v) => cb(v)),
});
